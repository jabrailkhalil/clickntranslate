// Modified for Click'n'Translate on October 3, 2026.
package dev.clickn.translate.translate

import dev.clickn.translate.data.Settings
import java.util.LinkedHashMap
import java.security.MessageDigest

/**
 * 译文缓存：key = 原文 + 模型 + 目标语 + prompt 哈希。
 * 命中率高的话 token 消耗能压一大截，galgame 同句重复出现的场景特别明显。
 */
class TranslationCache(capacity: Int = 256) {
    init {
        require(capacity > 0) { "capacity must be positive" }
    }

    private val cache = object : LinkedHashMap<String, String>(capacity, 0.75f, true) {
        override fun removeEldestEntry(eldest: MutableMap.MutableEntry<String, String>?): Boolean =
            size > capacity
    }

    fun key(source: String, model: String, targetLang: String, prompt: String): String {
        // String.hashCode collides for ordinary texts such as "Aa" and "BB".
        // Length-prefix each field so separators inside custom prompts remain unambiguous.
        val digest = MessageDigest.getInstance("SHA-256")
        for (field in arrayOf(model, targetLang, prompt, source)) {
            val bytes = field.toByteArray(Charsets.UTF_8)
            for (shift in 24 downTo 0 step 8) digest.update((bytes.size ushr shift).toByte())
            digest.update(bytes)
        }
        return digest.digest().joinToString("") { (it.toInt() and 255).toString(16).padStart(2, '0') }
    }

    fun get(key: String, settings: Settings): String? {
        if (!TranslationCachePolicy.isEnabled(settings)) return null
        return synchronized(cache) { cache[key] }
    }

    fun put(key: String, value: String, settings: Settings) {
        if (!TranslationCachePolicy.shouldCache(settings, value)) return
        synchronized(cache) { cache[key] = value }
    }

    fun remove(key: String) {
        synchronized(cache) { cache.remove(key) }
    }

    fun clear() {
        synchronized(cache) { cache.clear() }
    }
}

internal object TranslationCachePolicy {
    fun isEnabled(settings: Settings): Boolean = isEnabled(
        developerOptionsEnabled = settings.developerOptionsEnabled,
        disableTranslationCache = settings.disableTranslationCache,
    )

    fun isEnabled(
        developerOptionsEnabled: Boolean,
        disableTranslationCache: Boolean,
    ): Boolean = !(developerOptionsEnabled && disableTranslationCache)

    fun shouldCache(settings: Settings, value: String): Boolean =
        isEnabled(settings) && value.isNotBlank()
}
