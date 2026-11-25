package dev.clickn.translate.translate

import java.io.IOException
import java.io.InterruptedIOException
import java.net.ConnectException
import java.net.SocketTimeoutException
import java.net.UnknownHostException
import java.security.NoSuchAlgorithmException
import java.security.cert.CertificateException
import java.security.cert.CertPathValidatorException
import java.util.ConcurrentModificationException
import java.util.concurrent.CancellationException
import java.util.concurrent.RejectedExecutionException
import javax.net.ssl.SSLException
import javax.net.ssl.SSLHandshakeException
import javax.net.ssl.SSLKeyException
import javax.net.ssl.SSLPeerUnverifiedException
import javax.net.ssl.SSLProtocolException
import kotlinx.serialization.SerializationException
import okhttp3.Protocol
import okhttp3.Request
import okhttp3.ResponseBody.Companion.toResponseBody
import org.junit.Assert.*
import org.junit.Test
import retrofit2.HttpException

class TranslationFailurePolicyTest {
    @Test fun networkTypesClassifyWithoutReadingTheirHostOrFailureMessage() {
        val cases = listOf(
            Triple(UnknownHostException(SECRET), TranslationFailureKind.OFFLINE, "UnknownHostException"),
            Triple(ConnectException(SECRET), TranslationFailureKind.OFFLINE, "ConnectException"),
            Triple(SocketTimeoutException(SECRET), TranslationFailureKind.TIMEOUT, "SocketTimeoutException"),
            Triple(InterruptedIOException(SECRET), TranslationFailureKind.TIMEOUT, "InterruptedIOException"),
        )
        for ((error, expected, alias) in cases) {
            val failure = describeTranslationFailure(error)
            assertEquals(expected, failure.kind)
            assertEquals(listOf(alias), failure.causeTypes)
            assertNull(failure.httpStatus)
            assertSafe(failure)
        }
    }

    @Test fun tlsCertificateAndHandshakeReasonsHaveSafeStableAliases() {
        val cases = listOf(
            SSLException(SECRET) to "SSLException",
            SSLHandshakeException(SECRET) to "SSLHandshakeException",
            SSLPeerUnverifiedException(SECRET) to "SSLPeerUnverifiedException",
            SSLProtocolException(SECRET) to "SSLProtocolException",
            SSLKeyException(SECRET) to "SSLKeyException",
            CertificateException("CN=$SECRET issuer=$SECRET") to "CertificateException",
            CertPathValidatorException("CN=$SECRET") to "CertPathValidatorException",
        )
        for ((error, alias) in cases) {
            val failure = describeTranslationFailure(error)
            assertEquals(TranslationFailureKind.TLS, failure.kind)
            assertEquals(listOf(alias), failure.causeTypes)
            assertSafe(failure)
        }
    }

    @Test fun retrofitStatusIsUsedButItsRequestUrlErrorBodyAndReasonAreNot() {
        for ((status, kind) in httpCases()) {
            val raw = okhttp3.Response.Builder()
                .request(Request.Builder().url("https://private.invalid/$SECRET?api_key=$SECRET").build())
                .protocol(Protocol.HTTP_1_1).code(status).message(SECRET).build()
            val error = HttpException(retrofit2.Response.error<String>(SECRET.toResponseBody(), raw))
            val failure = describeTranslationFailure(error)
            assertEquals(kind, failure.kind)
            assertEquals(status, failure.httpStatus)
            assertEquals("TF_HTTP_$status", failure.diagnosticCode)
            assertEquals(listOf("HttpException"), failure.causeTypes)
            assertSafe(failure)
        }
    }

    @Test fun onlyTheExactOwnedHttpTemplateIsRecognized() {
        for ((status, kind) in httpCases()) {
            val failure = describeTranslationFailure(TranslationException("Translation service: HTTP $status"))
            assertEquals(kind, failure.kind)
            assertEquals(status, failure.httpStatus)
            assertEquals("TF_HTTP_$status", failure.diagnosticCode)
            assertSafe(failure)
        }
        val untrusted = listOf(
            "HTTP 401", "Translation service: HTTP401", "Translation service: HTTP 0401",
            "Translation service: HTTP 999", "Translation service: HTTP 401 $SECRET",
            "Translation service: HTTP 401\n$SECRET", "Translation service: HTTP 401\n",
            " Translation service: HTTP 401", "translation service: HTTP 401",
            "Baidu translation HTTP 401: $SECRET", "https://private.invalid/$SECRET HTTP 401",
            "Translation service: HTTP 401" + SECRET.repeat(30),
        )
        for (message in untrusted) {
            val failure = describeTranslationFailure(TranslationException(message))
            assertEquals(TranslationFailureKind.UNKNOWN, failure.kind)
            assertEquals("TF_UNKNOWN", failure.diagnosticCode)
            assertNull(failure.httpStatus)
            assertSafe(failure)
        }
        assertEquals(TranslationFailureKind.UNKNOWN,
            describeTranslationFailure(RuntimeException("Translation service: HTTP 401")).kind)
    }

    @Test fun currentGoogleAndBoundedBodyFailuresHaveFixedResponseCodes() {
        val cases = mapOf(
            "Empty service response" to "TF_RESPONSE_EMPTY",
            "Service response is too large" to "TF_RESPONSE_TOO_LARGE",
            "Google response could not be parsed" to "TF_RESPONSE_GOOGLE_PARSE",
            "Google response is not a JSON array" to "TF_RESPONSE_GOOGLE_ARRAY",
            "Google response is missing translation segments" to "TF_RESPONSE_GOOGLE_SEGMENTS",
            "Google returned an empty translation" to "TF_RESPONSE_GOOGLE_EMPTY",
        )
        for ((message, code) in cases) {
            val failure = describeTranslationFailure(TranslationException(message, SerializationException(SECRET)))
            assertEquals(TranslationFailureKind.INVALID_RESPONSE, failure.kind)
            assertEquals(code, failure.diagnosticCode)
            assertEquals(listOf("TranslationException", "SerializationException"), failure.causeTypes)
            assertSafe(failure)
        }
        assertEquals(TranslationFailureKind.UNKNOWN,
            describeTranslationFailure(TranslationException("Google response could not be parsed: $SECRET")).kind)
    }

    @Test fun builtinUnknownReasonsRemainUsefulUnderAppClassMinification() {
        val cases = listOf(
            IllegalStateException(SECRET) to "IllegalStateException",
            IllegalArgumentException(SECRET) to "IllegalArgumentException",
            SecurityException(SECRET) to "SecurityException",
            RejectedExecutionException(SECRET) to "RejectedExecutionException",
            ClassCastException(SECRET) to "ClassCastException",
            IOException(SECRET) to "IOException",
            NoSuchAlgorithmException(SECRET) to "NoSuchAlgorithmException",
            NullPointerException(SECRET) to "NullPointerException",
            IndexOutOfBoundsException(SECRET) to "IndexOutOfBoundsException",
            NoSuchElementException(SECRET) to "NoSuchElementException",
            UnsupportedOperationException(SECRET) to "UnsupportedOperationException",
            ConcurrentModificationException(SECRET) to "ConcurrentModificationException",
            UninitializedPropertyAccessException(SECRET) to "UninitializedPropertyAccessException",
            SerializationException(SECRET) to "SerializationException",
        )
        for ((error, alias) in cases) {
            val failure = describeTranslationFailure(error)
            assertEquals(TranslationFailureKind.UNKNOWN, failure.kind)
            assertEquals(listOf(alias), failure.causeTypes)
            assertTrue(failure.diagnosticCode.startsWith("TF_UNKNOWN_"))
            assertSafe(failure)
        }
    }

    @Test fun aConcreteCauseWinsOverAnUnknownWrapperAndTheFirstConcreteReasonIsStable() {
        val wrapped = TranslationException(SECRET, IllegalStateException(SECRET, SocketTimeoutException(SECRET)))
        val failure = describeTranslationFailure(wrapped)
        assertEquals(TranslationFailureKind.TIMEOUT, failure.kind)
        assertEquals("TF_TIMEOUT_SOCKET", failure.diagnosticCode)
        assertEquals(listOf("TranslationException", "IllegalStateException", "SocketTimeoutException"), failure.causeTypes)
        val outer = describeTranslationFailure(TranslationException("Translation service: HTTP 503", UnknownHostException(SECRET)))
        assertEquals(TranslationFailureKind.SERVICE, outer.kind)
        assertEquals(503, outer.httpStatus)
        assertSafe(failure)
        assertSafe(outer)
    }

    @Test fun cyclicCausesTerminateWithoutInventingTruncationOrEchoingMessages() {
        val first = RuntimeException(SECRET)
        val second = IOException(SECRET)
        first.initCause(second)
        second.initCause(first)
        val failure = describeTranslationFailure(first)
        assertTrue(failure.causeCycle)
        assertFalse(failure.chainTruncated)
        assertEquals(listOf("RuntimeException", "IOException"), failure.causeTypes)
        assertEquals("TF_UNKNOWN_IO", failure.diagnosticCode)
        assertSafe(failure)
    }

    @Test fun eightNodesAreInspectedButANinthReasonIsNeitherReadNorGuessed() {
        var exact: Throwable = UnknownHostException(SECRET)
        repeat(7) { exact = RuntimeException(SECRET, exact) }
        val included = describeTranslationFailure(exact)
        assertEquals(8, included.causeTypes.size)
        assertEquals(TranslationFailureKind.OFFLINE, included.kind)
        assertFalse(included.chainTruncated)
        val excluded = describeTranslationFailure(RuntimeException(SECRET, exact))
        assertEquals(8, excluded.causeTypes.size)
        assertEquals(TranslationFailureKind.UNKNOWN, excluded.kind)
        assertTrue(excluded.chainTruncated)
        assertFalse(excluded.causeCycle)
        assertFalse(excluded.causeTypes.contains("UnknownHostException"))
        assertSafe(excluded)
    }

    @Test fun directOrNestedCancellationIsRethrownByIdentityEvenAfterAnOuterHttpReason() {
        val canceled = CancellationException(SECRET)
        assertSame(canceled, runCatching { describeTranslationFailure(canceled) }.exceptionOrNull())
        assertSame(canceled, runCatching {
            describeTranslationFailure(TranslationException("Translation service: HTTP 401", IOException(SECRET, canceled)))
        }.exceptionOrNull())
        var boundary: Throwable = canceled
        repeat(7) { boundary = RuntimeException(SECRET, boundary) }
        assertSame(canceled, runCatching { describeTranslationFailure(boundary) }.exceptionOrNull())
    }

    @Test fun cancellationBeyondTheDocumentedBoundIsNotInspected() {
        var chain: Throwable = CancellationException(SECRET)
        repeat(8) { chain = RuntimeException(SECRET, chain) }
        val failure = describeTranslationFailure(chain)
        assertEquals(TranslationFailureKind.UNKNOWN, failure.kind)
        assertTrue(failure.chainTruncated)
        assertEquals(8, failure.causeTypes.size)
        assertSafe(failure)
    }

    @Test fun messagesClassNamesAndStackDataCannotEscapeEvenFromAnUnreviewedException() {
        val error = PrivateUrlApiKeySourceMarker().apply {
            stackTrace = arrayOf(StackTraceElement(SECRET, SECRET, SECRET, 17))
            addSuppressed(UnknownHostException(SECRET))
        }
        val failure = describeTranslationFailure(error)
        assertEquals(TranslationFailureKind.UNKNOWN, failure.kind)
        assertEquals(listOf("Other"), failure.causeTypes)
        assertFalse(failure.toString().contains("PrivateUrlApiKeySourceMarker"))
        assertSafe(failure)
        val another = describeTranslationFailure(UnknownHostException("completely-different-raw-host"))
        val original = describeTranslationFailure(UnknownHostException(SECRET))
        assertEquals(original.diagnosticCode, another.diagnosticCode)
        assertEquals(original.causeTypes, another.causeTypes)
    }

    private class PrivateUrlApiKeySourceMarker : RuntimeException() {
        override val message: String get() = error("Must not read raw message")
        override fun toString(): String = error("Must not format raw throwable")
    }

    private fun assertSafe(failure: TranslationFailureDescriptor) {
        val visible = failure.toString() + failure.diagnosticCode + failure.causeTypes.joinToString("|")
        assertFalse(visible.contains(SECRET))
        assertFalse(visible.contains("https://"))
        assertFalse(visible.contains("api_key="))
        assertTrue(failure.diagnosticCode.matches(Regex("[A-Z0-9_]{1,64}")))
        assertTrue(failure.causeTypes.size in 1..8)
    }

    private fun httpCases() = listOf(
        401 to TranslationFailureKind.AUTH, 403 to TranslationFailureKind.AUTH,
        407 to TranslationFailureKind.AUTH, 408 to TranslationFailureKind.TIMEOUT,
        429 to TranslationFailureKind.RATE_LIMIT, 500 to TranslationFailureKind.SERVICE,
        503 to TranslationFailureKind.SERVICE, 504 to TranslationFailureKind.TIMEOUT,
    )

    private companion object { const val SECRET = "private-source-api-key-مرحبا-😀" }
}
