// Modified for Click'n'Translate on October 3, 2026.
package dev.clickn.translate.ocr

import android.app.ActivityManager
import android.graphics.Bitmap
import android.content.Context
import dagger.hilt.android.qualifiers.ApplicationContext
import dev.clickn.translate.R
import dev.clickn.translate.data.AutoOcrRoute
import dev.clickn.translate.data.AutoOcrRoutingPolicy
import dev.clickn.translate.data.OcrEngineKind
import dev.clickn.translate.data.PaddleModelVersion
import dev.clickn.translate.data.Settings
import dev.clickn.translate.download.ModelReadinessChecker
import dev.clickn.translate.translate.PageTranslationGroupingPolicy
import javax.inject.Inject
import javax.inject.Singleton
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.async
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.sync.Semaphore
import kotlinx.coroutines.sync.withPermit
import kotlinx.coroutines.withContext
import timber.log.Timber

internal data class AutomaticOcrResult(val blocks: List<TextBlock>, val manga: Boolean = false)

@Singleton
class AutomaticOcrRecognizer @Inject constructor(
    private val mlKit: MlKitOcrEngine,
    private val identifier: OcrTextLanguageIdentifier,
    private val readiness: ModelReadinessChecker,
    private val tesseractModels: TesseractModelStore,
    @ApplicationContext private val context: Context,
) {
    // Share the limit across screen and photo requests. Each SDK task borrows the frame until it drains.
    private val bootstrapPermits = Semaphore(
        if (context.getSystemService(ActivityManager::class.java)?.isLowRamDevice == true) 1 else 2,
    )

    internal suspend fun recognize(
        bitmap: Bitmap,
        settings: Settings,
        recognize: suspend (Bitmap, OcrEngineKind, Settings) -> List<TextBlock>,
    ): AutomaticOcrResult {
        tesseractModels.refresh()
        val tesseractReady = tesseractModels.state.value.ready
        val arabicPaddleRoute = AutoOcrRoute(OcrEngineKind.PADDLE_ONNX, PaddleModelVersion.V5_ARABIC)
        val arabicPaddleReady = withContext(Dispatchers.IO) {
            readiness.paddle(arabicPaddleRoute.paddleVersion).ready
        }
        if (!tesseractReady && !arabicPaddleReady && requiresArabicOcrBootstrap(settings))
            throw ModelNotReadyException(context.getString(R.string.settings_tesseract_models_missing))
        // Per-invocation caches only: concurrent gallery/screen jobs and page turns cannot share a language guess.
        val ready = mutableMapOf(arabicPaddleRoute to arabicPaddleReady)
        suspend fun route(language: String): AutoOcrRoute? = withContext(Dispatchers.IO) {
            AutoOcrRoutingPolicy.resolve(settings, language) { choice ->
                ready.getOrPut(choice) {
                    when (choice.engine) {
                        OcrEngineKind.PADDLE_ONNX -> readiness.paddle(choice.paddleVersion).ready
                        OcrEngineKind.MANGA_OCR_JA -> readiness.mangaOcr().ready
                        OcrEngineKind.TESSERACT_ARABIC -> tesseractModels.state.value.ready
                        else -> true
                    }
                }
            }
        }
        // Translation source language must not bypass automatic OCR language detection.
        val languageCache = mutableMapOf<String, String?>()
        suspend fun tagLanguages(blocks: List<TextBlock>): List<TextBlock> = blocks.map { block ->
            // Cache is bounded to this frame, with bounded samples. Never retain screenshot text globally.
            val sample = block.text.take(1000)
            val language = when {
                block.recognizedLanguage == "ar" -> "ar"
                languageCache.containsKey(sample) -> languageCache[sample]
                languageCache.size >= 128 -> null
                else -> identifier.identify(sample).also { languageCache[sample] = it }
            }
            block.copy(recognizedLanguage = language)
        }
        val wholePage = PageTranslationGroupingPolicy.shouldMergeAll(
            settings.renderMode, settings.mergeAdjacentBlocks, settings.mergeStrength)
        var nextPageParent = 0
        suspend fun tag(blocks: List<TextBlock>): List<TextBlock> {
            val tagged = tagLanguages(blocks)
            if (wholePage) {
                // Native parent 0 from two recognizers describes two unrelated regions.
                // Scope parents per pass before mixing so wrapped columns retain their evidence.
                val passParents = mutableMapOf<Int, Int>()
                return tagged.map { block ->
                    val parent = block.parentRegionId ?: return@map block
                    block.copy(parentRegionId = passParents.getOrPut(parent) { nextPageParent++ })
                }
            }
            if (settings.mergeAdjacentBlocks) return tagged
            // Native parent IDs still belong to this one recognizer pass here. Preparing
            // after mixing would either lose that evidence or confuse equal IDs from two
            // engines. Language ID also makes short English wraps eligible when the text
            // recognizer supplied only its generic Latin-script fallback.
            val paragraphs = prepareAutomaticEnglishParagraphBlocks(tagged)
            return if (paragraphs == tagged) tagged else tagLanguages(paragraphs)
        }
        fun evidence(blocks: List<TextBlock>) = blocks.map {
            AutoOcrEvidence(it.text, it.recognizedLanguage, it.confidence)
        }

        // Run independent ML Kit passes with bounded overlap. Consume them in the existing
        // order because tagging shares a per-frame cache and merging uses deterministic ties.
        val candidates = autoOcrBootstrapEngines(tesseractReady, arabicPaddleReady)
        val passes = coroutineScope {
            val mlKitPasses = candidates
                .filterNot { it == OcrEngineKind.TESSERACT_ARABIC || it == OcrEngineKind.PADDLE_ONNX }
                .associateWith { kind ->
                    async {
                        bootstrapPermits.withPermit { mlKit.recognize(bitmap, kind, settings) }
                    }
                }
            val results = linkedMapOf<OcrEngineKind, List<TextBlock>>()
            for (kind in candidates) {
                val mlKitPass = mlKitPasses[kind]
                val blocks = if (mlKitPass != null) {
                    tag(mlKitPass.await())
                } else {
                    val bootstrapSettings = settings.copy(
                        sourceLang = "auto",
                        paddleModelVersion = if (kind == OcrEngineKind.PADDLE_ONNX) {
                            arabicPaddleRoute.paddleVersion
                        } else settings.paddleModelVersion,
                    )
                    try {
                        tag(recognize(bitmap, kind, bootstrapSettings))
                    } catch (cancelled: CancellationException) {
                        throw cancelled
                    } catch (missing: ModelNotReadyException) {
                        if (requiresArabicOcrBootstrap(settings)) throw missing
                        continue // An optional Arabic model can disappear while work is queued.
                    }
                }
                results[kind] = blocks
                Timber.tag("AutoOCR").d("candidate=%s blocks=%d score=%.3f languages=%s", kind,
                    blocks.size, AutoOcrLanguagePolicy.score(evidence(blocks)),
                    blocks.map { it.recognizedLanguage }.distinct())
            }
            results
        }
        val best = selectAutoOcrRegions(passes.values.flatten(),
            { AutoOcrEvidence(it.text, it.recognizedLanguage, it.confidence) }, ::overlaps)
        if (best.isEmpty()) return AutomaticOcrResult(best)

        val groups = best.filter { it.recognizedLanguage != null }.groupBy { it.recognizedLanguage!! }
        var result = best
        var usedManga = false
        // One refinement per detected language, never recursive Auto calls or an unbounded retry queue.
        for ((language) in groups.entries.sortedByDescending { it.value.sumOf { b -> b.text.length } }.take(4)) {
            val selected = route(language) ?: continue
            val effective = AutoOcrRoutingPolicy.settingsFor(settings, language, selected)
            val refined = try {
                // The Arabic bootstrap does not cache another Paddle recognizer's
                // output. Other languages may select a different installed pack.
                passes[selected.engine]?.takeIf {
                    selected.engine != OcrEngineKind.PADDLE_ONNX || selected == arabicPaddleRoute
                } ?: tag(recognize(bitmap, selected.engine, effective))
            } catch (cancelled: CancellationException) {
                throw cancelled
            } catch (error: Exception) {
                Timber.tag("AutoOCR").w(error, "Refinement failed language=%s engine=%s; keep bootstrap", language, selected.engine)
                continue
            }
            val selectedRefinements = selectAutoOcrRegions(refined,
                { AutoOcrEvidence(it.text, it.recognizedLanguage, it.confidence) }, ::overlaps)
            val usable = completeAutoOcrRefinements(result, selectedRefinements, language,
                { AutoOcrEvidence(it.text, it.recognizedLanguage, it.confidence) }, ::overlaps,
                covers = { old, replacements ->
                    fun sourceRects(block: TextBlock) = block.sourceBoxes.ifEmpty { listOf(block.boundingBox) }
                        .map { MergeDebugRect(it.left, it.top, it.right, it.bottom) }
                    coversAutoOcrSourceRects(sourceRects(old), replacements.flatMap(::sourceRects))
                })
            val replaced = replaceAutoOcrRegions(result, usable, language, { it.recognizedLanguage }, ::overlaps)
            Timber.tag("AutoOCR").i("refinement language=%s original=%d selected=%d accepted=%d final=%d",
                language, result.size, selectedRefinements.size, usable.size, replaced.size)
            if (replaced != result) {
                result = replaced
                usedManga = usedManga || selected.engine == OcrEngineKind.MANGA_OCR_JA
            }
        }
        Timber.tag("AutoOCR").i("bootstrap=regions passes=%d languages=%s blocks=%d", passes.size, groups.keys, result.size)
        val mixed = if (wholePage) result else result.map { it.copy(parentRegionId = null) }
        return AutomaticOcrResult(mixed.sortedWith(compareBy({ it.boundingBox.top }, { it.boundingBox.left })), usedManga)
    }

    private fun overlaps(a: TextBlock, b: TextBlock): Boolean {
        val x = (minOf(a.boundingBox.right, b.boundingBox.right) - maxOf(a.boundingBox.left, b.boundingBox.left)).coerceAtLeast(0)
        val y = (minOf(a.boundingBox.bottom, b.boundingBox.bottom) - maxOf(a.boundingBox.top, b.boundingBox.top)).coerceAtLeast(0)
        val area = minOf(a.boundingBox.width().toLong() * a.boundingBox.height(), b.boundingBox.width().toLong() * b.boundingBox.height())
        return area > 0 && x.toLong() * y >= area * 0.5
    }
}
