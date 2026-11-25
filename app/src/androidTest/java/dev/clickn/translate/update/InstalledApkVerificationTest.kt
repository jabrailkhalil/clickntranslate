package dev.clickn.translate.update

import androidx.core.content.FileProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import dev.clickn.translate.BuildConfig
import java.io.File
import java.security.MessageDigest
import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertThrows
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class InstalledApkVerificationTest {
    private val instrumentation get() = InstrumentationRegistry.getInstrumentation()

    @Test fun ownInstalledArchiveIsRecognizedAndReadableThroughTheInstallerUri() {
        val app = instrumentation.targetContext
        val installed = File(app.applicationInfo.sourceDir)
        val metadata = metadata(installed)
        val ready = requireNotNull(verifiedApkFile(app, metadata).parentFile)
        require(ready.isDirectory || ready.mkdirs())
        val cached = File.createTempFile("qa-installed-", ".apk", ready)
        try {
            installed.inputStream().use { input ->
                cached.outputStream().use { output -> copyVerified(input, output, metadata) {} }
            }
            assertThrows(AlreadyInstalled::class.java) { verifyArchive(app, cached, metadata) }
            assertThrows(InvalidApk::class.java) {
                verifyArchive(app, cached, metadata.copy(advertisedCode = BuildConfig.VERSION_CODE + 1L))
            }
            val uri = FileProvider.getUriForFile(app, "${app.packageName}.logfileprovider", cached)
            val fromInstallerUri = app.contentResolver.openInputStream(uri)!!.use { it.readBytesOfHeader() }
            assertArrayEquals(installed.inputStream().use { it.readBytesOfHeader() }, fromInstallerUri)
        } finally {
            cached.delete()
        }
    }

    @Test fun anApkWithAnotherApplicationIdIsRejectedByTheInstalledPackageCheck() {
        val app = instrumentation.targetContext
        val otherApk = File(instrumentation.context.applicationInfo.sourceDir)
        assertThrows(InvalidApk::class.java) { verifyArchive(app, otherApk, metadata(otherApk)) }
    }

    private fun metadata(file: File): ReleaseApk {
        val digest = MessageDigest.getInstance("SHA-256")
        file.inputStream().buffered().use { input ->
            val bytes = ByteArray(64 * 1024)
            while (true) {
                val size = input.read(bytes)
                if (size < 0) break
                digest.update(bytes, 0, size)
            }
        }
        val version = BuildConfig.VERSION_NAME
        return ReleaseApk("v$version", "ClicknTranslate-$version-universal.apk", file.length(),
            digest.digest().hex(), BuildConfig.VERSION_CODE.toLong())
    }

    private fun java.io.InputStream.readBytesOfHeader() = ByteArray(4).also {
        java.io.DataInputStream(this).readFully(it)
    }
}
