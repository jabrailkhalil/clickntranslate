package dev.clickn.translate.gallery

import android.content.Context
import android.net.Uri
import dagger.hilt.android.qualifiers.ApplicationContext
import java.io.File
import java.io.InputStream
import java.security.MessageDigest
import javax.inject.Inject
import javax.inject.Singleton
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext

/** Counts only: private destination URIs and translated content never enter UI diagnostics. */
data class GalleryExportRecoveryStatus(
    val pending: Int = 0,
    val unknownDestination: Int = 0,
    val terminalAwaitingCleanup: Int = 0,
    val journalAvailable: Boolean = true,
    val localCleanupPending: Boolean = false,
    /** Opaque snapshot of the records the user is acknowledging, never a destination/content hash. */
    val reviewToken: String? = null,
) {
    val reviewCount: Int get() = pending + unknownDestination
    val allClean: Boolean get() = journalAvailable && !localCleanupPending &&
        pending == 0 && unknownDestination == 0 && terminalAwaitingCleanup == 0
}

/** Recovery runs at startup and before the next explicit export, never on a polling timer. */
@Singleton
class GalleryExportReceipts @Inject constructor(@ApplicationContext context: Context) {
    private val recovery = GalleryExportReceiptRecovery(
        File(context.filesDir, "gallery-export-receipts-v1"),
        AndroidGalleryExportDocuments(context.contentResolver),
    )
    val status: StateFlow<GalleryExportRecoveryStatus> = recovery.status

    suspend fun recoverPending(): GalleryExportRecoveryStatus = recovery.recoverPending()

    /** Explicit user choice: keep all remote documents and forget only the displayed local records. */
    suspend fun keepFiles(reviewToken: String): GalleryExportRecoveryStatus = recovery.keepFiles(reviewToken)

    internal suspend fun exportFile(parent: Uri, mimeType: String, displayName: String, source: File) =
        recovery.export(parent, mimeType, displayName, source::inputStream)

    internal suspend fun exportText(parent: Uri, displayName: String, text: String) =
        recovery.export(parent, "text/plain", displayName) { text.byteInputStream(Charsets.UTF_8) }
}

/** One bounded journal, with a necessary private encoded source retained only while unresolved. */
internal class GalleryExportReceiptRecovery(
    private val store: GalleryExportReceiptStore,
    private val documents: GalleryExportDocuments,
) {
    constructor(directory: File, documents: GalleryExportDocuments) : this(GalleryExportReceiptStore(directory), documents)

    // Bounded by the journal's receipt limit. A transient disk failure need not discard a URI
    // already returned in this process. Process death before its durable bind remains unavoidable.
    private val knownBindings = mutableMapOf<String, GalleryExportReceipt>()
    private val mutableStatus = MutableStateFlow(GalleryExportRecoveryStatus(journalAvailable = false))
    val status: StateFlow<GalleryExportRecoveryStatus> = mutableStatus.asStateFlow()

    suspend fun recoverPending(): GalleryExportRecoveryStatus = withContext(Dispatchers.IO) {
        processMutex.withLock { recoverLocked() }
    }

    suspend fun keepFiles(expectedReviewToken: String): GalleryExportRecoveryStatus = withContext(Dispatchers.IO) {
        processMutex.withLock {
            val receipts = store.load()
            check(expectedReviewToken == reviewToken(receipts)) { "Export recovery changed. Check the current records first." }
            currentCoroutineContext().ensureActive()
            withContext(NonCancellable) {
                val retained = receipts.map { receipt ->
                    if (receipt.phase == GalleryExportReceiptPhase.PREPARED || receipt.phase == GalleryExportReceiptPhase.PENDING)
                        receipt.copy(phase = GalleryExportReceiptPhase.RETAINED) else receipt
                }
                // Persist the user's choice before any local source is removed. A restart must
                // never reopen/delete a destination after the user chose to leave its files.
                store.save(retained)
                retained.forEach { receipt ->
                    knownBindings.remove(receipt.id)
                    if (receipt.phase in TERMINAL_PHASES) forgetTerminal(receipt)
                }
                updateStatus()
            }
        }
    }

    suspend fun export(parent: Uri, mimeType: String, displayName: String, openSource: () -> InputStream) =
        withContext(Dispatchers.IO) {
            processMutex.withLock {
                var receipt: GalleryExportReceipt? = null
                var createAttempted = false
                val exportContext = currentCoroutineContext()
                try {
                    val previous = store.load()
                    check(previous.map { it.id }.containsAll(knownBindings.keys))
                    check(previous.size < GALLERY_EXPORT_MAX_RECEIPTS)
                    // The source and PREPARED marker exist before requesting any remote mutation.
                    val prepared = store.prepare(openSource)
                    receipt = prepared
                    store.save(previous + prepared)
                    exportContext.ensureActive()
                    withContext(NonCancellable) {
                        // Cancellation cannot discard a returned URI at a dispatcher hand-off.
                        exportContext.ensureActive()
                        createAttempted = true
                        val uri = checkNotNull(documents.create(parent, mimeType, displayName))
                        // Remote creation and local persistence cannot be atomic across providers.
                        // A process/disk failure here leaves PREPARED (unknown URI), never a guessed cleanup.
                        receipt = receipt!!.copy(phase = GalleryExportReceiptPhase.PENDING, uri = uri.toString())
                        knownBindings[receipt!!.id] = receipt!!
                        check(bindKnownDestination(receipt!!).phase == GalleryExportReceiptPhase.PENDING)
                    }
                    exportContext.ensureActive()
                    val bound = checkNotNull(receipt)
                    store.payload(bound).inputStream().use { input ->
                        checkNotNull(documents.openWrite(Uri.parse(checkNotNull(bound.uri)))).use { output ->
                            val buffer = ByteArray(64 * 1024)
                            while (true) {
                                exportContext.ensureActive()
                                val read = input.read(buffer)
                                if (read < 0) break
                                exportContext.ensureActive()
                                if (read > 0) output.write(buffer, 0, read)
                            }
                        }
                    }
                    // After a successful close, persist completion before cancellation/forgetting.
                    withContext(NonCancellable) {
                        val completed = bound.copy(phase = GalleryExportReceiptPhase.COMPLETE)
                        replace(completed)
                        forgetTerminal(completed)
                        updateStatus()
                    }
                } catch (error: Throwable) {
                    withContext(NonCancellable) {
                        runCatching {
                            val current = receipt
                            if (current != null && !createAttempted) {
                                // No remote call was made; only our local staging exists.
                                store.save(store.load().filterNot { it.id == current.id })
                                store.removePayload(current)
                            } else if (current?.phase == GalleryExportReceiptPhase.PENDING) {
                                bindKnownDestination(current)
                                // Read the durable state: a failed COMPLETE commit must not downgrade it.
                                store.load().find { it.id == current.id }?.let { recoverOne(it) }
                            }
                        }
                        updateStatus()
                    }
                    if (error is CancellationException) throw error
                    // Provider exceptions can contain private URIs/names. Do not propagate their cause.
                    throw GalleryExportWriteException()
                }
                Unit
            }
        }

    private suspend fun recoverLocked(): GalleryExportRecoveryStatus {
        for (receipt in knownBindings.values.toList()) {
            currentCoroutineContext().ensureActive()
            try { bindKnownDestination(receipt) }
            catch (_: Exception) { /* Keep the known URI in memory for a later explicit recovery. */ }
        }
        val receipts = try { store.load() } catch (_: Exception) {
            return unavailable()
        }
        val cursor = try { store.lastExaminedId() } catch (_: Exception) {
            return unavailable()
        }
        val pending = receipts.filter { it.phase == GalleryExportReceiptPhase.PENDING }.sortedBy { it.id }
        val orderedPending = if (cursor == null) pending else
            pending.filter { it.id > cursor } + pending.filter { it.id <= cursor }
        val localOnly = receipts.filter { it.phase != GalleryExportReceiptPhase.PENDING }
        var examined = 0
        var estimatedBytes = 0L
        for (receipt in localOnly + orderedPending) {
            currentCoroutineContext().ensureActive()
            if (receipt.phase == GalleryExportReceiptPhase.PENDING) {
                val cost = receipt.byteCount * 3 // source hash plus one source/remote comparison.
                // Stop here: skipping a large entry in favour of later small ones could starve it.
                if (examined >= MAX_RECOVERY_DOCUMENTS || estimatedBytes + cost > MAX_RECOVERY_BYTES) break
                examined++
                estimatedBytes += cost
                // Commit before a potentially blocking provider call, including one that crashes.
                try { store.advanceCursor(receipt.id) } catch (_: Exception) { return unavailable() }
            }
            try {
                recoverOne(receipt)
            } catch (cancellation: CancellationException) {
                throw cancellation
            } catch (_: Exception) {
                // Lost grants, changed documents and local I/O errors retain the exact receipt.
            }
        }
        return updateStatus()
    }

    private suspend fun recoverOne(receipt: GalleryExportReceipt) {
        when (receipt.phase) {
            GalleryExportReceiptPhase.PREPARED -> Unit // URI unknown: never guess by filename.
            GalleryExportReceiptPhase.COMPLETE, GalleryExportReceiptPhase.DELETED,
            GalleryExportReceiptPhase.RETAINED -> forgetTerminal(receipt)
            GalleryExportReceiptPhase.PENDING -> {
                val proof = galleryExportDocumentProof(receipt, store, documents)
                when (proof.kind) {
                    GalleryExportProofKind.COMPLETE -> {
                        val completed = receipt.copy(phase = GalleryExportReceiptPhase.COMPLETE)
                        replace(completed)
                        forgetTerminal(completed)
                    }
                    // Even an exact prefix is not exclusive ownership: an external editor may
                    // change it immediately after our read. SAF has no atomic compare-and-delete.
                    // Preserve it until completion is proven or the user acknowledges local records.
                    GalleryExportProofKind.PREFIX -> Unit
                    GalleryExportProofKind.UNCERTAIN -> Unit
                }
            }
        }
    }

    private fun replace(receipt: GalleryExportReceipt) {
        val current = store.load()
        check(current.any { it.id == receipt.id })
        store.save(current.map { if (it.id == receipt.id) receipt else it })
    }

    private fun bindKnownDestination(receipt: GalleryExportReceipt): GalleryExportReceipt {
        val receipts = store.load()
        val durable = checkNotNull(receipts.find { it.id == receipt.id })
        check(durable.sha256 == receipt.sha256 && durable.byteCount == receipt.byteCount)
        when (durable.phase) {
            GalleryExportReceiptPhase.PREPARED -> store.save(receipts.map { if (it.id == receipt.id) receipt else it })
            GalleryExportReceiptPhase.PENDING -> check(durable.uri == receipt.uri)
            else -> Unit // A committed terminal marker must never be downgraded.
        }
        knownBindings.remove(receipt.id)
        return if (durable.phase == GalleryExportReceiptPhase.PREPARED) receipt else durable
    }

    private fun forgetTerminal(receipt: GalleryExportReceipt) {
        check(receipt.phase in TERMINAL_PHASES)
        // Keep the terminal marker until its source is removed; future recovery never reopens the URI.
        if (store.removePayload(receipt)) store.save(store.load().filterNot { it.id == receipt.id })
    }

    private fun updateStatus(): GalleryExportRecoveryStatus = try {
        val receipts = store.load()
        check(receipts.map { it.id }.containsAll(knownBindings.keys))
        val clean = store.removeUnreferencedPayloads(receipts)
        GalleryExportRecoveryStatus(
            pending = receipts.count { it.phase == GalleryExportReceiptPhase.PENDING },
            unknownDestination = receipts.count { it.phase == GalleryExportReceiptPhase.PREPARED },
            terminalAwaitingCleanup = receipts.count {
                it.phase in TERMINAL_PHASES
            },
            localCleanupPending = !clean,
            reviewToken = reviewToken(receipts),
        ).also { mutableStatus.value = it }
    } catch (_: Exception) {
        unavailable()
    }

    private fun unavailable(): GalleryExportRecoveryStatus =
        GalleryExportRecoveryStatus(journalAvailable = false).also { mutableStatus.value = it }

    private fun reviewToken(receipts: List<GalleryExportReceipt>): String? {
        val review = receipts.filter { it.phase == GalleryExportReceiptPhase.PREPARED || it.phase == GalleryExportReceiptPhase.PENDING }
        if (review.isEmpty()) return null
        val snapshot = review.sortedBy { it.id }.joinToString("\n") { "${it.id}:${it.phase}" }
        return MessageDigest.getInstance("SHA-256").digest(snapshot.toByteArray(Charsets.UTF_8)).hex()
    }

    private companion object {
        // Also serializes independently created startup/export helpers in this process.
        val processMutex = Mutex()
        const val MAX_RECOVERY_DOCUMENTS = 8
        const val MAX_RECOVERY_BYTES = 384L * 1024 * 1024
        val TERMINAL_PHASES = setOf(GalleryExportReceiptPhase.COMPLETE, GalleryExportReceiptPhase.DELETED,
            GalleryExportReceiptPhase.RETAINED)
    }
}

internal class GalleryExportWriteException : java.io.IOException("The document could not be exported. Unresolved output is retained for safe recovery.")
