package dev.clickn.translate.gallery

import android.util.AtomicFile
import java.io.File
import java.io.FileOutputStream
import java.nio.file.Files
import java.nio.file.LinkOption.NOFOLLOW_LINKS
import java.security.MessageDigest
import java.util.UUID
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.ensureActive
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json

internal const val GALLERY_EXPORT_MAX_BYTES = 64L * 1024 * 1024
internal const val GALLERY_EXPORT_MAX_RECEIPTS = 64
private const val MAX_JOURNAL_BYTES = 512 * 1024
private const val MAX_PAYLOAD_TOTAL_BYTES = 256L * 1024 * 1024

@Serializable
internal enum class GalleryExportReceiptPhase { PREPARED, PENDING, COMPLETE, DELETED, RETAINED }

/** The URI is private bookkeeping, never diagnostic output. No names or translated text are stored. */
@Serializable
internal data class GalleryExportReceipt(
    val id: String,
    val phase: GalleryExportReceiptPhase,
    val uri: String? = null,
    val byteCount: Long,
    val sha256: String,
) {
    override fun toString(): String = "GalleryExportReceipt(<redacted>, phase=$phase)"
}

@Serializable
private data class GalleryExportJournal(
    val version: Int = 1,
    val receipts: List<GalleryExportReceipt>,
    val lastExaminedId: String? = null,
)

/** Caller holds the export mutex. AtomicFile supplies durability, not mutual exclusion. */
internal class GalleryExportReceiptStore(
    private val directory: File,
    private val atomic: AtomicFile = AtomicFile(File(directory, "receipts.json")),
) {
    private val json = Json
    private val journalFile get() = File(directory, "receipts.json")

    fun load(): List<GalleryExportReceipt> = readJournal().receipts

    fun lastExaminedId(): String? = readJournal().lastExaminedId

    fun advanceCursor(id: String) {
        check(ID.matches(id))
        saveJournal(readJournal().copy(lastExaminedId = id))
    }

    private fun readJournal(): GalleryExportJournal {
        requireDirectory()
        val related = listOf(journalFile, File(directory, "receipts.json.bak"), File(directory, "receipts.json.new"))
        related.filter(::exists).forEach(::requireRegular)
        if (!exists(journalFile) && !exists(related[1])) {
            check(!exists(related[2])) { "Export journal needs recovery." }
            return GalleryExportJournal(receipts = emptyList())
        }
        val bytes = atomic.openRead().use { input ->
            val result = input.readBytesLimited(MAX_JOURNAL_BYTES)
            check(result.size <= MAX_JOURNAL_BYTES) { "Export journal is too large." }
            result
        }
        val value = json.decodeFromString(GalleryExportJournal.serializer(), bytes.toString(Charsets.UTF_8))
        check(value.version == 1 && value.receipts.size <= GALLERY_EXPORT_MAX_RECEIPTS)
        check(value.lastExaminedId == null || ID.matches(value.lastExaminedId))
        check(value.receipts.map { it.id }.distinct().size == value.receipts.size)
        value.receipts.forEach { receipt ->
            check(ID.matches(receipt.id) && HASH.matches(receipt.sha256))
            check(receipt.byteCount in 1..GALLERY_EXPORT_MAX_BYTES)
            check(when (receipt.phase) {
                GalleryExportReceiptPhase.PREPARED -> receipt.uri == null
                GalleryExportReceiptPhase.RETAINED -> receipt.uri == null || validUri(receipt.uri)
                else -> validUri(receipt.uri)
            })
        }
        return value
    }

    fun save(receipts: List<GalleryExportReceipt>) {
        saveJournal(readJournal().copy(receipts = receipts))
    }

    private fun saveJournal(journal: GalleryExportJournal) {
        requireDirectory()
        check(journal.receipts.size <= GALLERY_EXPORT_MAX_RECEIPTS)
        listOf(journalFile, File(directory, "receipts.json.bak"), File(directory, "receipts.json.new"))
            .filter(::exists).forEach(::requireRegular)
        val bytes = json.encodeToString(GalleryExportJournal.serializer(), journal)
            .toByteArray(Charsets.UTF_8)
        check(bytes.size <= MAX_JOURNAL_BYTES)
        val output = atomic.startWrite()
        try {
            output.write(bytes)
            atomic.finishWrite(output)
        } catch (error: Throwable) {
            atomic.failWrite(output)
            throw error
        }
        // Do not forget a source on an apparently committed but unreadable journal.
        check(readJournal() == journal) { "Export journal was not committed." }
    }

    suspend fun prepare(openSource: () -> java.io.InputStream): GalleryExportReceipt {
        requireDirectory()
        val owned = directory.listFiles() ?: error("Export staging is unavailable.")
        val occupiedBytes = owned.filter { PAYLOAD.matches(it.name) }.sumOf { it.length() }
        check(occupiedBytes < MAX_PAYLOAD_TOTAL_BYTES)
        val id = UUID.randomUUID().toString()
        val file = payload(id)
        check(file.createNewFile())
        try {
            val digest = MessageDigest.getInstance("SHA-256")
            var length = 0L
            FileOutputStream(file).use { output ->
                openSource().use { input ->
                    val buffer = ByteArray(64 * 1024)
                    while (true) {
                        currentCoroutineContext().ensureActive()
                        val read = input.read(buffer)
                        if (read < 0) break
                        length += read
                        check(length <= GALLERY_EXPORT_MAX_BYTES) { "The export is too large." }
                        check(occupiedBytes + length <= MAX_PAYLOAD_TOTAL_BYTES) { "Unresolved export staging is full." }
                        output.write(buffer, 0, read)
                        digest.update(buffer, 0, read)
                    }
                }
                output.fd.sync()
            }
            check(length > 0)
            return GalleryExportReceipt(id, GalleryExportReceiptPhase.PREPARED, byteCount = length,
                sha256 = digest.digest().hex())
        } catch (error: Throwable) {
            file.delete()
            throw error
        }
    }

    fun payload(receipt: GalleryExportReceipt): File = payload(receipt.id).also(::requireRegular)

    fun removePayload(receipt: GalleryExportReceipt): Boolean {
        val file = payload(receipt.id)
        if (!exists(file)) return true
        requireRegular(file)
        return file.delete()
    }

    /** Only our UUID payloads in this private namespace; never a SAF destination scan. */
    fun removeUnreferencedPayloads(receipts: List<GalleryExportReceipt>): Boolean {
        val referenced = receipts.map { "${it.id}.payload" }.toSet()
        return (directory.listFiles() ?: return false).filter { PAYLOAD.matches(it.name) && it.name !in referenced }
            .map { file -> requireRegular(file); file.delete() }.all { it }
    }

    private fun payload(id: String): File {
        check(ID.matches(id))
        return File(directory, "$id.payload")
    }

    private fun requireDirectory() {
        check(directory.exists() || directory.mkdirs()) { "Export journal is unavailable." }
        check(Files.isDirectory(directory.toPath(), NOFOLLOW_LINKS)) { "Export journal is unavailable." }
    }

    private fun requireRegular(file: File) {
        check(Files.isRegularFile(file.toPath(), NOFOLLOW_LINKS)) { "Export journal is unsafe." }
    }

    private fun exists(file: File): Boolean = Files.exists(file.toPath(), NOFOLLOW_LINKS)

    private fun validUri(value: String?): Boolean = value != null && value.length <= 8192 &&
        android.net.Uri.parse(value).let { it.scheme == "content" && !it.authority.isNullOrBlank() }

    private companion object {
        val ID = Regex("[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
        val PAYLOAD = Regex("${ID.pattern}\\.payload")
        val HASH = Regex("[0-9a-f]{64}")
    }
}

internal fun ByteArray.hex(): String = joinToString("") { "%02x".format(it.toInt() and 255) }

private fun java.io.InputStream.readBytesLimited(limit: Int): ByteArray {
    val result = java.io.ByteArrayOutputStream()
    val buffer = ByteArray(8192)
    while (result.size() <= limit) {
        val count = read(buffer, 0, minOf(buffer.size, limit + 1 - result.size()))
        if (count < 0) break
        result.write(buffer, 0, count)
    }
    return result.toByteArray()
}
