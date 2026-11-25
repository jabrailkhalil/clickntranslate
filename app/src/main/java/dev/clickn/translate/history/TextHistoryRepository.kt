package dev.clickn.translate.history

import androidx.room.withTransaction
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.emitAll
import kotlinx.coroutines.flow.flow
import kotlinx.coroutines.flow.flowOn
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext
import kotlinx.serialization.Serializable
import kotlinx.serialization.builtins.ListSerializer
import kotlinx.serialization.json.Json

interface LegacyTextHistorySource {
    suspend fun read(): String
    suspend fun erase()
}

enum class TextHistoryIssue { LEGACY_IMPORT, LEGACY_ERASE, STORAGE }

data class TextHistoryState(
    val entries: List<TextHistoryEntry> = emptyList(),
    val loading: Boolean = true,
    val issue: TextHistoryIssue? = null,
)

/** All JSON/file work runs on IO; only Room transactions decide which writes may become visible. */
class TextHistoryRepository(
    private val database: TextHistoryDatabase,
    private val legacy: LegacyTextHistorySource,
) {
    private val dao = database.historyDao()
    private val importMutex = Mutex()
    private val issue = MutableStateFlow<TextHistoryIssue?>(null)
    private val json = Json { ignoreUnknownKeys = true }

    fun observe(): Flow<TextHistoryState> = flow {
        initialize()
        emitAll(combine(dao.observeAll(), dao.observeState(), issue) { entries, state, warning ->
            val visibleIssue = when {
                state?.legacyErasePending == true -> TextHistoryIssue.LEGACY_ERASE
                warning == TextHistoryIssue.LEGACY_IMPORT && state?.legacyImported != true -> warning
                else -> null
            }
            TextHistoryState(entries = entries, loading = false, issue = visibleIssue)
        })
    }.flowOn(Dispatchers.IO)

    /** Obtain before starting a translation, so Clear can reject a result already in flight. */
    suspend fun writeGeneration(): Long = withContext(Dispatchers.IO) {
        initialize()
        dao.state()?.generation ?: 0
    }

    suspend fun save(entry: TextHistoryEntry, generation: Long): Boolean = withContext(Dispatchers.IO) {
        database.withTransaction {
            if ((dao.state()?.generation ?: 0) != generation) return@withTransaction false
            dao.deletePrevious(entry.source, entry.from, entry.to, entry.provider)
            dao.insert(entry.copy(id = 0))
            true
        }
    }

    suspend fun clear() = withContext(Dispatchers.IO) {
        database.withTransaction {
            val previous = dao.state() ?: TextHistoryStoreState()
            dao.deleteAll()
            dao.putState(previous.copy(
                legacyImported = true,
                generation = Math.addExact(previous.generation, 1),
                legacyErasePending = true,
            ))
        }
        // If interrupted here, the durable receipt prevents resurrection and the next open retries erasure.
        finishLegacyErase()
    }

    private suspend fun initialize() = importMutex.withLock {
        val state = dao.state()
        if (state?.legacyErasePending == true) finishLegacyErase()
        if (state?.legacyImported == true) return@withLock
        val decoded = try {
            json.decodeFromString(ListSerializer(LegacyEntry.serializer()), legacy.read())
        } catch (cancelled: CancellationException) {
            throw cancelled
        } catch (_: Exception) {
            // Keep the original bytes and do not write a success receipt. New Room history remains usable.
            issue.value = if (dao.state()?.legacyImported == true) null else TextHistoryIssue.LEGACY_IMPORT
            return@withLock
        }
        database.withTransaction {
            val current = dao.state() ?: TextHistoryStoreState()
            if (!current.legacyImported) {
                // Old IDs were timestamps. Preserve them as dates, independently of Room row IDs.
                for (old in decoded.asReversed()) {
                    if (!dao.contains(old.id, old.source, old.translated, old.from, old.to, old.provider)) {
                        dao.insert(TextHistoryEntry(createdAtMs = old.id, source = old.source,
                            translated = old.translated, from = old.from, to = old.to, provider = old.provider))
                    }
                }
                dao.putState(current.copy(legacyImported = true))
            }
        }
        issue.value = null
    }

    private suspend fun finishLegacyErase() {
        try {
            legacy.erase()
            database.withTransaction {
                dao.state()?.takeIf { it.legacyErasePending }?.let {
                    dao.putState(it.copy(legacyErasePending = false))
                }
            }
            issue.value = null
        } catch (cancelled: CancellationException) {
            throw cancelled
        } catch (_: Exception) {
            // The pending receipt drives the warning, including after process loss or a competing clear.
        }
    }

    @Serializable
    private data class LegacyEntry(
        val id: Long, val source: String, val translated: String,
        val from: String, val to: String, val provider: String,
    )
}
