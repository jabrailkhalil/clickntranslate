package dev.clickn.translate.translate

import dev.clickn.translate.data.Settings
import dev.clickn.translate.data.TranslatorEngine
import dev.clickn.translate.data.withApiTimeout
import java.io.IOException
import javax.inject.Inject
import javax.inject.Singleton
import kotlin.coroutines.resume
import kotlin.coroutines.resumeWithException
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.flow
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlinx.serialization.json.*
import okhttp3.*
import okhttp3.HttpUrl.Companion.toHttpUrlOrNull
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.RequestBody.Companion.toRequestBody

/** Transport shared by the three online services offered in Click'n'Translate. */
@Singleton
class CommunityTranslationClient @Inject constructor(
    private val http: OkHttpClient,
    private val json: Json,
) {
    suspend fun translate(text: String, settings: Settings): String {
        require(settings.translatorEngine in COMMUNITY_ENGINES)
        val source = if (settings.translatorEngine == TranslatorEngine.MYMEMORY) settings.sourceLang else providerLanguageCode(settings.sourceLang)
        val target = if (settings.translatorEngine == TranslatorEngine.MYMEMORY) settings.targetLang else providerLanguageCode(settings.targetLang)
        require(target != "auto") { "Choose a target language" }
        require(source != "auto" || settings.translatorEngine != TranslatorEngine.MYMEMORY) {
            "MyMemory needs an explicit source language"
        }
        val limit = if (settings.translatorEngine == TranslatorEngine.MYMEMORY) 500 else 1800
        return buildString { for (chunk in splitProviderText(text, limit)) {
            val content = chunk.trim()
            append(if (content.isEmpty()) chunk else {
                val translated = request(content, source, target, settings)
                chunk.takeWhile(Char::isWhitespace) + translated + chunk.takeLastWhile(Char::isWhitespace)
            })
        } }
    }

    private suspend fun request(text: String, source: String, target: String, settings: Settings): String {
        val request = when (settings.translatorEngine) {
            TranslatorEngine.MYMEMORY -> Request.Builder().url(
                "https://api.mymemory.translated.net/get".toHttpUrlOrNull()!!.newBuilder()
                    .addQueryParameter("q", text).addQueryParameter("langpair", "$source|$target")
                    .apply { if (settings.myMemoryEmail.isNotBlank()) addQueryParameter("de", settings.myMemoryEmail.trim()) }
                    .build(),
            ).build()
            TranslatorEngine.LIBRETRANSLATE -> {
                val body = buildJsonObject {
                    put("q", text); put("source", source); put("target", target); put("format", "text")
                    if (settings.libreTranslateApiKey.isNotBlank()) put("api_key", settings.libreTranslateApiKey.trim())
                }
                Request.Builder().url(providerBaseUrl(settings.libreTranslateBaseUrl).newBuilder()
                    .addPathSegment("translate").build())
                    .post(body.toString().toRequestBody("application/json".toMediaType())).build()
            }
            TranslatorEngine.LINGVA -> {
                val base = providerBaseUrl(settings.lingvaBaseUrl)
                if ('/' in text) {
                    val body = buildJsonObject {
                        put("query", "query (\$source: String, \$target: String, \$text: String!) { translation(source: \$source, target: \$target, query: \$text) { target { text } } }")
                        put("variables", buildJsonObject { put("source", source); put("target", target); put("text", text) })
                    }
                    Request.Builder().url(base.newBuilder().addPathSegments("api/graphql").build())
                        .post(body.toString().toRequestBody("application/json".toMediaType())).build()
                } else Request.Builder().url(base.newBuilder().addPathSegments("api/v1")
                    .addPathSegment(source).addPathSegment(target).addPathSegment(text).build()).build()
            }
            else -> error("Unsupported service")
        }
        val client = http.withApiTimeout(settings.apiTimeoutSeconds).newBuilder()
            .followRedirects(false).followSslRedirects(false).build()
        val payload = client.newCall(request).awaitCommunityPayload(json)
        val result = when (settings.translatorEngine) {
            TranslatorEngine.MYMEMORY -> {
                check(payload["responseStatus"]?.jsonPrimitive?.content == "200") { "MyMemory rejected the request" }
                decodeTranslationEntities(payload["responseData"]?.jsonObject?.get("translatedText")?.jsonPrimitive?.content.orEmpty())
            }
            TranslatorEngine.LIBRETRANSLATE -> payload["translatedText"]?.jsonPrimitive?.content.orEmpty()
            TranslatorEngine.LINGVA -> {
                check(payload["errors"] == null) { "Lingva rejected the request" }
                payload["translation"]?.jsonPrimitive?.content
                    ?: payload["data"]?.jsonObject?.get("translation")?.jsonObject?.get("target")?.jsonObject?.get("text")?.jsonPrimitive?.content.orEmpty()
            }
            else -> error("Unsupported service")
        }
        check(result.isNotBlank()) { "Service returned an empty translation" }
        return result
    }
}

internal fun providerBaseUrl(value: String): HttpUrl {
    val url = value.trim().trimEnd('/').plus('/').toHttpUrlOrNull()
        ?: throw IllegalArgumentException("Enter a valid server URL")
    require(url.username.isEmpty() && url.password.isEmpty() && url.query == null && url.fragment == null) {
        "Server URL must not contain credentials, query parameters or a fragment"
    }
    return url
}

internal fun providerLanguageCode(value: String): String = when (value.lowercase()) {
    "", "auto" -> "auto"
    "zh", "zh-cn", "zh-hans" -> "zh"
    "zh-tw", "zh-hant" -> "zh-TW"
    else -> value.lowercase().substringBefore('-')
}

/** Split at word boundaries without dropping whitespace or breaking UTF-16 surrogate pairs. */
internal fun splitProviderText(value: String, byteLimit: Int): List<String> {
    require(byteLimit >= 4)
    val chunks = mutableListOf<String>()
    var start = 0
    while (start < value.length) {
        var end = start
        var bytes = 0
        var boundary = -1
        while (end < value.length) {
            val codePoint = value.codePointAt(end)
            val next = end + Character.charCount(codePoint)
            val size = value.substring(end, next).toByteArray(Charsets.UTF_8).size
            if (bytes + size > byteLimit) break
            bytes += size
            end = next
            if (Character.isWhitespace(codePoint)) boundary = end
        }
        if (end < value.length && boundary > start) end = boundary
        chunks += value.substring(start, end)
        start = end
    }
    return chunks
}

internal fun decodeTranslationEntities(value: String): String = Regex("&(#x[0-9a-fA-F]+|#[0-9]+|amp|lt|gt|quot|apos);?")
    .replace(value) { match ->
        when (val entity = match.groupValues[1]) {
            "amp" -> "&"; "lt" -> "<"; "gt" -> ">"; "quot" -> "\""; "apos" -> "'"
            else -> runCatching {
                val point = if (entity.startsWith("#x")) entity.drop(2).toInt(16) else entity.drop(1).toInt()
                String(Character.toChars(point))
            }.getOrDefault(match.value)
        }
    }

private suspend fun Call.awaitCommunityPayload(json: Json): JsonObject = suspendCancellableCoroutine { continuation ->
    continuation.invokeOnCancellation { cancel() }
    enqueue(object : Callback {
        override fun onFailure(call: Call, e: IOException) { if (continuation.isActive) continuation.resumeWithException(e) }
        override fun onResponse(call: Call, response: Response) {
            // Read and parse on OkHttp's worker thread. Cancellation closes the socket even
            // after headers arrived, while a slow or oversized body is still being read.
            try {
                val payload = response.use {
                    check(it.isSuccessful) { "Translation service: HTTP ${it.code}" }
                    val body = it.body?.source() ?: error("Empty service response")
                    check(!body.request(1_048_577)) { "Service response is too large" }
                    json.parseToJsonElement(body.readUtf8()).jsonObject
                }
                if (continuation.isActive) continuation.resume(payload)
            } catch (error: Exception) {
                if (continuation.isActive) continuation.resumeWithException(error)
            }
        }
    })
}

val COMMUNITY_ENGINES = setOf(TranslatorEngine.LINGVA, TranslatorEngine.MYMEMORY, TranslatorEngine.LIBRETRANSLATE)

@Singleton
class CommunityTranslator @Inject constructor(
    private val transport: CommunityTranslationClient,
    private val cache: TranslationCache,
) : Translator {
    override suspend fun translate(source: String, settings: Settings): String? {
        if (source.isBlank()) return null
        val server = when (settings.translatorEngine) {
            TranslatorEngine.LINGVA -> settings.lingvaBaseUrl
            TranslatorEngine.LIBRETRANSLATE -> settings.libreTranslateBaseUrl
            else -> "mymemory"
        }
        val key = cache.key(source, "${settings.translatorEngine}:$server", settings.targetLang, settings.sourceLang)
        cache.get(key, settings)?.let { return it }
        return transport.translate(source, settings).also { cache.put(key, it, settings) }
    }
    override fun translateStream(source: String, settings: Settings): Flow<String> = flow { translate(source, settings)?.let { emit(it) } }
    override suspend fun testConnection(settings: Settings): TestResult = try {
        TestResult(true, transport.translate("Hello", settings.copy(sourceLang = "en")))
    } catch (cancelled: CancellationException) { throw cancelled }
    catch (error: Exception) { TestResult(false, error.message ?: "Service unavailable") }
}
