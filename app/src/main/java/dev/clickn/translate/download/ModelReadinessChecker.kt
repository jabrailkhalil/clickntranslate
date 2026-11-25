// Modified for Click'n'Translate on October 3, 2026.
package dev.clickn.translate.download

import dev.clickn.translate.data.PaddleModelVersion
import dev.clickn.translate.llm.LlmModelInstaller
import dev.clickn.translate.llm.LlmModelKind
import dev.clickn.translate.llm.LocalLlmDeviceCapability
import dev.clickn.translate.ocr.MangaOcrModelInstaller
import dev.clickn.translate.ocr.OrientationModelInstaller
import dev.clickn.translate.ocr.PaddleModelInstaller
import dev.clickn.translate.ocr.TesseractModelStore
import dev.clickn.translate.ocr.TesseractModelFiles
import dev.clickn.translate.translate.MlKitOnDeviceTranslator
import dev.clickn.translate.translate.MlKitLanguagePolicy
import javax.inject.Inject
import javax.inject.Singleton

enum class ModelReadinessState {
    READY,
    MISSING,
    UNSUPPORTED,
}

data class ModelReadiness(
    val spec: ModelDownloadSpec,
    val installed: Boolean,
    val supported: Boolean,
    val totalBytes: Long = 0L,
) {
    val state: ModelReadinessState
        get() = when {
            !supported -> ModelReadinessState.UNSUPPORTED
            installed -> ModelReadinessState.READY
            else -> ModelReadinessState.MISSING
        }

    val ready: Boolean
        get() = state == ModelReadinessState.READY

    val downloadable: Boolean
        get() = state == ModelReadinessState.MISSING
}

/**
 * Shared model readiness boundary for onboarding, settings and download completion checks.
 * Installers remain responsible for validating their own file formats; this class makes every
 * caller consume those validations and the same runtime compatibility rule.
 */
@Singleton
class ModelReadinessChecker @Inject constructor(
    private val paddleInstaller: PaddleModelInstaller,
    private val mangaOcrInstaller: MangaOcrModelInstaller,
    private val orientationModelInstaller: OrientationModelInstaller,
    private val llmInstaller: LlmModelInstaller,
    private val localLlmDeviceCapability: LocalLlmDeviceCapability,
    private val tesseractModels: TesseractModelStore,
    private val mlKit: MlKitOnDeviceTranslator,
) {
    @Volatile private var downloadedMlKitLanguages: Set<String> = emptySet()
    private val mlKitInventoryLock = Any()
    private var mlKitInventoryRevision = 0L

    fun invalidateMlKitInventory() = synchronized(mlKitInventoryLock) {
        mlKitInventoryRevision++
        downloadedMlKitLanguages = emptySet()
    }

    /** Explicit inventory refresh only; never initiates a model download. */
    suspend fun refresh(specs: List<ModelDownloadSpec>) {
        if (specs.any { it.type == ModelDownloadType.TESSERACT_ARABIC }) tesseractModels.refresh()
        if (specs.any { it.type == ModelDownloadType.ML_KIT_TRANSLATION }) {
            val revision = synchronized(mlKitInventoryLock) { mlKitInventoryRevision }
            val installed = mlKit.getDownloadedLanguageModels()
            synchronized(mlKitInventoryLock) {
                if (revision == mlKitInventoryRevision) downloadedMlKitLanguages = installed
            }
        }
    }
    fun check(spec: ModelDownloadSpec): ModelReadiness =
        modelReadinessWithDependencies(spec, ::checkArtifact)

    /** Downloads skip valid files independently even when another required component is missing. */
    fun checkArtifact(spec: ModelDownloadSpec): ModelReadiness = when (spec.type) {
        ModelDownloadType.TESSERACT_ARABIC -> ModelReadiness(spec, tesseractModels.state.value.ready, true,
            if (tesseractModels.state.value.ready) TesseractModelFiles.models.sumOf { it.bytes } else 0L)
        ModelDownloadType.ML_KIT_TRANSLATION -> {
            val (source, target) = spec.mlKitLanguages()
            ModelReadiness(spec, source == target || downloadedMlKitLanguages.containsAll(
                MlKitLanguagePolicy.requiredDownloadLanguages(source, target)), true)
        }
        ModelDownloadType.PADDLE -> {
            val files = paddleInstaller.checkInstalled(PaddleModelVersion.valueOf(spec.variant))
            ModelReadiness(
                spec = spec,
                installed = files != null,
                supported = true,
                totalBytes = files?.totalBytes ?: 0L,
            )
        }
        ModelDownloadType.MANGA_OCR -> {
            val files = mangaOcrInstaller.checkInstalled()
            ModelReadiness(
                spec = spec,
                installed = files != null,
                supported = true,
                totalBytes = files?.let {
                    it.encoder.length() + it.decoder.length() + it.vocab.length() +
                        it.config.length() + it.generationConfig.length() +
                        it.preprocessorConfig.length() + it.specialTokensMap.length()
                } ?: 0L,
            )
        }
        ModelDownloadType.ORIENTATION -> {
            val files = orientationModelInstaller.checkFullyInstalled()
            ModelReadiness(
                spec = spec,
                installed = files != null,
                supported = true,
                totalBytes = files?.totalBytes ?: 0L,
            )
        }
        ModelDownloadType.LLM -> {
            val file = llmInstaller.checkInstalled(LlmModelKind.valueOf(spec.variant))
            ModelReadiness(
                spec = spec,
                installed = file != null,
                supported = localLlmDeviceCapability.isSupported(),
                totalBytes = file?.length() ?: 0L,
            )
        }
    }

    fun paddle(version: PaddleModelVersion): ModelReadiness =
        check(ModelDownloadSpec.paddle(version))

    fun mangaOcr(): ModelReadiness = check(ModelDownloadSpec.mangaOcr())

    fun orientation(): ModelReadiness = check(ModelDownloadSpec.orientation())
    fun tesseractArabic(): ModelReadiness = check(ModelDownloadSpec.tesseractArabic())

    fun llm(kind: LlmModelKind): ModelReadiness = check(ModelDownloadSpec.llm(kind))

    fun isLocalLlmSupported(): Boolean = localLlmDeviceCapability.isSupported()
}
