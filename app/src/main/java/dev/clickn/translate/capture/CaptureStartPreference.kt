package dev.clickn.translate.capture

import android.content.Context
import android.content.SharedPreferences
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext

/** Local device choice only: never included in translation presets or portable settings. */
object CaptureStartPreference {
    private val store = CaptureStartPreferenceStore()
    val mode = store.mode
    val initialized = store.initialized
    suspend fun initialize(context: Context) = store.initialize(context)
    fun select(mode: CaptureStartMode) = store.select(mode)
    internal fun revision(): Long = store.revision()
    internal fun selectIfUnchanged(mode: CaptureStartMode, expectedRevision: Long): Boolean =
        store.selectIfUnchanged(mode, expectedRevision)
    internal suspend fun awaitPersistence(): Boolean = store.awaitPersistence()
}

internal class CaptureStartPreferenceStore(
    private val writerScope: CoroutineScope = CoroutineScope(SupervisorJob() + Dispatchers.IO),
) {
    private val lock = Any()
    private val initializeMutex = Mutex()
    private val writeMutex = Mutex()
    private val selected = MutableStateFlow<CaptureStartMode?>(null)
    val mode = selected.asStateFlow()
    private val loaded = MutableStateFlow(false)
    val initialized = loaded.asStateFlow()
    private var storage: SharedPreferences? = null
    private var selectionRevision = 0L

    suspend fun initialize(context: Context, preferencesName: String = "clickn_capture_start_v1"): Unit =
        withContext(Dispatchers.IO) {
            initializeMutex.withLock {
                if (loaded.value && synchronized(lock) { storage != null }) return@withLock
                // Both obtaining SharedPreferences and the first read may load disk data.
                val preferences = runCatching {
                    context.applicationContext.getSharedPreferences(preferencesName, Context.MODE_PRIVATE)
                }.getOrNull()
                val stored = runCatching { preferences?.getString("mode", null) }.getOrNull()
                    ?.let { name -> CaptureStartMode.entries.firstOrNull { it.name == name } }
                val hasPendingChoice = synchronized(lock) {
                    storage = preferences
                    if (selectionRevision == 0L) selected.value = stored ?: CaptureStartMode.SYSTEM
                    loaded.value = true
                    selectionRevision > 0L
                }
                if (hasPendingChoice) awaitPersistence()
            }
        }

    fun revision(): Long = synchronized(lock) { selectionRevision }

    fun select(mode: CaptureStartMode) {
        synchronized(lock) {
            ++selectionRevision // A repeated SYSTEM selection still invalidates a pending authorization.
            selected.value = mode
        }
        writerScope.launch { awaitPersistence() }
    }

    fun selectIfUnchanged(mode: CaptureStartMode, expectedRevision: Long): Boolean {
        val selectedNow = synchronized(lock) {
            if (selectionRevision != expectedRevision) false else {
                ++selectionRevision
                selected.value = mode
                true
            }
        }
        if (selectedNow) writerScope.launch { awaitPersistence() }
        return selectedNow
    }

    /** Serializes writes and catches up to the latest choice if it changed during commit. */
    suspend fun awaitPersistence(): Boolean = withContext(Dispatchers.IO) {
        writeMutex.withLock {
            try {
                while (true) {
                    currentCoroutineContext().ensureActive()
                    val snapshot = synchronized(lock) {
                        val preferences = storage ?: return@withLock false
                        val value = selected.value ?: return@withLock false
                        Triple(preferences, value, selectionRevision)
                    }
                    if (!snapshot.first.edit().putString("mode", snapshot.second.name).commit()) return@withLock false
                    if (synchronized(lock) { selectionRevision == snapshot.third }) return@withLock true
                }
                @Suppress("UNREACHABLE_CODE") false
            } catch (cancelled: CancellationException) { throw cancelled }
            catch (_: Exception) { false }
        }
    }
}
