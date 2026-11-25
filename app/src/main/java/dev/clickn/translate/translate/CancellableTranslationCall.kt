package dev.clickn.translate.translate

import java.io.IOException
import kotlin.coroutines.resume
import kotlin.coroutines.resumeWithException
import kotlinx.coroutines.suspendCancellableCoroutine
import okhttp3.Call
import okhttp3.Callback
import okhttp3.Response

/** Read and decode on OkHttp's worker; cancelling a stale translation closes its socket. */
internal suspend fun <T> Call.awaitTranslationPayload(parse: (String) -> T): T =
    suspendCancellableCoroutine { continuation ->
        continuation.invokeOnCancellation { cancel() }
        enqueue(object : Callback {
            override fun onFailure(call: Call, e: IOException) {
                if (continuation.isActive) continuation.resumeWithException(e)
            }

            override fun onResponse(call: Call, response: Response) {
                try {
                    val result = response.use {
                        if (!it.isSuccessful) throw TranslationException("Translation service: HTTP ${it.code}")
                        val body = it.body?.source() ?: throw TranslationException("Empty service response")
                        if (body.request(1_048_577)) throw TranslationException("Service response is too large")
                        parse(body.readUtf8())
                    }
                    if (continuation.isActive) continuation.resume(result)
                } catch (error: Exception) {
                    if (continuation.isActive) continuation.resumeWithException(error)
                }
            }
        })
    }
