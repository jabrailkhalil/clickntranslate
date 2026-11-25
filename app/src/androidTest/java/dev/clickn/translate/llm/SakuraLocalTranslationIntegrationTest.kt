package dev.clickn.translate.llm

import android.content.ContextWrapper
import android.os.Debug
import android.os.SystemClock
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.filters.SdkSuppress
import androidx.test.platform.app.InstrumentationRegistry
import dev.clickn.translate.data.LogRepository
import dev.clickn.translate.data.Settings
import dev.clickn.translate.data.SettingsRepository
import dev.clickn.translate.data.SettingsSecretCipher
import dev.clickn.translate.data.SettingsStorage
import dev.clickn.translate.data.TranslatorEngine
import dev.clickn.translate.download.ModelFileDownloader
import dev.clickn.translate.translate.SakuraGalTranslator
import dev.clickn.translate.translate.TranslationCache
import dev.clickn.translate.util.RuntimePerformanceDiagnostics
import java.io.File
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeout
import okhttp3.OkHttpClient
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Assume.assumeTrue
import org.junit.Test
import org.junit.runner.RunWith

/** Two uncached translations through the ordinary offline translator in an opt-in QA directory. */
@RunWith(AndroidJUnit4::class)
@SdkSuppress(minSdkVersion = 33)
class SakuraLocalTranslationIntegrationTest {
    @Test
    fun stagedModelTranslatesTwoJapaneseRequestsToChineseAndUnloads() = runBlocking<Unit> {
        assumeTrue(InstrumentationRegistry.getArguments().getString("ownedNativeFixture") == "sakura183")
        val app = InstrumentationRegistry.getInstrumentation().targetContext
        assertEquals("dev.clickn.translate.debug", app.packageName)
        val root = File(app.cacheDir, "sakura183")
        val context = object : ContextWrapper(app) {
            override fun getFilesDir() = root
        }
        val kind = LlmModelKind.SAKURA_1_5B_Q4
        val model = File(root, "models/llm/${kind.fileName}")
        assertEquals("Stage the pinned model in the QA cache first.", kind.expectedSizeBytes, model.length())
        val settingsStorage = SettingsStorage(File(root, "isolated.preferences_pb"))
        val unusedCipher = object : SettingsSecretCipher {
            override fun encrypt(plainText: String): String = error("Offline fixture uses no credentials")
            override fun decrypt(cipherText: String): String = error("Offline fixture uses no credentials")
        }
        val repository = SettingsRepository(context, unusedCipher, settingsStorage.dataStore)
        val offlineClient = OkHttpClient.Builder().addInterceptor {
            error("The staged local translator must never need a download")
        }.build()
        val installer = LlmModelInstaller(context, ModelFileDownloader(offlineClient), repository)
        val holder = LlamaEngineHolder(context, installer, LocalLlmDeviceCapability())
        val logs = LogRepository()
        val translator = SakuraGalTranslator(holder, TranslationCache(), RuntimePerformanceDiagnostics(logs), logs)
        val settings = Settings(
            sourceLang = "ja", targetLang = "zh-CN", translatorEngine = TranslatorEngine.LOCAL_SAKURA,
            disableTranslationCache = true, localLlmMaxNewTokens = 64,
        )
        val rows = JSONArray()
        val report = JSONObject().put("fixtureOnly", true).put("model", model.name).put("cases", rows)
        val memory = JSONArray()
        report.put("modelBytes", model.length()).put("memorySamples", memory)
        fun sample(stage: String, unloadedAt: Long? = null): JSONObject =
            processMemory(model).apply {
                put("stage", stage)
                if (unloadedAt != null) put("msSinceUnload", SystemClock.elapsedRealtime() - unloadedAt)
                memory.put(this)
            }
        report.put("pssBeforeKb", sample("beforeLoad").getLong("pssKb"))
        try {
            withContext(Dispatchers.IO) {
                withTimeout(180_000) {
                    val sources = listOf("明日の朝、駅で会いましょう。", "窓を閉めてください。")
                    for ((index, source) in sources.withIndex()) {
                        val started = SystemClock.elapsedRealtime()
                        val output = translator.translate(source, settings).orEmpty()
                        rows.put(JSONObject().put("source", source).put("output", output)
                            .put("elapsedMs", SystemClock.elapsedRealtime() - started))
                        assertEquals(kind, holder.currentKind)
                        assertTrue("Expected Chinese for: $source; got: $output", output.isNotBlank() && output != source)
                        if (index == 0) {
                            assertTrue("Tomorrow's meeting at the station: $output",
                                ("明天" in output || "明早" in output || "明晨" in output) && '站' in output &&
                                    ("见" in output || "碰面" in output || "会合" in output || "集合" in output))
                        } else {
                            assertTrue("A request to close the window: $output",
                                '窗' in output && ("关" in output || "闭" in output || "合上" in output))
                        }
                    }
                }
            }
            report.put("assertionsPassed", true)
        } finally {
            report.put("pssBeforeUnloadKb", sample("beforeUnload").getLong("pssKb"))
            try {
                holder.unload()
                val unloadedAt = SystemClock.elapsedRealtime()
                assertNull(holder.currentKind)
                report.put("modelReleased", true)
                    .put("pssAfterUnloadKb", sample("afterUnload", unloadedAt).getLong("pssKb"))
                for (offset in listOf(100L, 600L, 2_000L)) {
                    delay((offset - (SystemClock.elapsedRealtime() - unloadedAt)).coerceAtLeast(0L))
                    sample("after${offset}ms", unloadedAt)
                }
            } finally {
                settingsStorage.closeAndJoin()
                File(root, "android-result.json").writeText(report.toString(2))
            }
        }
    }

    /** Only aggregate memory counters from this instrumentation process are retained. */
    private fun processMemory(model: File): JSONObject {
        val info = Debug.MemoryInfo()
        Debug.getMemoryInfo(info)
        val snapshot = JSONObject().put("pssKb", Debug.getPss()).put("nativePssKb", info.nativePss)
            .put("dalvikPssKb", info.dalvikPss).put("otherPssKb", info.otherPss)
            .put("nativeHeapAllocatedKb", Debug.getNativeHeapAllocatedSize() / 1024)
            .put("nativeHeapFreeKb", Debug.getNativeHeapFreeSize() / 1024)
        val kernel = JSONObject()
        val fields = setOf("Rss", "Pss", "Pss_Anon", "Pss_File", "Pss_Shmem", "Private_Clean", "Private_Dirty", "SwapPss")
        val rollupRead = runCatching {
            File("/proc/self/smaps_rollup").forEachLine { line ->
                val key = line.substringBefore(':')
                if (key in fields) kernel.put(key, line.substringAfter(':').trim().substringBefore(' ').toLong())
            }
        }.isSuccess
        snapshot.put("rollupAvailable", rollupRead).put("rollupKb", kernel)
        var mappings = 0
        var bytes = 0L
        val mapsRead = runCatching {
            File("/proc/self/maps").forEachLine { line ->
                if (line.removeSuffix(" (deleted)").endsWith("/${model.name}")) {
                    val range = line.substringBefore(' ')
                    bytes += range.substringAfter('-').toLong(16) - range.substringBefore('-').toLong(16)
                    mappings++
                }
            }
        }.isSuccess
        snapshot.put("mapsAvailable", mapsRead)
        if (mapsRead) snapshot.put("ggufMappings", mappings).put("ggufMappedKb", bytes / 1024)
        return snapshot
    }
}
