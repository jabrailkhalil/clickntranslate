package dev.clickn.translate.gallery

import dev.clickn.translate.translate.OcrTranslationRequestTextPolicy
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.ensureActive
import kotlinx.serialization.decodeFromString
import kotlinx.serialization.json.Json

/** A task owns an immutable private copy; retries reuse its OCR and already translated blocks. */
internal object GallerySegmentRecovery {
    fun missingIndices(segments: List<GalleryTranslationSegment>): List<Int> =
        segments.indices.filter { segments[it].sourceText.isNotBlank() && segments[it].translatedText.isBlank() }

    fun resume(
        item: GalleryTranslationItemEntity,
        width: Int,
        height: Int,
        json: Json,
    ): List<GalleryTranslationSegment>? {
        if (item.localPath.isBlank() || item.processedWidth != width || item.processedHeight != height) return null
        return decode(item.segmentsJson, json)?.takeIf { segments ->
            segments.isNotEmpty() && segments.all { segment ->
                with(segment.boundingBox) { left >= 0 && top >= 0 && right > left && bottom > top && right <= width && bottom <= height }
            }
        }
    }

    fun decode(value: String, json: Json): List<GalleryTranslationSegment>? =
        runCatching { json.decodeFromString<List<GalleryTranslationSegment>>(value) }.getOrNull()

    suspend fun translateMissing(
        segments: List<GalleryTranslationSegment>,
        translate: suspend (List<String>) -> List<String?>,
    ): List<GalleryTranslationSegment> {
        currentCoroutineContext().ensureActive()
        val missing = missingIndices(segments)
        if (missing.isEmpty()) return segments
        val results = translate(missing.map { OcrTranslationRequestTextPolicy.normalize(segments[it].sourceText) })
        currentCoroutineContext().ensureActive()
        return segments.toMutableList().apply {
            missing.forEachIndexed { requestIndex, segmentIndex ->
                this[segmentIndex] = this[segmentIndex].copy(translatedText = results.getOrNull(requestIndex).orEmpty())
            }
        }
    }

    /** Image-only APIs must repeat their image request; reuse only exactly matching recognition. */
    fun mergeImageOnlyResult(
        previous: List<GalleryTranslationSegment>?,
        fresh: List<GalleryTranslationSegment>,
    ): List<GalleryTranslationSegment> {
        previous ?: return fresh
        fun key(segment: GalleryTranslationSegment) = Triple(segment.sourceText, segment.boundingBox, segment.sourceBoxes)
        val old = previous.associateBy(::key)
        if (old.size != previous.size || fresh.map(::key).toSet() != old.keys || fresh.size != previous.size) return fresh
        return fresh.map { segment ->
            val saved = old.getValue(key(segment))
            if (saved.translatedText.isNotBlank()) segment.copy(translatedText = saved.translatedText) else segment
        }
    }
}
