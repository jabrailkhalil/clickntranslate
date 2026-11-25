package dev.clickn.translate.ocr

import java.nio.file.Files
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Test

class PaddleArabicModelSpecTest {
    @Test
    fun pinnedFileRejectsSameSizeCorruptionAndAcceptsExactBytes() {
        val file = Files.createTempFile("paddle-model-integrity", ".onnx").toFile()
        val spec = PaddlePinnedModelFile("rec.onnx", "PaddlePaddle/model", "revision", "inference.onnx", 3L,
            "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad")
        try {
            file.writeText("abc", Charsets.UTF_8)
            assertNull(spec.validationError(file))
            file.writeText("abd", Charsets.UTF_8)
            assertEquals("pinned model SHA-256 mismatch", spec.validationError(file))
            file.writeText("ab", Charsets.UTF_8)
            assertEquals("pinned model size mismatch", spec.validationError(file))
        } finally {
            file.delete()
        }
    }

    @Test
    fun arabicPackPinsDistinctDetectorRecognizerAndUtf8Dictionary() {
        assertEquals(setOf("det.onnx", "rec.onnx", "keys.yml"), PaddleArabicModelSpec.files.map { it.fileName }.toSet())
        assertEquals(7_998_947L, PaddleArabicModelSpec.recognition.bytes)
        assertEquals(6_165L, PaddleArabicModelSpec.keys.bytes)
        assertEquals(PaddleArabicModelSpec.recognition.revision, PaddleArabicModelSpec.keys.revision)
        assertEquals("inference.yml", PaddleArabicModelSpec.keys.sourceFileName)
        assertNotNull(PaddleArabicModelSpec.forFile("keys.yml"))
        assertNull(PaddleArabicModelSpec.forFile("keys.txt"))
        assertEquals("Apache-2.0", PaddleArabicModelSpec.LICENSE)
    }
}
