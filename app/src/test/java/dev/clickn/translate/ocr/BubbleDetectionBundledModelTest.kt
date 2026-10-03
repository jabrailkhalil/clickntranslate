// Modified for Click'n'Translate on October 3, 2026.
package dev.clickn.translate.ocr

import java.io.File
import java.io.RandomAccessFile
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder

class BubbleDetectionBundledModelTest {
    @get:Rule
    val temporaryFolder = TemporaryFolder()

    @Test
    fun validateModelFile_tableDriven_rejectsMissingWrongSizeAndWrongDigest() {
        data class Case(
            val name: String,
            val prepare: (File) -> Unit,
            val expectedReason: String,
        )
        val cases = listOf(
            Case("missing", prepare = {}, expectedReason = "missing"),
            Case(
                "wrong size",
                prepare = { it.writeBytes(byteArrayOf(0x08, 0x01)) },
                expectedReason = "size mismatch",
            ),
            Case(
                "correct size wrong digest",
                prepare = {
                    it.writeBytes(byteArrayOf(0x08, 0x01))
                    RandomAccessFile(it, "rw").use { output ->
                        output.setLength(BubbleDetectionModelProvider.EXPECTED_BYTES)
                    }
                },
                expectedReason = "SHA-256 mismatch",
            ),
        )

        cases.forEach { case ->
            val file = File(temporaryFolder.root, case.name)
            case.prepare(file)
            val result = BubbleDetectionModelProvider.validateModelFile(file)
            assertNotNull(case.name, result)
            assertTrue("$case: $result", result!!.contains(case.expectedReason))
        }
    }

    @Test
    fun bundledAsset_matchesPinnedProductionArtifact() {
        val candidates = listOf(
            File("src/main/assets/${BubbleDetectionModelProvider.BUNDLED_ASSET_PATH}"),
            File("app/src/main/assets/${BubbleDetectionModelProvider.BUNDLED_ASSET_PATH}"),
        )
        val asset = candidates.firstOrNull(File::isFile)
        assertNotNull("Bundled detector asset is missing; checked $candidates", asset)
        assertNull(
            asset!!.absolutePath,
            BubbleDetectionModelProvider.validateModelFile(asset),
        )
    }

    @Test
    fun pinnedArtifactMetadata_matchesVerifiedProductionModel() {
        assertEquals(11_120_765L, BubbleDetectionModelProvider.EXPECTED_BYTES)
        assertEquals(
            "5FE9E4F576E49D4E7E8B0E029D6D3CDC252ABD4694113E1CAE120E62C931EA79",
            BubbleDetectionModelProvider.EXPECTED_SHA256,
        )
        assertEquals("Apache-2.0", BubbleDetectionModelProvider.MODEL_LICENSE)
        assertTrue(
            BubbleDetectionModelProvider.MODEL_SOURCE_URL.startsWith(
                "https://huggingface.co/"
            )
        )
    }
}
