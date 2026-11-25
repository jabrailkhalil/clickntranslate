package dev.clickn.translate.translate

import java.io.IOException
import java.io.InterruptedIOException
import java.net.ConnectException
import java.net.SocketTimeoutException
import java.net.UnknownHostException
import java.security.NoSuchAlgorithmException
import java.security.cert.CertificateException
import java.security.cert.CertPathValidatorException
import java.util.Collections
import java.util.ConcurrentModificationException
import java.util.IdentityHashMap
import java.util.concurrent.CancellationException
import java.util.concurrent.RejectedExecutionException
import javax.net.ssl.SSLException
import javax.net.ssl.SSLHandshakeException
import javax.net.ssl.SSLKeyException
import javax.net.ssl.SSLPeerUnverifiedException
import javax.net.ssl.SSLProtocolException
import kotlinx.serialization.SerializationException
import retrofit2.HttpException

/**
 * Android-free, side-effect-free diagnostics for a translation failure.
 *
 * Inspects at most eight distinct cause nodes, outermost first. Cancellation encountered within
 * that bound is rethrown unchanged, even if an outer error already supplied a concrete reason.
 * Deeper causes are not inspected or guessed; [TranslationFailureDescriptor.chainTruncated]
 * records that boundary. Suppressed exceptions and stack frames are never inspected.
 *
 * The first concrete reason wins; a known UNKNOWN builtin is used only if no concrete reason
 * occurs in the inspected chain. All type aliases/codes are constants, independent of R8 names.
 */
fun describeTranslationFailure(error: Throwable): TranslationFailureDescriptor {
    val seen = Collections.newSetFromMap(IdentityHashMap<Throwable, Boolean>())
    val aliases = ArrayList<String>(MAX_FAILURE_CAUSES)
    var current: Throwable? = error
    var concrete: FailureReason? = null
    var unknown: FailureReason? = null
    while (current != null && aliases.size < MAX_FAILURE_CAUSES && seen.add(current)) {
        if (current is CancellationException) throw current
        val fact = failureFact(current)
        aliases += fact.alias
        fact.reason?.let { reason ->
            if (reason.kind == TranslationFailureKind.UNKNOWN) {
                if (unknown == null) unknown = reason
            } else if (concrete == null) {
                concrete = reason
            }
        }
        current = current.cause
    }
    val cycle = current != null && seen.contains(current)
    val reason = concrete ?: unknown ?: FailureReason(TranslationFailureKind.UNKNOWN, "TF_UNKNOWN")
    return TranslationFailureDescriptor(
        kind = reason.kind,
        diagnosticCode = reason.code,
        causeTypes = aliases,
        httpStatus = reason.httpStatus,
        causeCycle = cycle,
        chainTruncated = current != null && !cycle,
    )
}

private const val MAX_FAILURE_CAUSES = 8
private const val MAX_KNOWN_FAILURE_MESSAGE = 96
private val serviceHttpMessage = Regex("Translation service: HTTP ([1-5][0-9]{2})")

private data class FailureReason(
    val kind: TranslationFailureKind,
    val code: String,
    val httpStatus: Int? = null,
)

private data class FailureFact(val alias: String, val reason: FailureReason? = null)

private fun failureFact(error: Throwable): FailureFact = when (error) {
    is TranslationException -> FailureFact("TranslationException", knownTranslationReason(error))
    is UnknownHostException -> FailureFact("UnknownHostException", FailureReason(TranslationFailureKind.OFFLINE, "TF_OFFLINE_DNS"))
    is ConnectException -> FailureFact("ConnectException", FailureReason(TranslationFailureKind.OFFLINE, "TF_OFFLINE_CONNECT"))
    is SocketTimeoutException -> FailureFact("SocketTimeoutException", FailureReason(TranslationFailureKind.TIMEOUT, "TF_TIMEOUT_SOCKET"))
    is InterruptedIOException -> FailureFact("InterruptedIOException", FailureReason(TranslationFailureKind.TIMEOUT, "TF_TIMEOUT_IO"))
    is SSLHandshakeException -> FailureFact("SSLHandshakeException", FailureReason(TranslationFailureKind.TLS, "TF_TLS_HANDSHAKE"))
    is SSLPeerUnverifiedException -> FailureFact("SSLPeerUnverifiedException", FailureReason(TranslationFailureKind.TLS, "TF_TLS_PEER"))
    is SSLProtocolException -> FailureFact("SSLProtocolException", FailureReason(TranslationFailureKind.TLS, "TF_TLS_PROTOCOL"))
    is SSLKeyException -> FailureFact("SSLKeyException", FailureReason(TranslationFailureKind.TLS, "TF_TLS_KEY"))
    is SSLException -> FailureFact("SSLException", FailureReason(TranslationFailureKind.TLS, "TF_TLS"))
    is CertificateException -> FailureFact("CertificateException", FailureReason(TranslationFailureKind.TLS, "TF_TLS_CERTIFICATE"))
    is CertPathValidatorException -> FailureFact("CertPathValidatorException", FailureReason(TranslationFailureKind.TLS, "TF_TLS_CERT_PATH"))
    is HttpException -> FailureFact("HttpException", httpReason(error.code()))
    is SerializationException -> unknownFact("SerializationException", "TF_UNKNOWN_SERIALIZATION")
    is NoSuchAlgorithmException -> unknownFact("NoSuchAlgorithmException", "TF_UNKNOWN_ALGORITHM")
    is RejectedExecutionException -> unknownFact("RejectedExecutionException", "TF_UNKNOWN_EXECUTOR_REJECTED")
    is SecurityException -> unknownFact("SecurityException", "TF_UNKNOWN_SECURITY")
    is ClassCastException -> unknownFact("ClassCastException", "TF_UNKNOWN_CLASS_CAST")
    is NullPointerException -> unknownFact("NullPointerException", "TF_UNKNOWN_NULL_POINTER")
    is IndexOutOfBoundsException -> unknownFact("IndexOutOfBoundsException", "TF_UNKNOWN_INDEX_BOUNDS")
    is NoSuchElementException -> unknownFact("NoSuchElementException", "TF_UNKNOWN_NO_ELEMENT")
    is UnsupportedOperationException -> unknownFact("UnsupportedOperationException", "TF_UNKNOWN_UNSUPPORTED_OPERATION")
    is ConcurrentModificationException -> unknownFact("ConcurrentModificationException", "TF_UNKNOWN_CONCURRENT_MODIFICATION")
    is UninitializedPropertyAccessException -> unknownFact("UninitializedPropertyAccessException", "TF_UNKNOWN_UNINITIALIZED_PROPERTY")
    is IllegalStateException -> unknownFact("IllegalStateException", "TF_UNKNOWN_ILLEGAL_STATE")
    is IllegalArgumentException -> unknownFact("IllegalArgumentException", "TF_UNKNOWN_ILLEGAL_ARGUMENT")
    is IOException -> unknownFact("IOException", "TF_UNKNOWN_IO")
    else -> FailureFact(when (error.javaClass) {
        RuntimeException::class.java -> "RuntimeException"
        Exception::class.java -> "Exception"
        Throwable::class.java -> "Throwable"
        else -> "Other"
    })
}

private fun unknownFact(alias: String, code: String) =
    FailureFact(alias, FailureReason(TranslationFailureKind.UNKNOWN, code))

/** This final app-owned exception is the only type whose message is read. It is never returned. */
private fun knownTranslationReason(error: TranslationException): FailureReason? {
    val message = error.message ?: return null
    if (message.length > MAX_KNOWN_FAILURE_MESSAGE) return null
    val http = serviceHttpMessage.matchEntire(message)
    if (http != null) return httpReason(http.groupValues[1].toInt())
    val code = when (message) {
        "Empty service response" -> "TF_RESPONSE_EMPTY"
        "Service response is too large" -> "TF_RESPONSE_TOO_LARGE"
        "Google response could not be parsed" -> "TF_RESPONSE_GOOGLE_PARSE"
        "Google response is not a JSON array" -> "TF_RESPONSE_GOOGLE_ARRAY"
        "Google response is missing translation segments" -> "TF_RESPONSE_GOOGLE_SEGMENTS"
        "Google returned an empty translation" -> "TF_RESPONSE_GOOGLE_EMPTY"
        else -> return null
    }
    return FailureReason(TranslationFailureKind.INVALID_RESPONSE, code)
}

private fun httpReason(status: Int): FailureReason? {
    if (status !in 100..599) return null
    val kind = when (status) {
        401, 403, 407 -> TranslationFailureKind.AUTH
        429 -> TranslationFailureKind.RATE_LIMIT
        408, 504 -> TranslationFailureKind.TIMEOUT
        else -> TranslationFailureKind.SERVICE
    }
    return FailureReason(kind, "TF_HTTP_$status", status)
}
