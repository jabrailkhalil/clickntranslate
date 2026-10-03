// Modified for Click'n'Translate on October 3, 2026.
package dev.clickn.translate.translate

import android.content.Context
import dev.clickn.translate.data.Settings
import dev.clickn.translate.data.withApiTimeout
import dev.clickn.translate.util.TencentSigner
import dagger.hilt.android.qualifiers.ApplicationContext
import javax.inject.Inject
import javax.inject.Singleton
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.flow
import kotlinx.coroutines.flow.flowOn
import kotlinx.coroutines.withContext
import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody

/**
 * 腾讯云机器翻译 TMT（tmt.tencentcloudapi.com）。
 *
 * 协议：POST JSON，`Action=TextTranslateBatch`（单段也走批接口，少一份代码），
 *      `Version=2018-03-21`。
 * 鉴权：TC3-HMAC-SHA256，复用 [TencentSigner.signTc3]。
 *
 * **账号复用**：`Settings.tencentSecretId / Key / Region` 与 [dev.clickn.translate.ocr.TencentOcrEngine]
 * 共用——属于同一个腾讯云账号体系，让用户填两遍只会困惑。Region 翻译服务支持
 * ap-beijing / ap-shanghai / ap-guangzhou / ap-hongkong / ap-seoul / na-siliconvalley / eu-frankfurt
 * 等；用户填的 OCR region 一般都能直接用。
 *
 * 批量限制：单次 TextTranslateBatch 最多 2000 字符。
 */
@Singleton
class TencentTranslator @Inject constructor(
    @ApplicationContext private val appContext: Context,
    private val client: OkHttpClient,
    private val json: Json,
    private val cache: TranslationCache
) : Translator {

    override val prefersBatch: Boolean get() = true

    override suspend fun translate(source: String, settings: Settings): String? {
        val trimmed = source.trim()
        if (trimmed.isEmpty()) return null
        return translateBatch(listOf(trimmed), settings).firstOrNull()
    }

    override suspend fun translateBatch(sources: List<String>, settings: Settings): List<String?> {
        if (sources.isEmpty()) return emptyList()
        validate(settings)

        val targetCode = mapLang(settings.targetLang) ?: (mapLang(dev.clickn.translate.data.defaultTranslationTarget()) ?: "en")
        val sourceCode = mapLang(settings.sourceLang) ?: "auto"

        val result = arrayOfNulls<String>(sources.size)
        val pending = mutableListOf<Int>()
        for ((i, raw) in sources.withIndex()) {
            val t = raw.trim()
            if (t.isEmpty()) {
                result[i] = null
                continue
            }
            val key = cache.key(t, "tencent-tmt-$targetCode", targetCode, "")
            val hit = cache.get(key, settings)
            if (hit != null) result[i] = hit
            else pending.add(i)
        }
        if (pending.isEmpty()) return result.toList()

        val payload = json.encodeToString(JsonObject.serializer(), buildJsonObject {
            put("Source", sourceCode)
            put("Target", targetCode)
            put("ProjectId", 0)
            put("SourceTextList", JsonArray(pending.map { JsonPrimitive(sources[it].trim()) }))
        })

        val region = settings.tencentRegion.ifBlank { "ap-guangzhou" }
        val headers = TencentSigner.signTc3(
            secretId = settings.tencentSecretId,
            secretKey = settings.tencentSecretKey,
            service = SERVICE,
            host = HOST,
            region = region,
            action = ACTION,
            version = VERSION,
            payload = payload
        )

        val body = payload.toRequestBody("application/json; charset=utf-8".toMediaType())
        val builder = Request.Builder().url("https://$HOST/").post(body)
        headers.forEach { (k, v) -> builder.header(k, v) }
        val request = builder.build()

        val timedClient = client.withApiTimeout(settings.apiTimeoutSeconds)
        val parsed = withContext(Dispatchers.IO) {
            timedClient.newCall(request).execute().use { r ->
                val raw = r.body?.string().orEmpty()
                if (!r.isSuccessful) {
                    throw TranslationException("Tencent TMT HTTP ${r.code}: ${raw.take(200)}")
                }
                runCatching { json.decodeFromString<TmtEnvelope>(raw) }
                    .getOrElse {
                        throw TranslationException("Tencent TMT response could not be parsed: ${raw.take(200)}", it)
                    }
            }
        }
        val response = parsed.response
            ?: throw TranslationException("Tencent TMT returned an empty response")
        if (response.error != null) {
            throw TranslationException(friendlyError(response.error))
        }
        val targets = response.targetTextList.orEmpty()
        for ((order, idx) in pending.withIndex()) {
            val text = targets.getOrNull(order)?.trim() ?: continue
            result[idx] = text
            val key = cache.key(sources[idx].trim(), "tencent-tmt-$targetCode", targetCode, "")
            cache.put(key, text, settings)
        }
        return result.toList()
    }

    override fun translateStream(source: String, settings: Settings): Flow<String> = flow {
        val full = translate(source, settings) ?: return@flow
        emit(full)
    }.flowOn(Dispatchers.IO)

    override suspend fun testConnection(settings: Settings): TestResult {
        if (settings.tencentSecretId.isBlank() || settings.tencentSecretKey.isBlank()) {
            return TestResult(false, "Tencent SecretId / SecretKey is missing (configure it in OCR settings)")
        }
        // 先翻一段 hello 验证翻译功能；再额外查一次账户余额作为顺带反馈。余额查询失败
        // **不**导致整体失败——子账号通常缺财务读权限（finance:DescribeAccountBalance），
        // 没必要让用户因为这个被拒登就以为翻译不可用。
        val translateResult = runCatching {
            val out = translate("hello", settings)
            if (out.isNullOrBlank()) Result.failure<String>(TranslationException("Empty response"))
            else Result.success(out)
        }.getOrElse { Result.failure(it) }

        if (translateResult.isFailure) {
            val e = translateResult.exceptionOrNull()
            return TestResult(false, e?.message ?: e?.javaClass?.simpleName ?: "Unknown error")
        }
        val sample = translateResult.getOrThrow().take(40)
        val balance = runCatching { queryBalance(settings) }.getOrNull()
        val msg = if (balance != null) {
            "OK balance: ¥%.2f; sample: %s".format(balance, sample)
        } else {
            "OK sample: $sample (balance access is optional)"
        }
        return TestResult(true, msg)
    }

    /**
     * 调腾讯云 billing.DescribeAccountBalance 拿账户人民币余额（单位：元）。
     * 需要子账号有 `finance:DescribeAccountBalance` 或预付费 / 后付费财务权限——
     * 默认主账号有，被精细化授权的子账号常常没有，这种情况下应当吞掉错误而不是抛。
     */
    private suspend fun queryBalance(settings: Settings): Double? {
        val payload = "{}"
        val headers = TencentSigner.signTc3(
            secretId = settings.tencentSecretId,
            secretKey = settings.tencentSecretKey,
            service = BILLING_SERVICE,
            host = BILLING_HOST,
            region = "",  // billing 不分 region，X-TC-Region 填空即可
            action = BILLING_ACTION,
            version = BILLING_VERSION,
            payload = payload
        )
        val body = payload.toRequestBody("application/json; charset=utf-8".toMediaType())
        val builder = Request.Builder().url("https://$BILLING_HOST/").post(body)
        headers.forEach { (k, v) -> builder.header(k, v) }
        val timedClient = client.withApiTimeout(settings.apiTimeoutSeconds)
        return withContext(Dispatchers.IO) {
            timedClient.newCall(builder.build()).execute().use { r ->
                val raw = r.body?.string().orEmpty()
                if (!r.isSuccessful) return@use null
                val parsed = runCatching { json.decodeFromString<BalanceEnvelope>(raw) }.getOrNull()
                val resp = parsed?.response ?: return@use null
                if (resp.error != null) return@use null
                // Balance 字段是分；RealBalance 是元（Double）。两者都返回，优先 RealBalance。
                resp.realBalance ?: resp.balance?.let { it / 100.0 }
            }
        }
    }

    private fun validate(settings: Settings) {
        if (settings.tencentSecretId.isBlank() || settings.tencentSecretKey.isBlank()) {
            throw TranslationException("Tencent SecretId / SecretKey is not configured (shared with OCR settings)")
        }
    }

    /**
     * 把腾讯 TMT 的常见错误码翻译成对用户更有用的提示。重点：
     * - `FailedOperation.UserNotRegistered` 表示账号还没在控制台开通 TMT 服务（最常见的首次使用错误）
     * - `FailedOperation.ServiceIsolate` 表示账号欠费 / 服务已隔离
     * - `AuthFailure.*` 表示 SecretId/Key 或权限策略问题
     */
    private fun friendlyError(error: ErrorBody): String {
        val code = error.code ?: "UnknownError"
        val raw = error.message ?: "No message"
        val hint = when {
            code == "FailedOperation.UserNotRegistered" ->
                "Enable the translation service at https://console.cloud.tencent.com/tmt and retry."
            code == "FailedOperation.ServiceIsolate" ->
                "Check your account balance and TMT service status in the Tencent console."
            code.startsWith("AuthFailure") ->
                "Check your SecretId / SecretKey and the QcloudTMTFullAccess policy."
            code == "RequestLimitExceeded" ->
                "Request rate limit exceeded. Retry later."
            else -> null
        }
        return if (hint != null) "Tencent translation $code: $raw\n→ $hint"
        else "Tencent translation $code: $raw"
    }

    /**
     * BCP-47 → 腾讯云 TMT 语言码（见 https://cloud.tencent.com/document/product/551/15619）。
     * 腾讯码绝大多数与 BCP-47 主码一致；繁中是 `zh-TW`。"auto" 返回 null（调用方填 "auto"）。
     */
    private fun mapLang(code: String): String? {
        val raw = code.trim()
        if (raw.isEmpty() || raw.equals("auto", true)) return null
        val lower = raw.lowercase()
        return when (lower) {
            "zh", "zh-cn", "zh-hans" -> "zh"
            "zh-tw", "zh-hant", "zh-hk" -> "zh-TW"
            "en", "en-us", "en-gb" -> "en"
            "pt", "pt-br", "pt-pt" -> "pt"
            else -> lower.substringBefore('-')
        }
    }

    companion object {
        private const val HOST = "tmt.tencentcloudapi.com"
        private const val SERVICE = "tmt"
        private const val VERSION = "2018-03-21"
        private const val ACTION = "TextTranslateBatch"
        // 账户余额查询（计费 API）：与 TMT 完全不同的服务域。
        private const val BILLING_HOST = "billing.tencentcloudapi.com"
        private const val BILLING_SERVICE = "billing"
        private const val BILLING_VERSION = "2018-07-09"
        private const val BILLING_ACTION = "DescribeAccountBalance"
    }

    @Serializable
    private data class TmtEnvelope(@SerialName("Response") val response: TmtResponse? = null)

    @Serializable
    private data class TmtResponse(
        @SerialName("Source") val source: String? = null,
        @SerialName("Target") val target: String? = null,
        @SerialName("TargetTextList") val targetTextList: List<String>? = null,
        @SerialName("RequestId") val requestId: String? = null,
        @SerialName("Error") val error: ErrorBody? = null
    )

    @Serializable
    private data class ErrorBody(
        @SerialName("Code") val code: String? = null,
        @SerialName("Message") val message: String? = null
    )

    @Serializable
    private data class BalanceEnvelope(@SerialName("Response") val response: BalanceResponse? = null)

    @Serializable
    private data class BalanceResponse(
        @SerialName("Balance") val balance: Long? = null,
        @SerialName("RealBalance") val realBalance: Double? = null,
        @SerialName("Uin") val uin: Long? = null,
        @SerialName("RequestId") val requestId: String? = null,
        @SerialName("Error") val error: ErrorBody? = null
    )
}
