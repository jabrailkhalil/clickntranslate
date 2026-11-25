package dev.clickn.translate.llm

import java.io.File
import java.nio.file.Files
import kotlinx.coroutines.CancellationException
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder

class LlmModelIntegrityTest {
    @get:Rule val directory = TemporaryFolder()

    @Test fun exactLengthAndKnownSha256RejectSameLengthCorruptionAndTruncation() {
        val file = File(directory.root, "fixture.gguf").apply { writeText("abc") }
        // Independent standard SHA-256 "abc" test vector; this helper validates content,
        // while the installer's separate structural guard requires the GGUF header.
        val sha = "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
        assertNull(LlmModelIntegrity.validate(file, 3, sha))
        file.writeText("abd")
        assertTrue(LlmModelIntegrity.validate(file, 3, sha)?.contains("SHA-256") == true)
        file.writeText("ab")
        assertTrue(LlmModelIntegrity.validate(file, 3, sha)?.contains("size") == true)
        file.writeText("abcd")
        assertTrue(LlmModelIntegrity.validate(file, 3, sha)?.contains("size") == true)
    }

    @Test fun cancellationDuringStreamedHashClosesTheFileWithoutChangingInstalledOrStagedBytes() {
        val installed = File(directory.root, "installed.gguf").apply { writeText("old-model") }
        val staged = File(directory.root, "staged.tmp").apply { writeBytes(ByteArray(256 * 1024) { 7 }) }
        var checkpoints = 0
        val failure = runCatching {
            LlmModelIntegrity.validate(staged, staged.length(), "0".repeat(64)) {
                if (++checkpoints == 3) throw CancellationException("fixture cancellation after a real chunk read")
            }
        }.exceptionOrNull()
        assertTrue(failure is CancellationException)
        assertEquals(3, checkpoints)
        assertEquals("old-model", installed.readText())
        assertEquals(256 * 1024L, staged.length())
        assertTrue(staged.readBytes().all { it == 7.toByte() })
        val retained = File(directory.root, "retained.tmp")
        Files.move(staged.toPath(), retained.toPath()) // Windows also proves the owned stream was closed.
        assertTrue(retained.isFile)
    }

    @Test fun catalogPinsMatchPublishedLfsObjectsWithoutMutableMainDownloads() {
        val expected = mapOf(
            LlmModelKind.HY_MT2_1_8B_Q4_K_M to Triple("a0c709d9fac510f2c807aa3af52872340dc37a4a",
                1_133_080_448L, "dc5f44fcf1fa496ee7ad725982c0c8c553a4de00259b53af84c4b89fb0c06699"),
            LlmModelKind.SAKURA_1_5B_Q4 to Triple("6b704808673c735e326dfa25fe6fe62ac6ebc401",
                1_259_173_504L, "6722487146c594984e4d222cae0b926c9715ffff712afb5f348b603417c01680"),
        )
        expected.forEach { (kind, pin) ->
            assertEquals(pin.first, kind.revision)
            assertEquals(pin.second, kind.expectedSizeBytes)
            assertEquals(pin.third, kind.expectedSha256)
            assertTrue(kind.downloadUrl.contains("/resolve/${pin.first}/"))
            assertFalse(kind.downloadUrl.contains("/resolve/main/"))
            assertTrue(kind.downloadUrl.endsWith("/${kind.fileName}"))
        }
    }
}
