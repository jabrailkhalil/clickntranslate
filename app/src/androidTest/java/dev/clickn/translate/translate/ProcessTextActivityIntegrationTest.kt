package dev.clickn.translate.translate

import android.app.Activity
import android.content.Intent
import android.os.SystemClock
import androidx.test.core.app.ActivityScenario
import androidx.test.espresso.Espresso.onView
import androidx.test.espresso.NoMatchingViewException
import androidx.test.espresso.action.ViewActions.click
import androidx.test.espresso.assertion.ViewAssertions.matches
import androidx.test.espresso.matcher.RootMatchers.isDialog
import androidx.test.espresso.matcher.ViewMatchers.isDisplayed
import androidx.test.espresso.matcher.ViewMatchers.withText
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import dev.clickn.translate.ClickTranslateApp
import dev.clickn.translate.R
import dev.clickn.translate.data.TranslatorEngine
import java.net.InetAddress
import java.util.concurrent.TimeUnit
import kotlinx.coroutines.runBlocking
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class ProcessTextActivityIntegrationTest {
    @Test fun editableSelectionReturnsOnlyTheReviewedTranslationOnReplace() {
        reviewSelection("Open the blue door.", replace = true)
    }

    @Test fun cancelReturnsNoReplacementToTheEditingApp() {
        reviewSelection("Leave this selection intact.", replace = false)
    }

    private fun reviewSelection(source: String, replace: Boolean) {
        val context = InstrumentationRegistry.getInstrumentation().targetContext
        val settings = (context.applicationContext as ClickTranslateApp).settingsRepository
        val previous = runBlocking { settings.get() }
        val translation = "Проверенный перевод — точно как на экране."
        MockWebServer().use { server ->
            server.start(InetAddress.getByName("127.0.0.1"), 0)
            server.enqueue(MockResponse().setHeader("Content-Type", "application/json")
                .setBody(JSONObject().put("translatedText", translation).toString()))
            try {
                runBlocking {
                    settings.update { it.copy(translatorEngine = TranslatorEngine.LIBRETRANSLATE,
                        sourceLang = "en", targetLang = "ru", libreTranslateApiKey = "",
                        libreTranslateBaseUrl = "http://127.0.0.1:${server.port}") }
                }
                val intent = Intent(Intent.ACTION_PROCESS_TEXT).apply {
                    setPackage(context.packageName)
                    addCategory(Intent.CATEGORY_DEFAULT)
                    type = "text/plain"
                    putExtra(Intent.EXTRA_PROCESS_TEXT, source)
                    putExtra(Intent.EXTRA_PROCESS_TEXT_READONLY, false)
                }
                assertEquals(ProcessTextTranslateActivity::class.java.name, intent.resolveActivity(context.packageManager)?.className)
                ActivityScenario.launchActivityForResult<ProcessTextTranslateActivity>(intent).use { scenario ->
                    onView(withText(source)).inRoot(isDialog()).check(matches(isDisplayed()))
                    val request = requireNotNull(server.takeRequest(10, TimeUnit.SECONDS)) {
                        "The review screen did not contact the selected translator"
                    }
                    assertEquals("POST", request.method)
                    assertEquals("/translate", request.path)
                    val body = JSONObject(request.body.readUtf8())
                    assertEquals(source, body.getString("q"))
                    assertEquals("en", body.getString("source"))
                    assertEquals("ru", body.getString("target"))
                    awaitReviewText(translation)
                    val action = if (replace) R.string.process_text_replace else android.R.string.cancel
                    onView(withText(action)).inRoot(isDialog()).perform(click())
                    val result = scenario.result
                    if (replace) {
                        assertEquals(Activity.RESULT_OK, result.resultCode)
                        assertEquals(translation, result.resultData?.getCharSequenceExtra(Intent.EXTRA_PROCESS_TEXT)?.toString())
                    } else {
                        assertEquals(Activity.RESULT_CANCELED, result.resultCode)
                        assertNull(result.resultData?.getCharSequenceExtra(Intent.EXTRA_PROCESS_TEXT))
                    }
                    assertEquals(1, server.requestCount)
                }
            } finally {
                runBlocking {
                    settings.update { it.copy(translatorEngine = previous.translatorEngine, sourceLang = previous.sourceLang,
                        targetLang = previous.targetLang, libreTranslateBaseUrl = previous.libreTranslateBaseUrl,
                        libreTranslateApiKey = previous.libreTranslateApiKey) }
                }
            }
        }
    }

    private fun awaitReviewText(text: String) {
        val deadline = SystemClock.elapsedRealtime() + 10_000
        while (true) {
            try {
                onView(withText(text)).inRoot(isDialog()).check(matches(isDisplayed()))
                return
            } catch (missing: NoMatchingViewException) {
                if (SystemClock.elapsedRealtime() >= deadline) throw missing
                SystemClock.sleep(80)
            }
        }
    }
}
