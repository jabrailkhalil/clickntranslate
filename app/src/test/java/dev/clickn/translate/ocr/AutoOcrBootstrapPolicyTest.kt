package dev.clickn.translate.ocr

import dev.clickn.translate.data.OcrEngineKind
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Test

class AutoOcrBootstrapPolicyTest {
    @Test fun installedArabicPaddleReplacesTesseractDiscoveryRatherThanRunningBoth() {
        val scripts = listOf(OcrEngineKind.ML_KIT_JAPANESE, OcrEngineKind.ML_KIT_KOREAN,
            OcrEngineKind.ML_KIT_CHINESE, OcrEngineKind.ML_KIT_LATIN)
        for (tesseractReady in listOf(false, true)) {
            val candidates = autoOcrBootstrapEngines(tesseractReady, arabicPaddleReady = true)
            assertEquals(scripts + OcrEngineKind.PADDLE_ONNX, candidates)
            assertEquals(1, candidates.count { it == OcrEngineKind.PADDLE_ONNX })
            assertFalse(OcrEngineKind.TESSERACT_ARABIC in candidates)
        }
    }

    @Test fun unavailableArabicPaddlePreservesExistingInstalledTesseractAndMlKitPaths() {
        assertEquals(autoOcrBootstrapEngines(false),
            autoOcrBootstrapEngines(false, arabicPaddleReady = false))
        assertEquals(autoOcrBootstrapEngines(true),
            autoOcrBootstrapEngines(true, arabicPaddleReady = false))
        assertEquals(listOf(OcrEngineKind.TESSERACT_ARABIC),
            autoOcrBootstrapEngines(true).filterNot { it in autoOcrBootstrapEngines(false) })
        assertFalse(OcrEngineKind.PADDLE_ONNX in autoOcrBootstrapEngines(false))
    }
}
