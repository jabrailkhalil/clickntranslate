// Modified for Click'n'Translate on October 3, 2026.
package dev.clickn.translate.llm

import java.io.File
import org.junit.Assert.assertTrue
import org.junit.Test

class LocalLlmSamplingWiringTest {

    @Test
    fun modelProfile_reachesNativeSamplerBeforeModelLoad() {
        val holder = source("app/src/main/java/dev/clickn/translate/llm/LlamaEngineHolder.kt")
        val native = source("llama-android/src/main/cpp/llama_thread_policy.cpp")
        val cmake = source("llama-android/src/main/cpp/CMakeLists.txt")

        data class Case(val name: String, val source: String, val marker: String)
        listOf(
            Case("holder exports model profile", holder, "LocalLlmSamplingPolicy.nativeEnvironment(kind).forEach"),
            Case("holder overwrites stale variables", holder, "Os.setenv(name, value, true)"),
            Case("native reads temperature", native, "CLICKTRANSLATE_SAMPLER_TEMPERATURE"),
            Case("native reads top-p", native, "CLICKTRANSLATE_SAMPLER_TOP_P"),
            Case("native reads top-k", native, "CLICKTRANSLATE_SAMPLER_TOP_K"),
            Case("native reads repeat penalty", native, "CLICKTRANSLATE_SAMPLER_REPEAT_PENALTY"),
            Case("native applies top-k", native, "params.top_k = sampler_integer_from_environment"),
            Case("native applies repeat penalty", native, "params.penalty_repeat = sampler_value_from_environment"),
            Case("build redirects sampler construction", cmake, "common_sampler_init=clicktranslate_common_sampler_init"),
        ).forEach { case -> assertTrue(case.name, case.source.contains(case.marker)) }
    }

    private fun source(path: String): String = listOf(
        File("../$path"),
        File(path),
    ).firstOrNull(File::isFile)?.readText() ?: error("Source not found: $path")
}
