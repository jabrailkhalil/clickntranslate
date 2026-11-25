package dev.clickn.translate.data

import android.content.Context
import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.PreferenceDataStoreFactory
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.preferencesDataStoreFile
import dagger.hilt.android.qualifiers.ApplicationContext
import java.io.Closeable
import java.io.File
import javax.inject.Inject
import javax.inject.Singleton
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancelAndJoin

/** One Hilt/Application owner, one file and one IO scope. No process-static Context delegate. */
@Singleton
class SettingsStorage internal constructor(file: File) : Closeable {
    @Inject constructor(@ApplicationContext context: Context) : this(
        context.preferencesDataStoreFile("clickntranslate_settings"),
    )

    private val ownerJob = SupervisorJob()
    private val ownerScope = CoroutineScope(ownerJob + Dispatchers.IO)
    private val storageFile = file.canonicalFile
    val dataStore: DataStore<Preferences> = PreferenceDataStoreFactory.create(scope = ownerScope) { storageFile }

    /** Application termination cannot block its main thread waiting for file IO. */
    override fun close() { ownerJob.cancel() }

    /** Explicit owners in tests wait for file handles to close before reopening/deleting their files. */
    internal suspend fun closeAndJoin() { ownerJob.cancelAndJoin() }
    internal val isClosed: Boolean get() = !ownerJob.isActive
}
