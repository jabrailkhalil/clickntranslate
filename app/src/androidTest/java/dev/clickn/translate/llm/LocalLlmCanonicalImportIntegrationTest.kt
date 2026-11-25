package dev.clickn.translate.llm

import android.content.ContextWrapper
import android.os.StatFs
import android.system.Os
import androidx.core.content.FileProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.filters.SdkSuppress
import androidx.test.platform.app.InstrumentationRegistry
import dev.clickn.translate.data.SettingsRepository
import dev.clickn.translate.data.SettingsSecretCipher
import dev.clickn.translate.data.SettingsStorage
import dev.clickn.translate.download.ModelFileDownloader
import java.io.File
import java.io.RandomAccessFile
import java.nio.file.FileSystemException
import java.nio.file.Files
import java.util.concurrent.atomic.AtomicInteger
import kotlinx.coroutines.flow.toList
import kotlinx.coroutines.runBlocking
import okhttp3.OkHttpClient
import okhttp3.Protocol
import okhttp3.Response
import okhttp3.ResponseBody.Companion.toResponseBody
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Assume.assumeTrue
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
@SdkSuppress(minSdkVersion = 33)
class LocalLlmCanonicalImportIntegrationTest {
    @Test
    fun truncatedDocumentPreservesTheWorkingModelAndLeavesNoStage() = runBlocking<Unit> {
        assumeTrue(InstrumentationRegistry.getArguments().getString("ownedNativeFixture") == "model-import183")
        val app = InstrumentationRegistry.getInstrumentation().targetContext
        assertEquals("dev.clickn.translate.debug", app.packageName)
        val hy = LlmModelKind.HY_MT2_1_8B_Q4_K_M
        val sakura = LlmModelKind.SAKURA_1_5B_Q4
        val (kind, working) = listOf(
            hy to File(app.cacheDir, "hymt183/${hy.fileName}"),
            sakura to File(app.cacheDir, "sakura183/models/llm/${sakura.fileName}"),
        ).first { (model, file) -> file.isFile && file.length() == model.expectedSizeBytes }
        val root = Files.createTempDirectory(app.cacheDir.toPath(), "llm-import-").toFile()
        val exports = File(app.cacheDir, "log_exports").apply { mkdirs() }
        val docs = Files.createTempDirectory(exports.toPath(), "llm-import-").toFile()
        val context = object : ContextWrapper(app) { override fun getFilesDir() = root }
        val storage = SettingsStorage(File(root, "isolated.preferences_pb"))
        val cipher = object : SettingsSecretCipher {
            override fun encrypt(plainText: String): String = error("No credentials in this test")
            override fun decrypt(cipherText: String): String = error("No credentials in this test")
        }
        try {
            val httpRequests = AtomicInteger()
            val offline = OkHttpClient.Builder().addInterceptor { chain ->
                httpRequests.incrementAndGet()
                Response.Builder().request(chain.request()).protocol(Protocol.HTTP_1_1)
                    .code(503).message("Offline QA upstream").body("".toResponseBody()).build()
            }.build()
            val installer = LlmModelInstaller(context, ModelFileDownloader(offline), SettingsRepository(context, cipher, storage.dataStore))
            val installed = File(installer.modelsDir, kind.fileName)
            val fullCustom = InstrumentationRegistry.getArguments().getString("fullCustomImport") == "true"
            val reserve = if (fullCustom) 2L * working.length() else working.length()
            assertTrue("The isolated model copies must fit.", StatFs(root.absolutePath).availableBytes >= reserve + 512L * 1024 * 1024)
            linkOrCopy(working, installed)
            val before = Os.stat(installed.absolutePath)
            val corrupt = File(docs, kind.fileName).apply { writeText("GGUFtruncated") }
            val uri = FileProvider.getUriForFile(app, "${app.packageName}.logfileprovider", corrupt)
            assertEquals(0, installer.importFromLocal(listOf(uri), kind))
            val after = Os.stat(installed.absolutePath)
            assertEquals(before.st_dev, after.st_dev)
            assertEquals(before.st_ino, after.st_ino)
            assertEquals(kind.expectedSizeBytes, after.st_size)
            assertEquals(installed, installer.checkInstalled(kind))
            assertEquals(listOf(installed.name), installer.modelsDir.list()?.toList())
            val report = JSONObject().put("model", kind.fileName).put("installedBytes", after.st_size)
                .put("rejectedBytes", corrupt.length()).put("sameInode", true).put("temporaryFiles", 0)
            if (fullCustom) {
                val renamed = File(docs, "custom-weights.gguf")
                assertEquals(null, LlmModelIntegrity.importPin(kind, renamed.name))
                // The pinned fixtures have <6 MiB of metadata. Keep that exact tensor directory
                // in a sparse input while cutting 8 MiB off its advertised tensor payload.
                val prefix = ByteArray(8 * 1024 * 1024)
                working.inputStream().buffered().use { input -> java.io.DataInputStream(input).readFully(prefix) }
                RandomAccessFile(renamed, "rw").use { truncated ->
                    truncated.write(prefix)
                    truncated.setLength(working.length() - prefix.size)
                }
                val customUri = FileProvider.getUriForFile(app, "${app.packageName}.logfileprovider", renamed)
                assertEquals(0, installer.importFromLocal(listOf(customUri), kind))
                assertEquals(before.st_ino, Os.stat(installed.absolutePath).st_ino)
                assertEquals(listOf(installed.name), installer.modelsDir.list()?.toList())
                report.put("renamedTruncatedBytes", renamed.length()).put("renamedTruncatedRejected", true)

                // Simulate an older version which had already installed this incomplete file.
                assertTrue(installed.delete())
                val truncatedBytes = renamed.length()
                Files.move(renamed.toPath(), installed.toPath())
                val oldInode = Os.stat(installed.absolutePath).st_ino
                val failure = runCatching { installer.download(kind).toList() }.exceptionOrNull()
                assertTrue("An explicit download must try the offline upstream.", failure != null && httpRequests.get() > 0)
                assertEquals(oldInode, Os.stat(installed.absolutePath).st_ino)
                assertEquals(truncatedBytes, installed.length())
                report.put("retriedIncompleteInstallation", true).put("retainedAfterDownloadFailure", true)

                linkOrCopy(working, renamed)
                assertEquals(1, installer.importFromLocal(listOf(customUri), kind))
                assertEquals(installed, installer.checkInstalled(kind))
                assertEquals(null, LlmModelIntegrity.validate(installed, kind.expectedSizeBytes, kind.expectedSha256))
                assertEquals(listOf(installed.name), installer.modelsDir.list()?.toList())
                val requestsBefore = httpRequests.get()
                assertTrue(installer.download(kind).toList().single().done)
                assertEquals(requestsBefore, httpRequests.get())
                report.put("customImportVerifiedSha256", kind.expectedSha256).put("validDownloadReusedFile", true)
            }
            File(app.cacheDir, "llm-import-qa-result.json").writeText(report.toString(2))
        } finally {
            storage.closeAndJoin()
            assertTrue(docs.deleteRecursively())
            assertTrue(root.deleteRecursively())
        }
    }

    private fun linkOrCopy(source: File, destination: File) {
        try {
            Files.createLink(destination.toPath(), source.toPath())
        } catch (_: FileSystemException) {
            Files.copy(source.toPath(), destination.toPath())
        } catch (_: UnsupportedOperationException) {
            Files.copy(source.toPath(), destination.toPath())
        }
    }
}
