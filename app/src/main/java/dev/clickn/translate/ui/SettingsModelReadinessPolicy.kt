// Modified for Click'n'Translate on October 3, 2026.
package dev.clickn.translate.ui

import dev.clickn.translate.data.OcrEngineKind
import dev.clickn.translate.data.PaddleModelVersion
import dev.clickn.translate.data.TranslationPreset
import dev.clickn.translate.data.TranslatorEngine
import dev.clickn.translate.llm.LlmModelKind

internal data class SettingsModelReadinessRequest(
    val llmKinds: Set<LlmModelKind>,
    val paddleVersions: Set<PaddleModelVersion>,
)

/** Union of the selected model and preset requirements, not a persistent readiness cache. */
internal fun settingsModelReadinessRequest(
    translatorEngine: TranslatorEngine,
    paddleModelVersion: PaddleModelVersion,
    presets: List<TranslationPreset>,
): SettingsModelReadinessRequest = SettingsModelReadinessRequest(
    llmKinds = buildSet {
        localLlmModelKindFor(translatorEngine)?.let(::add)
        presets.mapNotNullTo(this) { localLlmModelKindFor(it.translatorEngine) }
    },
    paddleVersions = buildSet {
        add(paddleModelVersion)
        presets.filter { it.ocrEngine == OcrEngineKind.PADDLE_ONNX || it.ocrEngine == OcrEngineKind.MANGA_OCR_JA }
            .mapTo(this) { it.paddleModelVersion }
    },
)

internal data class SettingsModelStates<L, D>(
    val llm: Map<LlmModelKind, L>,
    val paddle: Map<PaddleModelVersion, D>,
    val manga: D,
    val orientation: D,
)

internal fun <L, D> checkSettingsModels(
    request: SettingsModelReadinessRequest,
    llm: (LlmModelKind) -> L,
    paddle: (PaddleModelVersion) -> D,
    manga: () -> D,
    orientation: () -> D,
): SettingsModelStates<L, D> = SettingsModelStates(
    llm = request.llmKinds.associateWith(llm),
    paddle = request.paddleVersions.associateWith(paddle),
    manga = manga(),
    orientation = orientation(),
)
