package dev.clickn.translate.dictionary

import android.content.ContentProvider
import android.content.ContentResolver
import android.content.ContentValues
import android.content.Context
import android.content.ContextWrapper
import android.content.res.AssetFileDescriptor
import android.database.Cursor
import android.net.Uri
import android.os.ParcelFileDescriptor
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.filters.SdkSuppress
import androidx.test.platform.app.InstrumentationRegistry
import dev.clickn.translate.translate.WordSense
import java.io.Closeable
import java.io.File
import java.io.IOException
import java.util.UUID
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicBoolean
import java.util.concurrent.atomic.AtomicReference
import kotlin.concurrent.thread
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.async
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.delay
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeout
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith

/** Android SQLite/rename/copy contract, using owned CC0 data; this is not a full SAF UI test. */
@RunWith(AndroidJUnit4::class)
class DictionaryPackIntegrationTest {
    private val instrumentation = InstrumentationRegistry.getInstrumentation()
    private val target = instrumentation.targetContext

    @Test fun installReadsFormsNfkcAndExactArabicDefinitionsFromRealSqlite() = runBlocking {
        withOwnedFiles { context ->
            val installer = DictionaryPackInstaller(context)
            val status = install(installer, fixture(context, V1))
            assertEquals("owned-parity183-v1", status.version)
            assertEquals(4L, status.entryCount)
            val repository = OfflineDictionaryRepository(context)
            val running = requireNotNull(repository.lookup("running", "en"))
            assertEquals("run", running.lemma)
            assertEquals("/rʌn/", running.phonetic)
            assertEquals(listOf("running", "ran", "runnings"), running.inflections)
            assertEquals(listOf(
                WordSense("v.", listOf("يركض؛ يتحرك بسرعة — owned v1"), "running → run; present participle"),
                WordSense("v.", listOf("يدير برنامجًا — run an app")),
                WordSense("n.", listOf("جولة أو مسار — a run"), "Separate homograph"),
            ), running.senses)
            // Forms select their linked entries, not every homograph sharing the returned lemma.
            val runnings = requireNotNull(repository.lookup("runnings", "en"))
            assertEquals(running.copy(senses = listOf(
                WordSense("v.", listOf("يركض؛ يتحرك بسرعة — owned v1"), "running → run; present participle"),
                WordSense("v.", listOf("يدير برنامجًا — run an app")),
            )), runnings)
            assertEquals(2, runnings.senses.size)
            val nfkcRunning = requireNotNull(repository.lookup("  ＲＵＮＮＩＮＧ  ", "en-US"))
            assertEquals(running, nfkcRunning)
            assertEquals(3, nfkcRunning.senses.size)
            val settings = requireNotNull(repository.lookup("Ｓｅｔｔｉｎｇｓ", "en"))
            assertEquals("Settings", settings.lemma)
            assertEquals(listOf("الإعدادات (Settings) — настройки"), settings.effectiveDefinitions())
            assertEquals(listOf("مرحبًا — Hello!"), repository.lookup("hello", "en")?.effectiveDefinitions())
            assertNull(repository.lookup("not-in-the-owned-pack", "en"))
            assertNoStaging(context)
        }
    }

    @Test fun invalidReplacementsKeepV1BytesAndV2AtomicallyReplacesItsDefinitions() = runBlocking {
        withOwnedFiles { context ->
            val installer = DictionaryPackInstaller(context)
            install(installer, fixture(context, V1))
            val installed = DictionaryPackInstaller.packFile(context, DictionaryPackId.ECDICT)
            val before = installed.readBytes()
            val repository = OfflineDictionaryRepository(context)
            val old = repository.lookup("running", "en")
            assertNotNull(old)
            for (invalid in listOf("wrong-pack-id.bin", "truncated-pack.bin")) {
                val result = installer.importPack(fixture(context, invalid), DictionaryPackId.ECDICT)
                assertTrue("$invalid was accepted: $result", result is DictionaryPackInstallResult.Failure)
                assertArrayEquals("$invalid modified the installed file", before, installed.readBytes())
                assertEquals(old, repository.lookup("running", "en"))
                assertVersion(installer, "owned-parity183-v1")
                assertNoStaging(context)
            }
            val replacement = fixture(context, V2)
            install(installer, replacement)
            assertArrayEquals(fixtureBytes(V2), installed.readBytes())
            assertVersion(installer, "owned-parity183-v2")
            // Reuse the same repository: a previously used connection must not retain old data.
            assertEquals("يركض؛ يتحرك بسرعة — reviewed v2",
                repository.lookup("runnings", "en")?.senses?.first()?.definitions?.single())
            assertNoStaging(context)
        }
    }

    @Test
    @SdkSuppress(minSdkVersion = 29)
    fun cancellingAnActualPartialPipeCopyKeepsV2CleansStagingAndAllowsNextImport() = runBlocking {
        withOwnedFiles { context ->
            val installer = DictionaryPackInstaller(context)
            install(installer, fixture(context, V2))
            val installed = DictionaryPackInstaller.packFile(context, DictionaryPackId.ECDICT)
            val before = installed.readBytes()
            val provider = SlowOwnedSource(fixtureBytes(V1))
            val resolver = ContentResolver.wrap(provider)
            val slowContext = object : ContextWrapper(context) {
                override fun getFilesDir(): File = context.filesDir
                override fun getContentResolver(): ContentResolver = resolver
            }
            val published = AtomicBoolean()
            val copy = async(Dispatchers.IO) {
                DictionaryPackInstaller(slowContext).importPack(SlowOwnedSource.URI, DictionaryPackId.ECDICT)
                    .also { published.set(true) }
            }
            try {
                withTimeout(10_000) {
                    while (staging(context).none { it.length() in 1 until before.size.toLong() }) {
                        check(!copy.isCompleted) { "Import completed before an actual partial copy was observed" }
                        delay(10)
                    }
                }
                assertFalse(copy.isCompleted)
                assertEquals(1, provider.opens)
                // Cancel only after actual FileOutputStream bytes exist, not on job admission.
                // The owned provider then releases the next chunk to drain any blocking read.
                copy.cancel(CancellationException("Owned fixture mid-copy cancellation"))
                provider.releaseTail()
                withTimeout(10_000) { copy.join() }
                assertTrue(copy.isCancelled)
                assertFalse("Cancelled import published a Success/Failure result", published.get())
                assertNoStaging(context)
                assertArrayEquals("Cancellation replaced v2", before, installed.readBytes())
                assertVersion(installer, "owned-parity183-v2")
                assertEquals("يركض؛ يتحرك بسرعة — reviewed v2", OfflineDictionaryRepository(context)
                    .lookup("running", "en")?.senses?.first()?.definitions?.single())
            } finally {
                withContext(NonCancellable) {
                    copy.cancel()
                    provider.releaseTail()
                    try { withTimeout(10_000) { copy.cancelAndJoin() } }
                    finally { provider.close() }
                }
            }
            // A cancelled operation must release the shared installer lock and file ownership.
            withTimeout(10_000) { install(installer, fixture(context, V1)) }
            assertVersion(installer, "owned-parity183-v1")
            assertArrayEquals(fixtureBytes(V1), installed.readBytes())
            assertNoStaging(context)
        }
    }

    private suspend fun install(installer: DictionaryPackInstaller, uri: Uri): DictionaryPackStatus {
        val result = installer.importPack(uri, DictionaryPackId.ECDICT)
        assertTrue("Import failed: $result", result is DictionaryPackInstallResult.Success)
        return (result as DictionaryPackInstallResult.Success).status.also { assertTrue(it.installed) }
    }

    private suspend fun assertVersion(installer: DictionaryPackInstaller, version: String) {
        val status = installer.statuses().single { it.spec.id == DictionaryPackId.ECDICT }
        assertTrue("Installed pack became unreadable: $status", status.installed)
        assertEquals(version, status.version)
        assertEquals(4L, status.entryCount)
        assertEquals(40_960L, status.byteCount)
    }

    private fun fixtureBytes(name: String): ByteArray =
        instrumentation.context.assets.open("dictionary-pack-fixtures/$name").use { it.readBytes() }

    private fun fixture(context: Context, name: String): Uri {
        val input = File(context.filesDir, "input-$name")
        input.writeBytes(fixtureBytes(name))
        return Uri.fromFile(input)
    }

    private fun staging(context: Context): List<File> =
        DictionaryPackInstaller.packDirectory(context).listFiles().orEmpty()
            .filter { it.name.startsWith("dictionary-import-") }

    private fun assertNoStaging(context: Context) =
        assertTrue("Staging files were retained: ${staging(context).map { it.name to it.length() }}", staging(context).isEmpty())

    private suspend fun withOwnedFiles(action: suspend (Context) -> Unit) {
        val root = File(target.cacheDir, "qa-dictionary-pack-${UUID.randomUUID()}")
        check(root.mkdirs())
        val context = object : ContextWrapper(target) { override fun getFilesDir(): File = root }
        var primary: Throwable? = null
        try { action(context) }
        catch (error: Throwable) { primary = error; throw error }
        finally {
            try {
                check(root.canonicalFile.parentFile == target.cacheDir.canonicalFile)
                check(root.deleteRecursively()) { "Could not remove owned dictionary fixture directory" }
            } catch (cleanup: Throwable) {
                if (primary != null) primary.addSuppressed(cleanup) else throw cleanup
            }
        }
    }

    /** Local-only provider, no registration/manifest/grants. A real Linux pipe supplies owned bytes. */
    private class SlowOwnedSource(private val bytes: ByteArray) : ContentProvider(), Closeable {
        private val tail = CountDownLatch(1)
        private val closing = AtomicBoolean()
        private val writerFailure = AtomicReference<Throwable?>()
        @Volatile private var descriptors: Array<ParcelFileDescriptor>? = null
        @Volatile private var writer: Thread? = null
        @Volatile var opens = 0
            private set

        override fun openAssetFile(uri: Uri, mode: String): AssetFileDescriptor {
            check(uri == URI && mode == "r")
            check(opens++ == 0) { "The slow source must be opened only once" }
            val pipe = ParcelFileDescriptor.createPipe().also { descriptors = it }
            writer = thread(name = "owned-dictionary-pipe", isDaemon = true) {
                try {
                    ParcelFileDescriptor.AutoCloseOutputStream(pipe[1]).use { output ->
                        output.write(bytes, 0, 2_048)
                        check(tail.await(15, TimeUnit.SECONDS)) { "Partial-copy cancellation was never reached" }
                        var offset = 2_048
                        while (offset < bytes.size && !closing.get()) {
                            val size = minOf(1_024, bytes.size - offset)
                            output.write(bytes, offset, size)
                            offset += size
                            Thread.sleep(20)
                        }
                    }
                } catch (error: IOException) {
                    // Broken pipe is expected when the cancelled installer closes its read end.
                } catch (error: InterruptedException) {
                    if (!closing.get()) writerFailure.set(error)
                } catch (error: Throwable) { writerFailure.set(error) }
            }
            return AssetFileDescriptor(pipe[0], 0, AssetFileDescriptor.UNKNOWN_LENGTH)
        }

        fun releaseTail() = tail.countDown()

        override fun close() {
            closing.set(true)
            tail.countDown()
            descriptors?.forEach { runCatching { it.close() } }
            writer?.interrupt()
            writer?.join(3_000)
            check(writer?.isAlive != true) { "Owned pipe writer did not terminate" }
            writerFailure.get()?.let { throw AssertionError("Owned pipe source failed", it) }
        }

        override fun onCreate() = true
        override fun getType(uri: Uri) = "application/vnd.sqlite3"
        override fun query(uri: Uri, projection: Array<out String>?, selection: String?,
            selectionArgs: Array<out String>?, sortOrder: String?): Cursor? = throw UnsupportedOperationException()
        override fun insert(uri: Uri, values: ContentValues?): Uri? = throw UnsupportedOperationException()
        override fun delete(uri: Uri, selection: String?, selectionArgs: Array<out String>?): Int = throw UnsupportedOperationException()
        override fun update(uri: Uri, values: ContentValues?, selection: String?,
            selectionArgs: Array<out String>?): Int = throw UnsupportedOperationException()

        companion object { val URI: Uri = Uri.parse("content://owned.dictionary.fixture/slow-v1") }
    }

    private companion object {
        const val V1 = "owned-english-arabic-v1.bin"
        const val V2 = "owned-english-arabic-v2.db"
    }
}
