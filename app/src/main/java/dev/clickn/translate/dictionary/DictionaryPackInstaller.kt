// Modified for Click'n'Translate on October 3, 2026.
package dev.clickn.translate.dictionary

import android.content.Context
import android.database.sqlite.SQLiteCantOpenDatabaseException
import android.database.sqlite.SQLiteDatabaseCorruptException
import android.database.sqlite.SQLiteException
import android.database.sqlite.SQLiteDatabase
import android.database.sqlite.SQLiteDatabase.NO_LOCALIZED_COLLATORS
import android.database.sqlite.SQLiteDatabase.OPEN_READONLY
import android.net.Uri
import android.system.Os
import dagger.hilt.android.qualifiers.ApplicationContext
import java.io.File
import java.io.FileOutputStream
import javax.inject.Inject
import javax.inject.Singleton
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext

data class DictionaryPackStatus(
    val spec: DictionaryPackSpec,
    val installed: Boolean,
    val version: String = "",
    val entryCount: Long? = null,
    val byteCount: Long = 0L,
    val invalidReason: String? = null,
    val invalidKind: DictionaryPackFailureKind? = null,
)

sealed interface DictionaryPackInstallResult {
    data class Success(val status: DictionaryPackStatus) : DictionaryPackInstallResult
    data class Failure(
        val reason: String,
        val kind: DictionaryPackFailureKind = DictionaryPackFailureKind.UNKNOWN,
    ) : DictionaryPackInstallResult
}

@Singleton
class DictionaryPackInstaller @Inject constructor(
    @ApplicationContext private val context: Context,
) {
    suspend fun statuses(): List<DictionaryPackStatus> = withContext(Dispatchers.IO) {
        DictionaryPackCatalog.all.map { status(it) }
    }

    suspend fun importPack(
        uri: Uri,
        expectedId: DictionaryPackId,
    ): DictionaryPackInstallResult = withContext(Dispatchers.IO) {
        fileOperations.withLock {
            val directory = packDirectory(context)
            var temporary: File? = null
            try {
                currentCoroutineContext().ensureActive()
                val staging = packOperation(DictionaryPackFailureKind.STORAGE) {
                    if (!directory.isDirectory && !directory.mkdirs()) {
                        throw PackImportException(DictionaryPackFailureKind.STORAGE)
                    }
                    File.createTempFile("dictionary-import-", ".db", directory)
                }
                temporary = staging
                val input = packOperation(DictionaryPackFailureKind.READ) {
                    context.contentResolver.openInputStream(uri)
                } ?: return@withLock packFailure(DictionaryPackFailureKind.READ)
                input.use { source ->
                    packOperation(DictionaryPackFailureKind.STORAGE) {
                        FileOutputStream(staging).use { output ->
                            val buffer = ByteArray(DEFAULT_BUFFER_SIZE)
                            var total = 0L
                            while (true) {
                                currentCoroutineContext().ensureActive()
                                val count = packOperation(DictionaryPackFailureKind.READ) { source.read(buffer) }
                                if (count < 0) break
                                total += count
                                if (total > MAX_PACK_BYTES) {
                                    return@withLock packFailure(DictionaryPackFailureKind.TOO_LARGE)
                                }
                                output.write(buffer, 0, count)
                            }
                            output.fd.sync()
                        }
                    }
                }
                currentCoroutineContext().ensureActive()
                val validated = validate(staging, expectedId)
                if (validated.invalidReason != null) {
                    return@withLock DictionaryPackInstallResult.Failure(
                        validated.invalidReason,
                        validated.invalidKind ?: DictionaryPackFailureKind.UNKNOWN,
                    )
                }
                currentCoroutineContext().ensureActive()
                // Same-directory POSIX rename is the commit point. Readers retain the old inode;
                // there is no target->backup gap and a failed rename leaves the old pack intact.
                withContext(NonCancellable) {
                    packOperation(DictionaryPackFailureKind.STORAGE) {
                        Os.rename(staging.absolutePath, packFile(context, expectedId).absolutePath)
                    }
                    DictionaryPackInstallResult.Success(validated)
                }
            } catch (cancelled: CancellationException) {
                throw cancelled
            } catch (error: Exception) {
                packFailure(error.packFailureKind(DictionaryPackFailureKind.UNKNOWN))
            } finally {
                temporary?.delete()
            }
        }
    }

    suspend fun delete(id: DictionaryPackId): Boolean = withContext(Dispatchers.IO) {
        fileOperations.withLock {
            currentCoroutineContext().ensureActive()
            val file = packFile(context, id)
            !file.exists() || file.delete()
        }
    }

    private suspend fun status(spec: DictionaryPackSpec): DictionaryPackStatus {
        val file = packFile(context, spec.id)
        if (!file.isFile) return DictionaryPackStatus(spec = spec, installed = false)
        return validate(file, spec.id).copy(byteCount = file.length())
    }

    private suspend fun validate(file: File, expectedId: DictionaryPackId): DictionaryPackStatus {
        val spec = DictionaryPackCatalog.byId(expectedId)
        return try {
            cancellableDictionaryRead { signal ->
                SQLiteDatabase.openDatabase(
                    file.absolutePath,
                    null,
                    OPEN_READONLY or NO_LOCALIZED_COLLATORS,
                ).use { database ->
                    val integrity = database.rawQuery("PRAGMA quick_check(1)", null, signal).use { cursor ->
                        if (cursor.moveToFirst()) cursor.getString(0) else "invalid"
                    }
                    if (!integrity.equals("ok", ignoreCase = true)) {
                        throw PackImportException(DictionaryPackFailureKind.CORRUPT)
                    }
                    DictionaryPackContract.requiredColumns.forEach { (table, required) ->
                        val realTable = database.rawQuery(
                            "SELECT type, sql FROM sqlite_master WHERE name = ?",
                            arrayOf(table), signal,
                        ).use { cursor ->
                            cursor.moveToFirst() && cursor.getString(0) == "table" &&
                                !cursor.getString(1).orEmpty().trimStart().startsWith("CREATE VIRTUAL", ignoreCase = true)
                        }
                        if (!realTable) throw PackImportException(DictionaryPackFailureKind.SCHEMA)
                        val actual = database.rawQuery("PRAGMA table_info($table)", null, signal).use { cursor ->
                            buildSet {
                                while (cursor.moveToNext()) add(cursor.getString(1))
                            }
                        }
                        if (!actual.containsAll(required)) throw PackImportException(DictionaryPackFailureKind.SCHEMA)
                    }
                    val metadata = database.rawQuery(
                        "SELECT key, value FROM ${DictionaryPackContract.METADATA_TABLE}",
                        null,
                        signal,
                    ).use { cursor ->
                        buildMap {
                            while (cursor.moveToNext()) put(cursor.getString(0), cursor.getString(1))
                        }
                    }
                    if (metadata["pack_id"] != expectedId.wireId) {
                        throw PackImportException(DictionaryPackFailureKind.WRONG_PACK)
                    }
                    if (metadata["schema_version"]?.toIntOrNull() != DictionaryPackContract.SCHEMA_VERSION) {
                        throw PackImportException(DictionaryPackFailureKind.VERSION)
                    }
                    DictionaryPackStatus(
                        spec = spec,
                        installed = true,
                        version = metadata["data_version"].orEmpty(),
                        entryCount = metadata["entry_count"]?.toLongOrNull(),
                        byteCount = file.length(),
                    )
                }
            }
        } catch (cancelled: CancellationException) {
            throw cancelled
        } catch (error: Exception) {
            val kind = error.packFailureKind(DictionaryPackFailureKind.UNKNOWN)
            DictionaryPackStatus(
                spec = spec,
                installed = false,
                byteCount = file.length(),
                invalidReason = kind.name,
                invalidKind = kind,
            )
        }
    }

    companion object {
        // Shared across installer instances, including a delete racing a replacement.
        private val fileOperations = Mutex()
        private const val DIRECTORY_NAME = "dictionaries"
        private const val MAX_PACK_BYTES = 2L * 1024L * 1024L * 1024L

        fun packDirectory(context: Context): File = File(context.filesDir, DIRECTORY_NAME)

        fun packFile(context: Context, id: DictionaryPackId): File =
            File(packDirectory(context), id.fileName)
    }
}

private class PackImportException(
    val kind: DictionaryPackFailureKind,
    cause: Exception? = null,
) : Exception(kind.name, cause)

private fun Exception.packFailureKind(fallback: DictionaryPackFailureKind): DictionaryPackFailureKind = when (this) {
    is PackImportException -> kind
    is SQLiteDatabaseCorruptException -> DictionaryPackFailureKind.CORRUPT
    is SQLiteCantOpenDatabaseException -> DictionaryPackFailureKind.READ
    is SQLiteException -> DictionaryPackFailureKind.SCHEMA
    is java.io.IOException, is SecurityException -> DictionaryPackFailureKind.READ
    else -> fallback
}

private fun packFailure(kind: DictionaryPackFailureKind) = DictionaryPackInstallResult.Failure(kind.name, kind)

private inline fun <T> packOperation(kind: DictionaryPackFailureKind, operation: () -> T): T = try {
    operation()
} catch (cancelled: CancellationException) {
    throw cancelled
} catch (known: PackImportException) {
    throw known
} catch (error: Exception) {
    throw PackImportException(kind, error)
}
