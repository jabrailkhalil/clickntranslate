package dev.clickn.translate.ocr

import dev.clickn.translate.download.ModelFileDownloader
import java.io.File
import java.io.IOException
import java.io.InterruptedIOException
import java.security.MessageDigest
import java.util.Collections
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.async
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.launch
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withTimeout
import okhttp3.MediaType
import okhttp3.OkHttpClient
import okhttp3.Protocol
import okhttp3.Request
import okhttp3.Response
import okhttp3.ResponseBody
import okhttp3.ResponseBody.Companion.toResponseBody
import okio.Buffer
import okio.Source
import okio.Timeout
import okio.buffer
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder

class TesseractModelStoreTest {
    @get:Rule val folder = TemporaryFolder()
    private val bytes = mapOf("ara" to "arabic-model-v1".toByteArray(), "eng" to "english-model-v1".toByteArray())
    private val specs get() = bytes.map { (code, data) -> TesseractModelSpec(code, data.size.toLong(), digest(data), "https://models.invalid/$code.traineddata") }
    private fun digest(data: ByteArray) = MessageDigest.getInstance("SHA-256").digest(data).joinToString("") { "%02x".format(it) }
    private fun response(request: Request, data: ByteArray): Response = Response.Builder().request(request).protocol(Protocol.HTTP_1_1)
        .code(200).message("fixture").body(data.toResponseBody()).build()
    private fun fixture(handler: (Request) -> Response = { request -> response(request, bytes.getValue(request.url.pathSegments.last().substringBefore('.'))) }): Pair<TesseractModelStore, MutableList<Request>> {
        val requests = Collections.synchronizedList(mutableListOf<Request>())
        val client = OkHttpClient.Builder().addInterceptor { chain -> requests += chain.request(); handler(chain.request()) }.build()
        return TesseractModelStore(folder.newFolder(), ModelFileDownloader(client), specs) to requests
    }
    private suspend fun rejected(expected: TesseractModelFailure, action: suspend () -> Unit) {
        try { action(); fail("Expected $expected") } catch (error: TesseractModelException) { assertEquals(expected, error.failure) }
    }

    @Test fun missingModelsCannotAcquireALeaseOrCauseAnyNetworkRequest() = runBlocking {
        val (store, requests) = fixture()
        store.refresh()
        assertFalse(store.state.value.ready)
        assertEquals(TesseractModelFailure.MISSING, store.state.value.error)
        rejected(TesseractModelFailure.MISSING) { store.withOcrModels { fail("Missing models reached native init") } }
        assertTrue(requests.isEmpty())
    }

    @Test fun onlyTheCompleteVerifiedPairIsPublishedAndExplicitDownloadIsIdempotent() = runBlocking {
        val (store, requests) = fixture()
        store.download()
        assertEquals(TesseractModelState(ready = true), store.state.value)
        store.withOcrModels { path ->
            assertTrue(File(path).isDirectory)
            specs.forEach { assertArrayEquals(bytes.getValue(it.language), File(path, "tessdata/${it.language}.traineddata").readBytes()) }
        }
        store.refresh(); store.download()
        assertEquals(listOf("ara.traineddata", "eng.traineddata"), requests.map { it.url.pathSegments.last() })
    }

    @Test fun sameLengthCorruptionIsRejectedBeforeNativeUseAndCanBeDeletedAndDownloadedAgain() = runBlocking {
        val (store, requests) = fixture()
        store.download()
        store.withOcrModels { path -> File(path, "tessdata/ara.traineddata").writeBytes(ByteArray(bytes.getValue("ara").size)) }
        store.refresh()
        assertFalse(store.state.value.ready)
        assertEquals(TesseractModelFailure.INVALID, store.state.value.error)
        rejected(TesseractModelFailure.INVALID) { store.withOcrModels { fail("Corruption reached native init") } }
        assertEquals(2, requests.size)
        store.delete(); store.refresh()
        assertEquals(TesseractModelFailure.MISSING, store.state.value.error)
        store.download()
        assertTrue(store.state.value.ready)
        assertEquals(4, requests.size)
    }

    @Test fun aFailedSecondFileCannotPublishTheFirstAndExplicitRetryCanRecover() = runBlocking {
        var failEnglish = true
        val (store, _) = fixture { request ->
            val code = request.url.pathSegments.last().substringBefore('.')
            if (code == "eng" && failEnglish) throw IOException("private transport detail")
            response(request, bytes.getValue(code))
        }
        rejected(TesseractModelFailure.DOWNLOAD) { store.download() }
        assertFalse(store.state.value.ready); assertFalse(store.state.value.busy)
        assertTrue("Failed staging was retained", folder.root.walkTopDown().none { it.name.startsWith(".staging-") })
        rejected(TesseractModelFailure.MISSING) { store.withOcrModels { fail("Partial pair was published") } }
        failEnglish = false
        store.download()
        assertTrue(store.state.value.ready)
    }

    @Test fun wrongPinnedContentNeverBecomesReadyOrLeaksItsPrivateTransportCause() = runBlocking {
        val (store, _) = fixture { response(it, ByteArray(bytes.getValue("ara").size)) }
        rejected(TesseractModelFailure.INVALID) { store.download() }
        assertFalse(store.state.value.ready)
        assertEquals(TesseractModelFailure.INVALID, store.state.value.error)
    }

    @Test fun deletionWaitsUntilTheNativeModelLeaseHasDrained() = runBlocking {
        val (store, _) = fixture()
        store.download()
        val entered = CompletableDeferred<String>(); val release = CompletableDeferred<Unit>()
        val native = async { store.withOcrModels { entered.complete(it); release.await() } }
        val path = entered.await()
        val deletion = launch(start = CoroutineStart.UNDISPATCHED) { store.delete() }
        assertFalse(deletion.isCompleted)
        assertTrue(File(path, "tessdata/ara.traineddata").isFile)
        release.complete(Unit)
        native.await(); deletion.join()
        assertFalse(File(path).exists())
        assertFalse(store.state.value.ready)
    }

    @Test fun cancellationDuringAnActualBodyReadCleansStagingAndLeavesTheStoreReusable() = runBlocking {
        val entered = CountDownLatch(1); val drained = CountDownLatch(1)
        var blockRead = true
        val (store, _) = fixture { request ->
            if (!blockRead) response(request, bytes.getValue(request.url.pathSegments.last().substringBefore('.')))
            else Response.Builder().request(request).protocol(Protocol.HTTP_1_1).code(200).message("fixture")
                .body(object : ResponseBody() {
                    override fun contentType(): MediaType? = null
                    override fun contentLength() = bytes.getValue("ara").size.toLong()
                    override fun source() = object : Source {
                        override fun read(sink: Buffer, byteCount: Long): Long {
                            entered.countDown()
                            try { Thread.sleep(Long.MAX_VALUE) } catch (_: InterruptedException) { throw InterruptedIOException("cancelled fixture") }
                            finally { drained.countDown() }
                            return -1
                        }
                        override fun timeout() = Timeout.NONE
                        override fun close() = Unit
                    }.buffer()
                }).build()
        }
        val job = launch(Dispatchers.Default) { store.download() }
        assertTrue("The request never entered streamed body reading", entered.await(5, TimeUnit.SECONDS))
        withTimeout(5_000) { job.cancelAndJoin() }
        assertEquals(0L, drained.count)
        assertFalse(store.state.value.ready); assertFalse(store.state.value.busy)
        assertNull("Cancellation must not become a download error", store.state.value.error)
        assertTrue("Cancelled staging was retained", folder.root.walkTopDown().none { it.name.startsWith(".staging-") })
        blockRead = false
        store.download()
        assertTrue(store.state.value.ready)
    }

    @Test fun officialModelCatalogPinsBestArabicAndFastEnglishAtTheirOwnImmutableRevisions() {
        assertEquals(setOf("ara", "eng"), TesseractModelFiles.models.map { it.language }.toSet())
        assertEquals(listOf(12_603_724L, 4_113_088L), TesseractModelFiles.models.map { it.bytes })
        assertEquals(listOf("ab9d157d8e38ca00e7e39c7d5363a5239e053f5b0dbdb3167dde9d8124335896",
            "7d4322bd2a7749724879683fc3912cb542f19906c83bcc1a52132556427170b2"), TesseractModelFiles.models.map { it.sha256 })
        assertEquals(listOf("https://raw.githubusercontent.com/tesseract-ocr/tessdata_best/e12c65a915945e4c28e237a9b52bc4a8f39a0cec/ara.traineddata",
            "https://raw.githubusercontent.com/tesseract-ocr/tessdata_fast/65727574dfcd264acbb0c3e07860e4e9e9b22185/eng.traineddata"),
            TesseractModelFiles.models.map { it.url })
        assertEquals("ara-best-e12c65a91594_eng-fast-65727574dfcd", TesseractModelFiles.REVISION)
    }
}
