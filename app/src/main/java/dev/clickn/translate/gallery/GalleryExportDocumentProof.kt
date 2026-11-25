package dev.clickn.translate.gallery

import android.content.ContentResolver
import android.net.Uri
import android.provider.DocumentsContract
import java.io.InputStream
import java.io.OutputStream
import java.security.MessageDigest
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.ensureActive

internal interface GalleryExportDocuments {
    fun create(parent: Uri, mimeType: String, displayName: String): Uri?
    fun openRead(uri: Uri): InputStream?
    fun openWrite(uri: Uri): OutputStream?
    fun delete(uri: Uri): Boolean
}

internal class AndroidGalleryExportDocuments(private val resolver: ContentResolver) : GalleryExportDocuments {
    override fun create(parent: Uri, mimeType: String, displayName: String): Uri? =
        DocumentsContract.createDocument(resolver, parent, mimeType, displayName)
    override fun openRead(uri: Uri): InputStream? = resolver.openInputStream(uri)
    override fun openWrite(uri: Uri): OutputStream? = resolver.openOutputStream(uri, "w")
    override fun delete(uri: Uri): Boolean = DocumentsContract.deleteDocument(resolver, uri)
}

internal enum class GalleryExportProofKind { COMPLETE, PREFIX, UNCERTAIN }
internal data class GalleryExportProof(val kind: GalleryExportProofKind, val length: Long = 0, val hash: String = "")

/** Source equality, not URI possession, is the evidence used by recovery. Empty files are uncertain. */
internal suspend fun galleryExportDocumentProof(
    receipt: GalleryExportReceipt,
    store: GalleryExportReceiptStore,
    documents: GalleryExportDocuments,
): GalleryExportProof {
    val source = store.payload(receipt)
    val sourceHash = MessageDigest.getInstance("SHA-256")
    var sourceLength = 0L
    source.inputStream().use { input ->
        val buffer = ByteArray(64 * 1024)
        while (true) {
            currentCoroutineContext().ensureActive()
            val read = input.read(buffer)
            if (read < 0) break
            sourceLength += read
            if (sourceLength > receipt.byteCount) return GalleryExportProof(GalleryExportProofKind.UNCERTAIN)
            sourceHash.update(buffer, 0, read)
        }
    }
    if (sourceLength != receipt.byteCount || sourceHash.digest().hex() != receipt.sha256) {
        return GalleryExportProof(GalleryExportProofKind.UNCERTAIN)
    }
    val remoteHash = MessageDigest.getInstance("SHA-256")
    var remoteLength = 0L
    val remote = documents.openRead(Uri.parse(requireNotNull(receipt.uri)))
        ?: return GalleryExportProof(GalleryExportProofKind.UNCERTAIN)
    remote.use { input ->
        source.inputStream().use { expected ->
            val buffer = ByteArray(64 * 1024)
            val sourceBuffer = ByteArray(buffer.size)
            while (true) {
                currentCoroutineContext().ensureActive()
                val read = input.read(buffer)
                if (read < 0) break
                if (read == 0) continue
                remoteLength += read
                if (remoteLength > receipt.byteCount) return GalleryExportProof(GalleryExportProofKind.UNCERTAIN)
                var offset = 0
                while (offset < read) {
                    val count = expected.read(sourceBuffer, offset, read - offset)
                    if (count <= 0) return GalleryExportProof(GalleryExportProofKind.UNCERTAIN)
                    offset += count
                }
                for (index in 0 until read) {
                    if (buffer[index] != sourceBuffer[index]) return GalleryExportProof(GalleryExportProofKind.UNCERTAIN)
                }
                remoteHash.update(buffer, 0, read)
            }
        }
    }
    val kind = when {
        remoteLength == receipt.byteCount -> GalleryExportProofKind.COMPLETE
        remoteLength > 0 -> GalleryExportProofKind.PREFIX
        else -> GalleryExportProofKind.UNCERTAIN
    }
    return GalleryExportProof(kind, remoteLength, remoteHash.digest().hex())
}
