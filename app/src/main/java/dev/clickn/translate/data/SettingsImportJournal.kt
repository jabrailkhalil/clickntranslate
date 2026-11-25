package dev.clickn.translate.data

import android.system.Os
import android.system.OsConstants
import android.util.AtomicFile
import dev.clickn.translate.glossary.GlossaryImportRollback
import java.io.File
import java.io.FileOutputStream
import java.io.ByteArrayOutputStream
import java.nio.file.Files
import java.util.UUID
import kotlinx.serialization.Serializable
import kotlinx.serialization.encodeToString
import kotlinx.serialization.decodeFromString
import kotlinx.serialization.json.Json

@Serializable
internal data class ImportPreferenceValue(val kind: String, val values: List<String>) {
    override fun toString(): String = "ImportPreferenceValue(<redacted>)"
}

@Serializable
internal data class ImportPreferenceChange(
    val name: String,
    val before: ImportPreferenceValue?,
    val after: ImportPreferenceValue?,
) {
    override fun toString(): String = "ImportPreferenceChange(<redacted>)"
}

@Serializable
internal data class ImportFontChange(
    val fileName: String,
    val backupName: String?,
    val beforeSha256: String?,
    val afterSha256: String,
    val published: Boolean = false,
    val referencedBefore: Boolean = false,
)

@Serializable
internal data class SettingsImportRecord(
    val version: Int = 1,
    val id: String,
    val decision: String = PENDING,
    val settings: List<ImportPreferenceChange> = emptyList(),
    val glossary: List<GlossaryImportRollback.Change> = emptyList(),
    val fonts: List<ImportFontChange> = emptyList(),
    val uiPreferences: List<ImportUiPreferenceChange> = emptyList(),
) {
    override fun toString(): String = "SettingsImportRecord(<redacted>)"

    companion object {
        const val PENDING = "pending"
        const val COMMITTED = "committed"
        const val ROLLED_BACK = "rolled_back"
    }
}

/** Local encrypted write-ahead intent. Never participates in the portable ZIP format. */
internal class SettingsImportJournal(
    private val root: File,
    private val cipher: SettingsSecretCipher,
    private val syncDirectoryAction: (File) -> Unit = Companion::syncDirectory,
) {
    private val atomic get() = AtomicFile(File(root, FILE_NAME))
    private val json = Json { encodeDefaults = true }
    private var ownerId: String? = null

    fun begin(): File = synchronized(operationLock) {
        check(read() == null) { "A settings import still needs recovery." }
        ensureOwnedDirectory(root)
        cleanUnpublishedStaging()
        val record = SettingsImportRecord(id = UUID.randomUUID().toString())
        val directory = directory(record)
        check(directory.mkdir()) { "Could not create private import staging." }
        syncDirectoryAction(root)
        ownerId = record.id
        write(record)
        // API26 AtomicFile writes its very first base directly. An empty activation inode
        // proves that initial intent finished before any store mutation was allowed.
        val activation = File(root, ACTIVE_MARKER)
        check(activation.createNewFile()) { "Could not activate private import intent." }
        FileOutputStream(activation, true).use { it.fd.sync() }
        syncDirectoryAction(root)
        directory
    }

    fun read(): SettingsImportRecord? = synchronized(operationLock) {
        ensureNoLinks(root)
        if (!hasRecord(root)) return@synchronized null
        listOf(FILE_NAME, "$FILE_NAME.bak", "$FILE_NAME.new", ACTIVE_MARKER).forEach { ensureNoLinks(File(root, it)) }
        val activation = File(root, ACTIVE_MARKER)
        if (!activation.exists()) {
            // Unactivated bootstrap, or cleanup after a durable terminal decision.
            // Neither state can own an unfinished store mutation.
            atomic.delete()
            check(!hasRecord(root)) { "Could not remove unpublished import intent." }
            syncDirectoryAction(root)
            cleanUnpublishedStaging()
            return@synchronized null
        }
        check(activation.isFile && activation.length() == 0L) { "Invalid private import activation marker." }
        val encrypted = atomic.openRead().use { input ->
            val output = ByteArrayOutputStream()
            val buffer = ByteArray(8 * 1024)
            while (true) {
                val count = input.read(buffer)
                if (count < 0) break
                check(output.size() + count <= MAX_RECORD_BYTES) { "Private import record is too large." }
                output.write(buffer, 0, count)
            }
            output.toByteArray().toString(Charsets.UTF_8)
        }
        val record = try {
            json.decodeFromString<SettingsImportRecord>(cipher.decrypt(encrypted))
        } catch (_: Exception) {
            throw IllegalStateException("Private settings import recovery record cannot be read.")
        }
        validate(record)
        check(ownerId == null || ownerId == record.id) { "Private import ownership changed." }
        ownerId = record.id
        record
    }

    fun recordSettings(changes: List<ImportPreferenceChange>) = update { it.copy(settings = changes) }
    fun recordGlossary(changes: List<GlossaryImportRollback.Change>) = update { it.copy(glossary = changes) }
    fun recordUiPreferences(changes: List<ImportUiPreferenceChange>) = update { it.copy(uiPreferences = changes) }
    fun recordFont(change: ImportFontChange) = update { record ->
        check(record.fonts.none { it.fileName == change.fileName }) { "Duplicate private font intent." }
        record.copy(fonts = record.fonts + change)
    }

    fun markFontPublished(fileName: String) = update { record ->
        check(record.fonts.any { it.fileName == fileName })
        record.copy(fonts = record.fonts.map { if (it.fileName == fileName) it.copy(published = true) else it })
    }

    fun decide(decision: String) = update(pendingOnly = false) { record ->
        check(decision in setOf(SettingsImportRecord.COMMITTED, SettingsImportRecord.ROLLED_BACK))
        check(record.decision == SettingsImportRecord.PENDING || record.decision == decision) {
            "A terminal private import decision cannot change."
        }
        record.copy(decision = decision)
    }

    fun directory(record: SettingsImportRecord): File = synchronized(operationLock) {
        validate(record)
        val result = File(root, record.id)
        check(result.canonicalFile.parentFile == root.canonicalFile) { "Invalid private import directory." }
        ensureNoLinks(result)
        result
    }

    /** The only recursive cleanup target is the exact journal-owned UUID directory. */
    fun cleanTerminal(record: SettingsImportRecord) = synchronized(operationLock) {
        check(record.decision != SettingsImportRecord.PENDING) { "Unfinished import must retain its backups." }
        check(read() == record) { "Private import cleanup does not own the active record." }
        // A prior finishWrite may have succeeded while its directory fsync failed.
        // Re-establish terminal durability before deleting the only original backups.
        write(record)
        val directory = directory(record)
        if (directory.exists()) {
            check(directory.walkTopDown().all { !Files.isSymbolicLink(it.toPath()) }) { "Private import contains a link." }
            check(directory.deleteRecursively()) { "Could not clean private import staging." }
        }
        // Once backups are gone, a terminal decision is durable. Removing activation first
        // makes interruption between this removal and AtomicFile.delete safe to discard.
        check(File(root, ACTIVE_MARKER).delete()) { "Could not remove private import activation." }
        syncDirectoryAction(root)
        atomic.delete()
        check(!hasRecord(root)) { "Could not remove completed import record." }
        syncDirectoryAction(root)
    }

    private fun update(
        pendingOnly: Boolean = true,
        transform: (SettingsImportRecord) -> SettingsImportRecord,
    ) = synchronized(operationLock) {
        // DataStore/Room may finish a callback on another thread after its caller was
        // cancelled. Read under the shared lock; a cached record could erase another
        // checkpoint or resurrect an already cleaned/replaced import.
        val before = checkNotNull(read()) { "No active private settings import." }
        check(!pendingOnly || before.decision == SettingsImportRecord.PENDING) { "Private import is already terminal." }
        write(transform(before))
    }

    private fun write(record: SettingsImportRecord) {
        validate(record)
        ensureOwnedDirectory(root)
        listOf(FILE_NAME, "$FILE_NAME.bak", "$FILE_NAME.new").forEach { ensureNoLinks(File(root, it)) }
        val plain = json.encodeToString(record)
        val encrypted = cipher.encrypt(plain)
        check(encrypted.isNotEmpty() && encrypted != plain) { "Settings import requires encrypted local storage." }
        val bytes = encrypted.toByteArray(Charsets.UTF_8)
        check(bytes.size <= MAX_RECORD_BYTES) { "Private import record is too large." }
        val output = atomic.startWrite()
        var finished = false
        try {
            output.write(bytes)
            output.fd.sync()
            atomic.finishWrite(output)
            finished = true
            syncDirectoryAction(root)
        } catch (error: Throwable) {
            // API26 failWrite deletes the base and restores .bak. After finishWrite
            // removed .bak, calling it for a failed directory fsync destroys the
            // only published intent. Retain that intent for a fresh recovery read.
            if (!finished) atomic.failWrite(output)
            throw error
        }
    }

    /** Only empty/pre-parse UUID directories can exist here without a published active record. */
    private fun cleanUnpublishedStaging() {
        check(!hasRecord(root)) { "Published import must be recovered before orphan cleanup." }
        root.listFiles().orEmpty().forEach { file ->
            if (!file.isDirectory || runCatching { UUID.fromString(file.name).toString() == file.name }.getOrDefault(false).not()) return@forEach
            ensureNoLinks(file)
            check(file.canonicalFile.parentFile == root.canonicalFile)
            check(file.walkTopDown().all { !Files.isSymbolicLink(it.toPath()) }) { "Private import contains a link." }
            check(file.deleteRecursively()) { "Could not clean unpublished import staging." }
        }
        if (root.exists()) syncDirectoryAction(root)
    }

    private fun validate(record: SettingsImportRecord) {
        check(record.version == 1 && runCatching { UUID.fromString(record.id).toString() == record.id }.getOrDefault(false)) {
            "Unsupported private import record."
        }
        check(record.decision in setOf(SettingsImportRecord.PENDING, SettingsImportRecord.COMMITTED, SettingsImportRecord.ROLLED_BACK))
        check(record.settings.map { it.name }.distinct().size == record.settings.size)
        check(record.uiPreferences.map { it.field }.distinct().size == record.uiPreferences.size)
        record.uiPreferences.forEach(ImportUiPreferenceChange::validate)
        record.settings.forEach { change ->
            check(change.name.isNotBlank() && change.name.length <= 256)
            listOfNotNull(change.before, change.after).forEach(ImportPreferenceValues::validate)
        }
        record.glossary.forEach { check(it.after.id > 0 && (it.before == null || it.before.id == it.after.id)) }
        record.fonts.forEach {
            check(OverlayFontPolicy.normalizeStoredFileName(it.fileName) == it.fileName)
            check(it.afterSha256.matches(Regex("[a-f0-9]{64}")))
            check(it.beforeSha256 == null || it.beforeSha256.matches(Regex("[a-f0-9]{64}")))
            check((it.backupName == null) == (it.beforeSha256 == null))
            check(it.backupName == null || it.backupName == "backup-${it.fileName}")
        }
    }

    companion object {
        const val DIRECTORY = "settings-import-journal-v1"
        private const val FILE_NAME = "active.enc"
        private const val ACTIVE_MARKER = "activated"
        private const val MAX_RECORD_BYTES = 32 * 1024 * 1024
        // AtomicFile provides no locking. One app process owns this coordinator;
        // shared locking also fences late callbacks from different journal instances.
        private val operationLock = Any()

        fun hasRecord(root: File): Boolean = synchronized(operationLock) {
            listOf(FILE_NAME, "$FILE_NAME.bak", "$FILE_NAME.new", ACTIVE_MARKER).any { File(root, it).exists() }
        }

        internal fun ensureNoLinks(file: File) {
            check(!Files.isSymbolicLink(file.toPath())) { "Private import path is a link." }
        }

        internal fun ensureOwnedDirectory(directory: File) {
            ensureNoLinks(directory)
            check(directory.isDirectory || directory.mkdirs()) { "Could not create private import storage." }
        }

        internal fun syncDirectory(directory: File) {
            val descriptor = Os.open(directory.absolutePath, OsConstants.O_RDONLY, 0)
            try {
                check(OsConstants.S_ISDIR(Os.fstat(descriptor).st_mode)) { "Private import sync target is not a directory." }
                Os.fsync(descriptor)
            } finally { Os.close(descriptor) }
        }

        internal fun copyAndSync(source: File, target: File) {
            FileOutputStream(target).use { output ->
                source.inputStream().use { it.copyTo(output) }
                output.fd.sync()
            }
            syncDirectory(checkNotNull(target.parentFile))
        }
    }
}
