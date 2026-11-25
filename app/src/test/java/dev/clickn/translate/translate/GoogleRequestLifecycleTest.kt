package dev.clickn.translate.translate

import android.content.ContextWrapper
import dev.clickn.translate.data.Settings
import java.io.IOException
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import kotlinx.coroutines.*
import kotlinx.serialization.json.*
import okhttp3.*
import okhttp3.ResponseBody.Companion.toResponseBody
import org.junit.Assert.*
import org.junit.Test

class GoogleRequestLifecycleTest {
    @Test fun longUnicodeTextUsesBoundedRequestsWithoutLosingParagraphs() = runBlocking {
        val requests = mutableListOf<String>()
        val client = OkHttpClient.Builder().addInterceptor { chain ->
            val text = chain.request().url.queryParameter("q")!!
            synchronized(requests) { requests += text }
            val response = buildJsonArray { add(buildJsonArray { add(buildJsonArray { add(text); add(text) }) }) }
            Response.Builder().request(chain.request()).protocol(Protocol.HTTP_1_1).code(200).message("OK")
                .body(response.toString().toResponseBody()).build()
        }.build()
        try {
            val source = "Arabic مرحبا and emoji 😀.\n\n".repeat(220)
            val translator = GoogleTranslator(ContextWrapper(null), client, Json, TranslationCache())
            assertEquals(source.trim(), translator.translate(source, Settings(sourceLang = "en", targetLang = "ru")))
            assertTrue(requests.size > 1)
            requests.forEach { assertTrue(it.toByteArray(Charsets.UTF_8).size <= 1800) }
        } finally { client.dispatcher.executorService.shutdown(); client.connectionPool.evictAll() }
    }

    @Test fun obsoleteRequestCancelsItsHttpCall() = runBlocking {
        val started = CountDownLatch(1)
        val cancelled = CountDownLatch(1)
        val release = CountDownLatch(1)
        val client = OkHttpClient.Builder().eventListener(object : EventListener() {
            override fun canceled(call: Call) { cancelled.countDown() }
        }).addInterceptor {
            started.countDown()
            release.await(3, TimeUnit.SECONDS)
            throw IOException("request cancelled")
        }.build()
        val translator = GoogleTranslator(ContextWrapper(null), client, Json, TranslationCache())
        val work = launch(Dispatchers.Default) { translator.translate("Hello", Settings()) }
        try {
            assertTrue(started.await(3, TimeUnit.SECONDS))
            work.cancelAndJoin()
            assertTrue(cancelled.await(3, TimeUnit.SECONDS))
        } finally { release.countDown(); client.dispatcher.executorService.shutdown(); client.connectionPool.evictAll() }
    }
}
