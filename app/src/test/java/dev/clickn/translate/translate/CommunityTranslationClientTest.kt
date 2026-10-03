package dev.clickn.translate.translate

import dev.clickn.translate.data.Settings
import dev.clickn.translate.data.TranslatorEngine
import java.io.IOException
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import kotlinx.coroutines.*
import kotlinx.serialization.json.*
import okhttp3.*
import okhttp3.ResponseBody.Companion.toResponseBody
import okio.Buffer
import org.junit.Assert.*
import org.junit.Test

class CommunityTranslationClientTest {
    private val json = Json { ignoreUnknownKeys = true }
    private fun client(response: String, status: Int = 200, inspect: (Request) -> Unit = {}): CommunityTranslationClient =
        CommunityTranslationClient(OkHttpClient.Builder().addInterceptor { chain ->
            inspect(chain.request())
            Response.Builder().request(chain.request()).protocol(Protocol.HTTP_1_1).code(status).message("test")
                .body(response.toResponseBody()).build()
        }.build(), json)

    @Test fun libreUsesOnlyItsOwnKeyAndSelectedHost() = runBlocking {
        val transport = client("""{"translatedText":"Bonjour"}""") { request ->
            assertEquals("https://my-server.example/custom/translate", request.url.toString())
            assertEquals("POST", request.method)
            val body = json.parseToJsonElement(Buffer().apply { request.body!!.writeTo(this) }.readUtf8()).jsonObject
            assertEquals("own-key", body["api_key"]!!.jsonPrimitive.content)
            assertEquals("auto", body["source"]!!.jsonPrimitive.content)
            assertEquals("zh", body["target"]!!.jsonPrimitive.content)
            assertFalse(body.toString().contains("other-secret"))
        }
        assertEquals("Bonjour", transport.translate("Hello", Settings(translatorEngine = TranslatorEngine.LIBRETRANSLATE,
            libreTranslateBaseUrl = "https://my-server.example/custom/", libreTranslateApiKey = "own-key", apiKey = "other-secret")))
    }

    @Test fun libreOmitsAnEmptyOptionalKey(): Unit = runBlocking {
        client("""{"translatedText":"Hola"}""") { request ->
            val body = Buffer().apply { request.body!!.writeTo(this) }.readUtf8()
            assertFalse(body.contains("api_key"))
        }.translate("Hello", Settings(translatorEngine = TranslatorEngine.LIBRETRANSLATE))
    }

    @Test fun lingvaEncodesSpecialCharactersAsOneSegment() = runBlocking {
        val transport = client("""{"translation":"Привет"}""") { request ->
            assertEquals(listOf("api", "v1", "auto", "ru", "Hi? # + & 😀"), request.url.pathSegments)
            assertNull(request.url.query)
            assertNull(request.url.fragment)
        }
        assertEquals("Привет", transport.translate("Hi? # + & 😀", Settings(translatorEngine = TranslatorEngine.LINGVA, targetLang = "ru")))
    }

    @Test fun lingvaSlashTextUsesGraphqlVariables(): Unit = runBlocking {
        client("""{"data":{"translation":{"target":{"text":"répertoire"}}}}""") { request ->
            assertEquals("/api/graphql", request.url.encodedPath)
            val body = json.parseToJsonElement(Buffer().apply { request.body!!.writeTo(this) }.readUtf8()).jsonObject
            assertEquals("a/b \"quoted\"", body["variables"]!!.jsonObject["text"]!!.jsonPrimitive.content)
            assertFalse(body["query"]!!.jsonPrimitive.content.contains("quoted"))
        }.translate("a/b \"quoted\"", Settings(translatorEngine = TranslatorEngine.LINGVA, targetLang = "fr"))
    }

    @Test fun myMemoryChunksByUtf8BytesAndPreservesChineseLanguageTags() = runBlocking {
        var requests = 0
        val transport = client("""{"responseStatus":200,"responseData":{"translatedText":"OK &amp; &#x1F600;"}}""") { request ->
            requests++
            assertTrue(request.url.queryParameter("q")!!.toByteArray().size <= 500)
            assertEquals("en|zh-CN", request.url.queryParameter("langpair"))
            assertEquals("person@example.com", request.url.queryParameter("de"))
        }
        val result = transport.translate("😀".repeat(251), Settings(translatorEngine = TranslatorEngine.MYMEMORY,
            sourceLang = "en", myMemoryEmail = "person@example.com"))
        assertEquals(3, requests)
        assertEquals("OK & 😀".repeat(3), result)
    }

    @Test fun invalidConfigurationMakesNoNetworkRequest() = runBlocking {
        var requested = false
        val transport = client("{}") { requested = true }
        for (settings in listOf(
            Settings(translatorEngine = TranslatorEngine.MYMEMORY, sourceLang = "auto"),
            Settings(translatorEngine = TranslatorEngine.LIBRETRANSLATE, libreTranslateBaseUrl = "https://secret@server.example"),
            Settings(translatorEngine = TranslatorEngine.LINGVA, lingvaBaseUrl = "https://server.example?token=secret"),
        )) assertTrue(runCatching { transport.translate("Hello", settings) }.isFailure)
        assertFalse(requested)
    }

    @Test fun malformedEmptyAndProviderErrorResponsesFail() = runBlocking {
        val cases = listOf(
            TranslatorEngine.LINGVA to """{"errors":[{"message":"Denied"}]}""",
            TranslatorEngine.LINGVA to """{"translation":""}""",
            TranslatorEngine.LIBRETRANSLATE to """{"error":"Invalid key"}""",
            TranslatorEngine.MYMEMORY to """{"responseStatus":403,"responseData":{"translatedText":"invalid"}}""",
            TranslatorEngine.LIBRETRANSLATE to "not json",
            TranslatorEngine.LIBRETRANSLATE to "x".repeat(1_048_577),
        )
        for ((engine, body) in cases) assertTrue(engine.name, runCatching {
            client(body).translate("Hello", Settings(translatorEngine = engine, sourceLang = "en"))
        }.isFailure)
        assertTrue(runCatching { client("{}", 429).translate("Hi", Settings(translatorEngine = TranslatorEngine.LINGVA)) }.isFailure)
    }

    @Test fun whitespaceChunkingIsLosslessAndDoesNotSplitSurrogatePairs() {
        val text = "  word 😀\n".repeat(300) + "終"
        val chunks = splitProviderText(text, 500)
        assertEquals(text, chunks.joinToString(""))
        chunks.forEach { assertTrue(it.toByteArray().size <= 500); assertFalse(it.last().isHighSurrogate()); assertFalse(it.first().isLowSurrogate()) }
    }

    @Test fun cancelledRequestCancelsTheHttpCall() = runBlocking {
        val started = CountDownLatch(1)
        val cancelled = CountDownLatch(1)
        val release = CountDownLatch(1)
        val http = OkHttpClient.Builder().eventListener(object : EventListener() {
            override fun canceled(call: Call) { cancelled.countDown() }
        }).addInterceptor { chain ->
            started.countDown(); release.await(3, TimeUnit.SECONDS)
            throw IOException("cancelled test request")
        }.build()
        val work = launch(Dispatchers.Default) {
            CommunityTranslationClient(http, json).translate("Hi", Settings(translatorEngine = TranslatorEngine.LINGVA))
        }
        try {
            assertTrue(started.await(3, TimeUnit.SECONDS))
            work.cancelAndJoin()
            assertTrue(cancelled.await(3, TimeUnit.SECONDS))
        } finally { release.countDown(); http.dispatcher.executorService.shutdown() }
    }

    @Test fun cacheIsIsolatedByEngineAndServer() = runBlocking {
        var requests = 0
        val transport = client("""{"translation":"translated"}""") { requests++ }
        val translator = CommunityTranslator(transport, TranslationCache())
        val settings = Settings(translatorEngine = TranslatorEngine.LINGVA)
        translator.translate("Hello", settings)
        translator.translate("Hello", settings)
        translator.translate("Hello", settings.copy(lingvaBaseUrl = "https://another.example"))
        assertEquals(2, requests)
    }
}
