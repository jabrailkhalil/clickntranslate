// Modified for Click'n'Translate on October 3, 2026.
package dev.clickn.translate.service

import dev.clickn.translate.data.OcrEngineKind
import org.junit.Assert.assertEquals
import org.junit.Test

class ShapeAwareBubbleEnginePolicyTest {
    @Test
    fun supportedEngines_tableDriven_onlyIncludesDbnetEngines() {
        val expected = mapOf(
            OcrEngineKind.PADDLE_ONNX to true,
            OcrEngineKind.MANGA_OCR_JA to true,
        )

        OcrEngineKind.entries.forEach { engine ->
            assertEquals(
                engine.name,
                expected[engine] ?: false,
                supportsShapeAwareBubblePatches(engine),
            )
        }
    }
}
