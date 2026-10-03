// Modified for Click'n'Translate on October 3, 2026.
package dev.clickn.translate.gallery

import dev.clickn.translate.data.OcrEngineKind
import dev.clickn.translate.data.TranslatorEngine
import java.io.IOException

internal object GalleryTranslationWorkPolicy {
    const val ACTION_SEND = "android.intent.action.SEND"
    const val ACTION_SEND_MULTIPLE = "android.intent.action.SEND_MULTIPLE"
    const val MAX_IMAGES_PER_TASK = 100
    const val MAX_RETRY_ATTEMPTS = 3
    const val FOREGROUND_IMAGE_THRESHOLD = 10
    const val WORK_TAG = "gallery_translation"

    fun uniqueWorkName(taskId: String): String = "gallery_translation_$taskId"

    fun normalizeSelection(uriStrings: List<String>): List<String> =
        uriStrings.asSequence()
            .map(String::trim)
            .filter(String::isNotEmpty)
            .distinct()
            .take(MAX_IMAGES_PER_TASK)
            .toList()

    fun mergeSelection(current: List<String>, additions: List<String>): List<String> =
        normalizeSelection(current + additions)

    fun removeSelection(current: List<String>, uriString: String): List<String> {
        val target = uriString.trim()
        return normalizeSelection(current).filterNot { it == target }
    }

    fun sharedImageSelection(
        action: String?,
        mimeType: String?,
        singleUri: String?,
        multipleUris: List<String>,
    ): List<String> {
        if (mimeType?.startsWith("image/", ignoreCase = true) != true) return emptyList()
        val candidates = when (action) {
            ACTION_SEND -> listOfNotNull(singleUri)
            ACTION_SEND_MULTIPLE -> multipleUris
            else -> emptyList()
        }
        // Exported share intents may only point to content providers. Never let another
        // app make us read file:// paths inside our own private storage.
        return normalizeSelection(candidates).filter { value ->
            runCatching { java.net.URI(value) }.getOrNull()?.let { uri ->
                uri.scheme.equals("content", true) && !uri.rawAuthority.isNullOrBlank() && uri.rawUserInfo == null
            } == true
        }
    }

    fun requiresNetwork(
        ocrEngine: OcrEngineKind,
        translatorEngine: TranslatorEngine,
    ): Boolean = ocrEngine in networkOcrEngines || translatorEngine in networkTranslators

    fun shouldUseForeground(
        imageCount: Int,
        translatorEngine: TranslatorEngine,
    ): Boolean =
        imageCount >= FOREGROUND_IMAGE_THRESHOLD ||
            translatorEngine == TranslatorEngine.LOCAL_SAKURA ||
            translatorEngine == TranslatorEngine.LOCAL_HY_MT2

    fun terminalStatus(
        progress: GalleryTaskProgress,
        canceled: Boolean,
    ): GalleryTaskStatus = when {
        canceled -> GalleryTaskStatus.CANCELED
        progress.total <= 0 -> GalleryTaskStatus.FAILED
        progress.completed < progress.total -> GalleryTaskStatus.RUNNING
        progress.succeeded == progress.total -> GalleryTaskStatus.SUCCEEDED
        progress.failed == progress.total -> GalleryTaskStatus.FAILED
        else -> GalleryTaskStatus.PARTIAL
    }

    fun shouldRetry(error: Throwable, attemptCount: Int): Boolean {
        if (attemptCount >= MAX_RETRY_ATTEMPTS) return false
        val causes = mutableListOf<Throwable>()
        val seen = java.util.Collections.newSetFromMap(java.util.IdentityHashMap<Throwable, Boolean>())
        var current: Throwable? = error
        while (current != null && causes.size < 32 && seen.add(current)) {
            causes += current
            current = current.cause
        }
        if (causes.any { it is IOException }) return true
        val message = causes.joinToString(" ") { it.message.orEmpty() }.lowercase()
        return retryableMarkers.any(message::contains)
    }

    fun shouldRetryFailedTranslation(enabled: Boolean, attemptCount: Int): Boolean =
        enabled && attemptCount == FIRST_RETRY_ATTEMPT

    private val networkOcrEngines = setOf(
        OcrEngineKind.UMI_OCR,
        OcrEngineKind.LUNA_OCR,
        OcrEngineKind.BAIDU,
        OcrEngineKind.TENCENT,
        OcrEngineKind.YOUDAO,
        OcrEngineKind.PADDLE_AI_STUDIO,
    )

    private val networkTranslators = setOf(
        TranslatorEngine.OPENAI,
        TranslatorEngine.ANTHROPIC,
        TranslatorEngine.DEEPL,
        TranslatorEngine.YOUDAO_PICTRANS,
        TranslatorEngine.GOOGLE,
        TranslatorEngine.LINGVA,
        TranslatorEngine.MYMEMORY,
        TranslatorEngine.LIBRETRANSLATE,
        TranslatorEngine.NIUTRANS,
        TranslatorEngine.VOLC,
        TranslatorEngine.BAIDU_FANYI,
        TranslatorEngine.TENCENT,
    )

    private val retryableMarkers = listOf(
        "timeout",
        "timed out",
        "http 408",
        "http 425",
        "http 429",
        "http 500",
        "http 502",
        "http 503",
        "http 504",
        "too many requests",
        "temporarily unavailable",
        "connection reset",
        "connection refused",
    )

    private const val FIRST_RETRY_ATTEMPT = 1
}
