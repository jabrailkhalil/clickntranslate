package dev.clickn.translate.llm

import android.system.Os
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.filters.SdkSuppress
import androidx.test.platform.app.InstrumentationRegistry
import com.arm.aichat.AiChat
import com.arm.aichat.InferenceEngine
import dev.clickn.translate.data.RuntimeTranslationPromptContext
import dev.clickn.translate.translate.HyMt2PromptPolicy
import java.io.File
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeout
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Assume.assumeTrue
import org.junit.Test
import org.junit.runner.RunWith

/** Opt-in: a pinned model and host-rendered reference are staged in our QA cache first. */
@RunWith(AndroidJUnit4::class)
@SdkSuppress(minSdkVersion = 33)
class LocalLlmTemplateIntegrationTest {
    @Test
    fun pinnedGgufTemplateMatchesTokenBudgetAndIndependentNativeGeneration() = runBlocking {
        assumeTrue(
            "Needs the explicitly staged, owned native fixture; no download is performed.",
            InstrumentationRegistry.getArguments().getString("ownedNativeFixture") == "hymt183",
        )
        val context = InstrumentationRegistry.getInstrumentation().targetContext
        assertEquals("This fixture must never touch the production package.", "dev.clickn.translate.debug", context.packageName)
        val directory = File(context.cacheDir, "hymt183")
        val contract = JSONObject(File(directory, "contract.json").readText())
        assertEquals("OWNED_HYMT183_TEMPLATE_REPLAY", contract.getString("scope"))
        val kind = LlmModelKind.HY_MT2_1_8B_Q4_K_M
        assertEquals(kind.expectedSha256, contract.getString("model_sha256"))
        val model = File(directory, kind.fileName)
        assertEquals(kind.expectedSizeBytes, model.length())
        val rows = contract.getJSONArray("cases")
        assertEquals(3, rows.length())
        val prompts = (0 until rows.length()).map { index ->
            val row = rows.getJSONObject(index)
            HyMt2PromptPolicy.build(row.getString("source"), "ru", RuntimeTranslationPromptContext()).also {
                assertEquals("Use the actual application prompt policy.", row.getString("prompt"), it)
            }
        }
        val environment = LocalLlmSamplingPolicy.nativeEnvironment(kind) +
            LocalLlmThreadPolicy.nativeEnvironment(LocalLlmThreadConfig(2, 2)) +
            (LocalLlmAccelerationPolicy.VULKAN_OFFLOAD_ENV to "0")
        val previous = environment.keys.associateWith(System::getenv)
        val report = JSONObject().put("fixtureOnly", true).put("modelSha256", kind.expectedSha256)
        var engine: InferenceEngine? = null
        var assertionsPassed = false
        try {
            withContext(Dispatchers.IO) {
                withTimeout(360_000) {
                    environment.forEach { (key, value) -> Os.setenv(key, value, true) }
                    val active = AiChat.getInferenceEngine(context)
                    engine = active
                    active.loadModel(model.absolutePath)
                    val counts = prompts.map(LlamaPromptMetrics::countUserPromptTokens)
                    report.put("promptTokens", JSONArray(counts))
                    counts.forEachIndexed { index, count ->
                        assertEquals(
                            "JNI prefill count must use the pinned GGUF Jinja reference, not legacy heuristics.",
                            rows.getJSONObject(index).getInt("input_tokens"), count,
                        )
                    }
                    val batchTokens = LlamaPromptMetrics.effectiveUserPromptBatchTokens(prompts.toTypedArray())
                    report.put("effectiveBatchTokens", batchTokens)
                    assertTrue(batchTokens in counts.max()..counts.sum())
                    val single = StringBuilder()
                    active.sendUserPrompt(prompts.last(), 96).collect { single.append(it) }
                    report.put("singleEnglishToRussian", single.toString())
                    assertTrue("Single generation must return Russian text.", single.any { it in '\u0400'..'\u04ff' })
                    val batch = LlamaMultiSequence.generateWithMetrics(prompts, List(prompts.size) { 160 })
                    assertNotNull("The actual independent JNI batch must complete.", batch)
                    val outputs = requireNotNull(batch).outputs
                    report.put("batchOutputs", JSONArray(outputs))
                    assertEquals(prompts.size, outputs.size)
                    outputs.forEach { output ->
                        assertTrue(output.isNotBlank() && output.any { it in '\u0400'..'\u04ff' })
                        assertTrue("A generation boundary must not be shown as a translation.", !output.contains("<|clicktranslate_"))
                    }
                    assertTrue("The independent train request must not contain the Arabic story.",
                        !outputs.last().contains("книг", ignoreCase = true) &&
                            !outputs.last().contains("лисен", ignoreCase = true) &&
                            !outputs.last().contains("лисён", ignoreCase = true))
                    assertEquals("Metrics must still describe the next isolated request after a single generation.",
                        counts.first(), LlamaPromptMetrics.countUserPromptTokens(prompts.first()))
                    assertionsPassed = true
                }
            }
        } finally {
            report.put("assertionsPassed", assertionsPassed)
            var destroyed = false
            try {
                engine?.destroy()
                destroyed = true
            } finally {
                previous.forEach { (key, value) ->
                    if (value == null) Os.unsetenv(key) else Os.setenv(key, value, true)
                }
                report.put("engineDestroyed", destroyed)
                File(directory, "android-result.json").writeText(report.toString(2))
                println(report.toString())
            }
        }
    }
}
