// Modified for Click'n'Translate on October 3, 2026.
package dev.clickn.translate.llm

import java.io.File
import java.io.IOException
import java.security.MessageDigest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertThrows
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder

class LlmModelInstallerValidationTest {

    @get:Rule
    val temp = TemporaryFolder()

    @Test
    fun pinnedImportChecksTheCompleteFileBeforeReplacingTheInstalledModel() {
        val original = "GGUFprevious-usable-model".toByteArray()
        val published = "GGUFcomplete-published-model".toByteArray()
        val publishedHash = MessageDigest.getInstance("SHA-256").digest(published)
            .joinToString("") { "%02x".format(it) }
        val pin = LlmModelIntegrity.Pin(published.size.toLong(), publishedHash)
        val kind = LlmModelKind.HY_MT2_1_8B_Q4_K_M
        val destination = File(temp.root, kind.fileName).apply { writeBytes(original) }
        val minimum = (published.size * 0.8).toLong()
        val damaged = listOf(
            published.copyOf(published.size - 1),
            published.copyOf().also { it[it.lastIndex] = 0 },
            published + byteArrayOf(1),
        )
        for (source in damaged) {
            assertTrue(source.size >= minimum)
            assertThrows(IOException::class.java) {
                LlmModelInstaller.installImportedModel(source.inputStream(), destination, minimum, pin) {}
            }
            assertTrue(original.contentEquals(destination.readBytes()))
            assertEquals(listOf(destination), temp.root.listFiles()?.toList())
        }
        LlmModelInstaller.installImportedModel(published.inputStream(), destination, minimum, pin) {}
        assertTrue(published.contentEquals(destination.readBytes()))
        assertEquals(kind.expectedSha256, LlmModelIntegrity.importPin(kind, kind.fileName.uppercase())?.sha256)
        val customPin = LlmModelIntegrity.importPin(kind, "My-Hy-MT2-Q6.gguf")
        assertNull(customPin)
        LlmModelInstaller.installImportedModel(original.inputStream(), destination, minimum, customPin) {}
        assertTrue(original.contentEquals(destination.readBytes()))
    }

    @Test
    fun validateGgufFile_coversInstallAndImportCases() {
        data class Case(
            val name: String,
            val bytes: ByteArray?,
            val minBytes: Long,
            val expectedError: String?,
        )

        val cases = listOf(
            Case("valid gguf", "GGUFbody".toByteArray(), minBytes = 4, expectedError = null),
            Case("missing file", null, minBytes = 4, expectedError = "missing"),
            Case("too small", "GGUF".toByteArray(), minBytes = 8, expectedError = "too small"),
            Case("html response", "<html>error</html>".toByteArray(), minBytes = 4, expectedError = "GGUF"),
        )

        cases.forEach { case ->
            val file = File(temp.root, "${case.name.replace(' ', '_')}.gguf")
            case.bytes?.let { file.writeBytes(it) }

            val error = LlmModelInstaller.validateGgufFile(file, case.minBytes)

            if (case.expectedError == null) {
                assertNull(case.name, error)
            } else {
                assertTrue(
                    "${case.name}: expected ${case.expectedError}, got $error",
                    error?.contains(case.expectedError, ignoreCase = true) == true
                )
            }
        }
    }

    @Test
    fun modelKindMetadata_coversLocalLlmInstallCases() {
        data class Case(
            val kind: LlmModelKind,
            val expectedFileName: String,
            val expectedApproxSizeMb: Int,
            val expectedTargetMode: LlmModelKind.TargetLangMode,
            val expectedOnlySource: String?,
        )

        val cases = listOf(
            Case(
                kind = LlmModelKind.SAKURA_1_5B_Q4,
                expectedFileName = "sakura-1.5b-qwen2.5-v1.0-Q5KS.gguf",
                expectedApproxSizeMb = 1260,
                expectedTargetMode = LlmModelKind.TargetLangMode.FIXED_ZH_CN,
                expectedOnlySource = "ja",
            ),
            Case(
                kind = LlmModelKind.HY_MT2_1_8B_Q4_K_M,
                expectedFileName = "Hy-MT2-1.8B-Q4_K_M.gguf",
                expectedApproxSizeMb = 1130,
                expectedTargetMode = LlmModelKind.TargetLangMode.FOLLOWS_SETTINGS,
                expectedOnlySource = null,
            ),
        )

        cases.forEach { case ->
            assertEquals(case.kind.name, case.expectedFileName, case.kind.fileName)
            assertEquals(case.kind.name, case.expectedApproxSizeMb, case.kind.approxSizeMb)
            assertEquals(case.kind.name, case.expectedTargetMode, case.kind.targetLangMode)
            assertEquals(case.kind.name, case.expectedOnlySource, case.kind.onlySourceLangBcp47)
            assertTrue(case.kind.name, case.kind.downloadUrl.endsWith("/${case.expectedFileName}"))
            assertEquals(
                case.kind.name,
                case.expectedApproxSizeMb.toLong() * 1024L * 1024L * 80L / 100L,
                LlmModelInstaller.minimumSizeBytes(case.kind)
            )
        }
    }
}
