package dev.clickn.translate.ocr

import dev.clickn.translate.data.AutoOcrSettings
import dev.clickn.translate.data.OcrEngineKind
import dev.clickn.translate.data.Settings

/** An installed recognizer is required to discover Arabic; ML Kit never supplies Arabic glyphs. */
internal fun autoOcrBootstrapEngines(
    tesseractReady: Boolean,
    arabicPaddleReady: Boolean = false,
): List<OcrEngineKind> = buildList {
    addAll(listOf(OcrEngineKind.ML_KIT_JAPANESE, OcrEngineKind.ML_KIT_KOREAN,
        OcrEngineKind.ML_KIT_CHINESE, OcrEngineKind.ML_KIT_LATIN))
    // One Arabic discovery pass: an installed Paddle pack replaces, rather than
    // duplicates, Tesseract's bootstrap cost. Explicit overrides apply in refinement.
    if (arabicPaddleReady) add(OcrEngineKind.PADDLE_ONNX)
    else if (tesseractReady) add(OcrEngineKind.TESSERACT_ARABIC)
}

internal fun requiresArabicOcrBootstrap(settings: Settings): Boolean =
    AutoOcrSettings.languageKey(settings.sourceLang) == "ar"
