package dev.clickn.translate.gallery

import android.net.Uri
import android.util.AtomicFile
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import java.io.ByteArrayOutputStream
import java.io.File
import java.io.FileOutputStream
import java.io.IOException
import java.io.InputStream
import java.io.OutputStream
import java.nio.file.Files
import java.util.UUID
import kotlinx.coroutines.cancel
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.launch
import kotlinx.coroutines.runBlocking
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith

/** Real AtomicFile/private files; controlled document operations isolate recovery failure boundaries. */
@RunWith(AndroidJUnit4::class)
class GalleryExportReceiptsIntegrationTest {
    @Test fun successfulWriteBindsBeforeOpenAndNeverRevisitsFinishedOutput() = runBlocking {
        owned { fixture ->
            fixture.documents.onOpenWrite = {
                val receipt = fixture.store.load().single()
                assertEquals(GalleryExportReceiptPhase.PENDING, receipt.phase)
                assertEquals(fixture.documents.created.single().toString(), receipt.uri)
                assertFalse(receipt.toString().contains("content://"))
            }
            fixture.export()
            val output = fixture.documents.created.single()
            assertArrayEquals(SOURCE, fixture.documents.bytes.getValue(output))
            assertTrue(fixture.store.load().isEmpty())
            fixture.documents.bytes[output] = "user edited a completed export".toByteArray()
            repeat(2) { assertTrue(fixture.reopen().recoverPending().allClean) }
            assertTrue(fixture.documents.reads.isEmpty())
            assertTrue(fixture.documents.deletes.isEmpty())
        }
    }

    @Test fun exactPrefixAndSameNamedOtherDocumentAreRetainedWithoutCheckDeleteRace() = runBlocking {
        owned { fixture ->
            val receipt = fixture.seed(SOURCE.copyOfRange(0, 19))
            val unrelated = Uri.parse("content://owned.fixture/document/other-same-name")
            fixture.documents.bytes[unrelated] = SOURCE.copyOfRange(0, 19)
            assertEquals(1, fixture.reopen().recoverPending().pending)
            val exact = Uri.parse(receipt.uri)
            assertEquals(listOf(exact), fixture.documents.reads)
            assertTrue(fixture.documents.deletes.isEmpty())
            assertArrayEquals(SOURCE.copyOfRange(0, 19), fixture.documents.bytes[exact])
            assertArrayEquals(SOURCE.copyOfRange(0, 19), fixture.documents.bytes[unrelated])
            fixture.documents.bytes[exact] = "User edited the partial export after our read".toByteArray()
            repeat(2) { assertFalse(fixture.reopen().recoverPending().allClean) }
            assertTrue(fixture.documents.deletes.isEmpty())
            assertEquals(listOf(receipt), fixture.store.load())
        }
    }

    @Test fun explicitKeepForKnownAndUnknownDestinationsRemovesOnlyLocalRecoveryData() = runBlocking {
        owned { fixture ->
            val known = fixture.seed(SOURCE.copyOfRange(0, 11))
            val unknown = fixture.store.prepare { SOURCE.inputStream() }
            fixture.store.save(listOf(known, unknown))
            val engine = fixture.reopen()
            val status = engine.recoverPending()
            assertEquals(2, status.reviewCount)
            val reads = fixture.documents.reads.size
            assertTrue(engine.keepFiles(checkNotNull(status.reviewToken)).allClean)
            assertTrue(fixture.store.load().isEmpty())
            assertFalse(File(fixture.directory, "${known.id}.payload").exists())
            assertFalse(File(fixture.directory, "${unknown.id}.payload").exists())
            assertEquals(reads, fixture.documents.reads.size)
            assertTrue(fixture.documents.deletes.isEmpty())
            assertArrayEquals(SOURCE.copyOfRange(0, 11), fixture.documents.bytes[Uri.parse(known.uri)])
            assertTrue(fixture.reopen().recoverPending().allClean)
        }
    }

    @Test fun fullyWrittenPendingDocumentIsPreservedAndCompletionSurvivesLaterEdits() = runBlocking {
        owned { fixture ->
            val receipt = fixture.seed(SOURCE)
            assertTrue(fixture.reopen().recoverPending().allClean)
            assertTrue(fixture.documents.deletes.isEmpty())
            fixture.documents.bytes[Uri.parse(receipt.uri)] = byteArrayOf(1, 2, 3)
            val reads = fixture.documents.reads.size
            assertTrue(fixture.reopen().recoverPending().allClean)
            assertEquals(reads, fixture.documents.reads.size)
            assertTrue(fixture.documents.deletes.isEmpty())
        }
    }

    @Test fun foreignEmptyAndPartialOutputsRemainUnresolved() = runBlocking {
        for (remote in listOf(byteArrayOf(), "foreign content".toByteArray(), SOURCE.copyOfRange(0, 7))) {
            owned { fixture ->
                fixture.seed(remote)
                val status = fixture.reopen().recoverPending()
                assertFalse(status.allClean)
                assertEquals(1, status.pending)
                assertTrue(fixture.documents.deletes.isEmpty())
                assertEquals(1, fixture.store.load().size)
            }
        }
    }

    @Test fun revokedReadGrantAndMissingOrTamperedSourceNeverAuthorizeDeletion() = runBlocking {
        repeat(3) { mode ->
            owned { fixture ->
                val receipt = fixture.seed(SOURCE.copyOfRange(0, 8))
                when (mode) {
                    0 -> fixture.documents.readError = SecurityException("private grant detail")
                    1 -> fixture.store.payload(receipt).delete()
                    else -> fixture.store.payload(receipt).writeBytes("changed source".toByteArray())
                }
                val status = fixture.reopen().recoverPending()
                assertFalse(status.allClean)
                assertTrue(fixture.documents.deletes.isEmpty())
                assertEquals(1, fixture.store.load().size)
            }
        }
    }

    @Test fun preparedUnknownUriAndCorruptJournalArePreservedWithoutProviderCalls() = runBlocking {
        owned { fixture ->
            val prepared = fixture.store.prepare { SOURCE.inputStream() }
            fixture.store.save(listOf(prepared))
            val status = fixture.reopen().recoverPending()
            assertFalse(status.allClean)
            assertEquals(1, status.unknownDestination)
            assertTrue(fixture.documents.reads.isEmpty())
            val journal = File(fixture.directory, "receipts.json")
            journal.writeText("{corrupt owned journal")
            val before = journal.readBytes()
            assertFalse(fixture.reopen().recoverPending().journalAvailable)
            assertArrayEquals(before, journal.readBytes())
            assertTrue(fixture.store.payload(prepared).exists())
            assertTrue(fixture.documents.deletes.isEmpty())
        }
    }

    @Test fun durableTerminalMarkersNeverReadOrDeleteRemoteDocuments() = runBlocking {
        for (phase in listOf(GalleryExportReceiptPhase.COMPLETE, GalleryExportReceiptPhase.DELETED, GalleryExportReceiptPhase.RETAINED)) {
            owned { fixture ->
                val pending = fixture.seed("user changed output".toByteArray())
                fixture.store.save(listOf(pending.copy(phase = phase)))
                assertTrue(fixture.reopen().recoverPending().allClean)
                assertTrue(fixture.documents.reads.isEmpty())
                assertTrue(fixture.documents.deletes.isEmpty())
            }
        }
    }

    @Test fun cancellationAfterCreateDurablyBindsEmptyOutputAndDoesNotBlindlyDeleteIt() = runBlocking {
        owned { fixture ->
            coroutineScope {
                val job = launch {
                    val caller = coroutineContext
                    fixture.documents.onCreate = { caller.cancel() }
                    fixture.export()
                }
                job.join()
                assertTrue(job.isCancelled)
            }
            val receipt = fixture.store.load().single()
            assertEquals(GalleryExportReceiptPhase.PENDING, receipt.phase)
            assertEquals(fixture.documents.created.single().toString(), receipt.uri)
            assertTrue(fixture.documents.deletes.isEmpty())
            assertFalse(fixture.reopen().recoverPending().allClean)
        }
    }

    @Test fun cancellationDuringPrivatePreparationCreatesNoRemoteDocument() = runBlocking {
        owned { fixture ->
            coroutineScope {
                val job = launch {
                    val caller = coroutineContext
                    fixture.reopen().export(PARENT, "text/plain", "owned.txt") {
                        caller.cancel()
                        SOURCE.inputStream()
                    }
                }
                job.join()
                assertTrue(job.isCancelled)
            }
            assertTrue(fixture.documents.created.isEmpty())
            assertTrue(fixture.store.load().isEmpty())
            assertTrue(fixture.reopen().recoverPending().allClean)
        }
    }

    @Test fun transientBindFailurePersistsTheReturnedUriBeforeLosingTheExportCall() = runBlocking {
        owned { fixture ->
            val atomic = FailingJournal(File(fixture.directory, "receipts.json"))
            val store = GalleryExportReceiptStore(fixture.directory, atomic)
            val engine = GalleryExportReceiptRecovery(store, fixture.documents)
            fixture.documents.onCreate = { atomic.failWrites = 1 }
            try {
                engine.export(PARENT, "text/plain", "owned.txt") { SOURCE.inputStream() }
                fail("Expected bind failure")
            } catch (_: GalleryExportWriteException) { }
            val receipt = store.load().single()
            assertEquals(GalleryExportReceiptPhase.PENDING, receipt.phase)
            assertEquals(fixture.documents.created.single().toString(), receipt.uri)
            assertTrue(store.payload(receipt).exists())
            assertEquals(1, engine.status.value.pending)
            assertEquals(0, engine.status.value.unknownDestination)
            assertTrue(fixture.documents.writes.isEmpty())
            assertTrue(fixture.documents.deletes.isEmpty())
        }
    }

    @Test fun knownUriSurvivesTwoDiskFailuresForALaterRecoveryWithinTheSameProcess() = runBlocking {
        owned { fixture ->
            val atomic = FailingJournal(File(fixture.directory, "receipts.json"))
            val store = GalleryExportReceiptStore(fixture.directory, atomic)
            val engine = GalleryExportReceiptRecovery(store, fixture.documents)
            fixture.documents.onCreate = { atomic.failWrites = 2 }
            try {
                engine.export(PARENT, "text/plain", "owned.txt") { SOURCE.inputStream() }
                fail("Expected persistent bind failure")
            } catch (_: GalleryExportWriteException) { }
            assertEquals(GalleryExportReceiptPhase.PREPARED, store.load().single().phase)
            assertEquals(1, engine.status.value.unknownDestination)
            val afterRetry = engine.recoverPending()
            assertEquals(0, afterRetry.unknownDestination)
            assertEquals(1, afterRetry.pending)
            assertEquals(fixture.documents.created.single().toString(), store.load().single().uri)
            assertEquals(1, fixture.documents.created.size)
            assertTrue(fixture.documents.writes.isEmpty())
            assertTrue(fixture.documents.deletes.isEmpty())
        }
    }

    @Test fun keepCannotAcknowledgeExportsCreatedAfterTheDisplayedSnapshot() = runBlocking {
        owned { fixture ->
            fixture.seed(SOURCE.copyOfRange(0, 5))
            val engine = fixture.reopen()
            val displayed = checkNotNull(engine.recoverPending().reviewToken)
            val previous = fixture.store.load()
            val newer = fixture.store.prepare { SOURCE.inputStream() }
            fixture.store.save(previous + newer)
            try {
                engine.keepFiles(displayed)
                fail("A stale confirmation must not clear a new export")
            } catch (_: IllegalStateException) { }
            assertEquals(previous + newer, fixture.store.load())
            assertTrue(fixture.store.load().all { fixture.store.payload(it).exists() })
            assertTrue(fixture.documents.deletes.isEmpty())
        }
    }

    @Test fun failedKeepCommitPreservesTheReceiptAndPrivateSource() = runBlocking {
        owned { fixture ->
            val receipt = fixture.seed(SOURCE.copyOfRange(0, 6))
            val atomic = FailingJournal(File(fixture.directory, "receipts.json"))
            val store = GalleryExportReceiptStore(fixture.directory, atomic)
            val engine = GalleryExportReceiptRecovery(store, fixture.documents)
            val token = checkNotNull(engine.recoverPending().reviewToken)
            atomic.failWrites = 1
            try {
                engine.keepFiles(token)
                fail("Expected journal failure")
            } catch (_: IOException) { }
            assertEquals(listOf(receipt), store.load())
            assertTrue(store.payload(receipt).exists())
            assertTrue(fixture.documents.deletes.isEmpty())
            assertArrayEquals(SOURCE.copyOfRange(0, 6), fixture.documents.bytes[Uri.parse(receipt.uri)])
        }
    }

    @Test fun recoveryDefersBeyondItsDocumentBudgetWithoutClaimingAllClean() = runBlocking {
        owned { fixture ->
            val receipts = (1..9).map {
                val source = fixture.store.prepare { SOURCE.inputStream() }
                val uri = fixture.documents.create(PARENT, "text/plain", "owned.txt")
                fixture.documents.bytes[uri] = SOURCE
                source.copy(phase = GalleryExportReceiptPhase.PENDING, uri = uri.toString())
            }
            fixture.store.save(receipts)
            val first = fixture.reopen().recoverPending()
            assertFalse(first.allClean)
            assertEquals(1, first.pending)
            assertEquals(8, fixture.documents.reads.size)
            assertTrue(fixture.reopen().recoverPending().allClean)
            assertEquals(9, fixture.documents.reads.size)
            assertEquals(9, fixture.documents.bytes.size)
            assertTrue(fixture.documents.deletes.isEmpty())
        }
    }

    @Test fun durableCursorAdvancesPastUncertainEntriesWithinEachRecoveryBudget() = runBlocking {
        owned { fixture ->
            val receipts = (1..12).map {
                val source = fixture.store.prepare { SOURCE.inputStream() }
                val uri = fixture.documents.create(PARENT, "text/plain", "owned.txt") // Empty = uncertain.
                source.copy(phase = GalleryExportReceiptPhase.PENDING, uri = uri.toString())
            }
            fixture.store.save(receipts)
            fixture.documents.onRead = {
                val exact = fixture.documents.reads.last().toString()
                assertEquals(receipts.single { it.uri == exact }.id, fixture.store.lastExaminedId())
            }
            val sorted = receipts.sortedBy { it.id }
            val first = fixture.reopen().recoverPending()
            assertFalse(first.allClean)
            assertEquals(12, first.pending)
            assertEquals(sorted.take(8).map { Uri.parse(it.uri) }, fixture.documents.reads)
            val second = fixture.reopen().recoverPending() // New engine must reload the durable cursor.
            assertFalse(second.allClean)
            assertEquals(12, second.pending)
            assertEquals(sorted.drop(8).map { Uri.parse(it.uri) }, fixture.documents.reads.drop(8).take(4))
            assertEquals(16, fixture.documents.reads.size)
            assertEquals(12, fixture.documents.reads.distinct().size)
            assertTrue(fixture.documents.deletes.isEmpty())
            assertEquals(receipts, fixture.store.load())
        }
    }

    @Test fun cancellationMidWriteKeepsPartialFileAndCancellationAfterCloseKeepsFullFile() = runBlocking {
        for (cancelAfterClose in listOf(false, true)) {
            owned { fixture ->
                coroutineScope {
                    val job = launch {
                        val caller = coroutineContext
                        if (cancelAfterClose) fixture.documents.onClose = { caller.cancel() }
                        else fixture.documents.onWrite = { caller.cancel() }
                        fixture.export(ByteArray(128 * 1024) { (it % 251).toByte() })
                    }
                    job.join()
                    assertTrue(job.isCancelled)
                }
                if (cancelAfterClose) {
                    assertTrue(fixture.store.load().isEmpty())
                    assertEquals(128 * 1024, fixture.documents.bytes.values.single().size)
                    assertTrue(fixture.documents.deletes.isEmpty())
                } else {
                    assertEquals(64 * 1024, fixture.documents.bytes.values.single().size)
                    assertEquals(GalleryExportReceiptPhase.PENDING, fixture.store.load().single().phase)
                    assertEquals(1, fixture.reopen().recoverPending().pending)
                    assertTrue(fixture.documents.deletes.isEmpty())
                }
            }
        }
    }

    @Test fun providerWriteFailureRetainsPartialOutputUntilCompletedAndRedactsProviderException() = runBlocking {
        owned { fixture ->
            fixture.documents.failAfterPrefix = true
            try {
                fixture.export()
                fail("Expected export failure")
            } catch (error: GalleryExportWriteException) {
                assertNull(error.cause)
                assertFalse(error.toString().contains("content://"))
                assertFalse(error.toString().contains("private provider detail"))
            }
            assertEquals(1, fixture.store.load().size)
            assertFalse(fixture.reopen().recoverPending().allClean)
            assertTrue(fixture.documents.deletes.isEmpty())
            fixture.documents.bytes[fixture.documents.created.single()] = SOURCE
            assertTrue(fixture.reopen().recoverPending().allClean)
        }
    }

    @Test(timeout = 30_000) fun realContentResolverDocumentsProviderSupportsExactPngAndUtf8Outputs() = runBlocking {
        val target = InstrumentationRegistry.getInstrumentation().targetContext
        val resolver = target.contentResolver
        val provider = GalleryExportDocumentsFixture
        val parent = provider.parentUri()
        val exported = mutableListOf<Uri>()
        owned { fixture ->
            val actual = AndroidGalleryExportDocuments(resolver)
            val operations = object : GalleryExportDocuments by actual {
                override fun create(parent: Uri, mimeType: String, displayName: String): Uri? =
                    actual.create(parent, mimeType, displayName)?.also { exported += it }
            }
            val engine = GalleryExportReceiptRecovery(fixture.directory, operations)
            try {
                val png = android.graphics.Bitmap.createBitmap(3, 2, android.graphics.Bitmap.Config.ARGB_8888)
                val encoded = ByteArrayOutputStream()
                try { assertTrue(png.compress(android.graphics.Bitmap.CompressFormat.PNG, 100, encoded)) }
                finally { png.recycle() }
                val text = "Two paragraphs.\n\nالعربية и русский.".toByteArray(Charsets.UTF_8)
                engine.export(parent, "image/png", "owned-${UUID.randomUUID()}.png") { encoded.toByteArray().inputStream() }
                engine.export(parent, "text/plain", "owned-${UUID.randomUUID()}.txt") { text.inputStream() }
                assertArrayEquals(encoded.toByteArray(), resolver.openInputStream(exported[0])!!.use { it.readBytes() })
                assertArrayEquals(text, resolver.openInputStream(exported[1])!!.use { it.readBytes() })
                assertTrue(engine.recoverPending().allClean)
                assertTrue(fixture.store.load().isEmpty())
            } finally {
                try { exported.forEach { assertTrue(actual.delete(it)) } }
                finally { provider.revoke(parent) }
            }
        }
    }

    @Test(timeout = 30_000) fun realProviderRegrantKeepsPartialOutputAndExplicitKeepClearsLocalReceiptOnly() = runBlocking {
        val target = InstrumentationRegistry.getInstrumentation().targetContext
        val provider = GalleryExportDocumentsFixture
        val actual = AndroidGalleryExportDocuments(target.contentResolver)
        val parent = provider.parentUri()
        var created: Uri? = null
        try {
            owned { fixture ->
                val source = fixture.store.prepare { SOURCE.inputStream() }
                val uri = checkNotNull(actual.create(parent, "text/plain", "owned-${UUID.randomUUID()}.txt"))
                created = uri
                val receipt = source.copy(phase = GalleryExportReceiptPhase.PENDING, uri = uri.toString())
                fixture.store.save(listOf(receipt))
                checkNotNull(actual.openWrite(uri)).use { it.write(SOURCE, 0, 13) }
                provider.revoke(parent)
                val recovery = GalleryExportReceiptRecovery(fixture.directory, actual)
                assertFalse(recovery.recoverPending().allClean)
                assertEquals(listOf(receipt), fixture.store.load())
                assertEquals(parent, provider.parentUri()) // Exact fixture tree grant restored by its owner.
                val retained = recovery.recoverPending()
                assertFalse(retained.allClean)
                assertArrayEquals(SOURCE.copyOfRange(0, 13), actual.openRead(uri)!!.use { it.readBytes() })
                assertTrue(recovery.keepFiles(checkNotNull(retained.reviewToken)).allClean)
                assertTrue(fixture.store.load().isEmpty())
                assertTrue(recovery.recoverPending().allClean)
                assertArrayEquals(SOURCE.copyOfRange(0, 13), actual.openRead(uri)!!.use { it.readBytes() })
            }
        } finally {
            try {
                provider.parentUri()
                created?.let { actual.delete(it) }
            } finally { provider.revoke(parent) }
        }
    }

    private suspend fun owned(block: suspend (Fixture) -> Unit) {
        val parent = InstrumentationRegistry.getInstrumentation().targetContext.filesDir
        val directory = File(parent, "gallery-export-receipts-test-${UUID.randomUUID()}")
        check(directory.mkdir())
        try { block(Fixture(directory)) } finally {
            // Only a freshly created private test subtree, never provider destinations or user folders.
            check(directory.canonicalFile.parentFile == parent.canonicalFile)
            Files.walk(directory.toPath()).use { paths ->
                paths.sorted(Comparator.reverseOrder()).forEach { Files.deleteIfExists(it) }
            }
        }
    }

    private class Fixture(val directory: File) {
        val documents = OwnedDocuments()
        val store = GalleryExportReceiptStore(directory)
        fun reopen() = GalleryExportReceiptRecovery(directory, documents)
        suspend fun export(bytes: ByteArray = SOURCE) = reopen().export(PARENT, "image/png", "owned.png") { bytes.inputStream() }
        suspend fun seed(remote: ByteArray): GalleryExportReceipt {
            val source = store.prepare { SOURCE.inputStream() }
            val uri = checkNotNull(documents.create(PARENT, "image/png", "owned.png"))
            documents.bytes[uri] = remote
            return source.copy(phase = GalleryExportReceiptPhase.PENDING, uri = uri.toString()).also {
                store.save(listOf(it))
            }
        }
    }

    private class OwnedDocuments : GalleryExportDocuments {
        val bytes = linkedMapOf<Uri, ByteArray>()
        val created = mutableListOf<Uri>()
        val reads = mutableListOf<Uri>()
        val writes = mutableListOf<Uri>()
        val deletes = mutableListOf<Uri>()
        var onCreate: (() -> Unit)? = null
        var onOpenWrite: (() -> Unit)? = null
        var onWrite: (() -> Unit)? = null
        var onClose: (() -> Unit)? = null
        var onRead: ((Int) -> Unit)? = null
        var readError: Exception? = null
        var failAfterPrefix = false
        override fun create(parent: Uri, mimeType: String, displayName: String): Uri =
            Uri.parse("content://owned.fixture/document/${UUID.randomUUID()}").also {
                bytes[it] = byteArrayOf(); created += it; onCreate?.invoke()
            }
        override fun openRead(uri: Uri): InputStream {
            reads += uri
            readError?.let { throw it }
            onRead?.invoke(reads.size)
            return bytes.getValue(uri).inputStream()
        }
        override fun openWrite(uri: Uri): OutputStream {
            writes += uri
            onOpenWrite?.invoke()
            return object : ByteArrayOutputStream() {
                override fun write(buffer: ByteArray, offset: Int, length: Int) {
                    super.write(buffer, offset, if (failAfterPrefix) minOf(7, length) else length)
                    bytes[uri] = toByteArray()
                    onWrite?.invoke()
                    if (failAfterPrefix) throw IOException("private provider detail content://secret/output")
                }
                override fun close() { super.close(); onClose?.invoke() }
            }
        }
        override fun delete(uri: Uri): Boolean {
            deletes += uri
            bytes.remove(uri)
            return true
        }
    }

    /** Real AtomicFile except for bounded disk-write failures at a provider-controlled boundary. */
    private class FailingJournal(path: File) : AtomicFile(path) {
        var failWrites = 0
        override fun startWrite(): FileOutputStream {
            if (failWrites > 0) {
                failWrites--
                throw IOException("Owned fixture disk write unavailable")
            }
            return super.startWrite()
        }
    }

    private companion object {
        val SOURCE = "A complete owned fixture.\n\nВторой абзац عربي.".toByteArray(Charsets.UTF_8)
        val PARENT = Uri.parse("content://owned.fixture/tree/owned/document/owned")
    }
}
