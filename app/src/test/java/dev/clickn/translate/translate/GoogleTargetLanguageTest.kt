package dev.clickn.translate.translate

import android.content.ContextWrapper
import dev.clickn.translate.data.Settings
import java.util.Locale
import kotlinx.coroutines.runBlocking
import kotlinx.serialization.json.Json
import okhttp3.*
import okhttp3.ResponseBody.Companion.toResponseBody
import org.junit.Assert.*
import org.junit.Test

class GoogleTargetLanguageTest {
    @Test fun requestsUseUserLanguageForInvalidTargetsAndPreserveExplicitTargets() = runBlocking {
        val previous = Locale.getDefault()
        try {
            Locale.setDefault(Locale.forLanguageTag("ru"))
            val requested = mutableListOf<String?>()
            val client = OkHttpClient.Builder().addInterceptor { chain ->
                requested += chain.request().url.queryParameter("tl")
                Response.Builder().request(chain.request()).protocol(Protocol.HTTP_1_1).code(200).message("OK")
                    .body("""[[["translated","hello"]],null,"en"]""".toResponseBody()).build()
            }.build()
            val translator = GoogleTranslator(ContextWrapper(null), client, Json, TranslationCache())
            listOf("" to "ru", " AUTO " to "ru", "zh-CN" to "zh-CN", "fr-FR" to "fr").forEach { (input, expected) ->
                val settings = Settings(targetLang = input, developerOptionsEnabled = true, disableTranslationCache = true)
                assertEquals("translated", translator.translate("hello", settings))
                assertEquals(expected, requested.last())
                assertTrue(translator.testConnection(settings).success)
                assertEquals(expected, requested.last())
            }
            assertEquals(8, requested.size)
        } finally { Locale.setDefault(previous) }
    }
}
