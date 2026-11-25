package dev.clickn.translate.translate

import java.util.Collections

enum class TranslationFailureKind {
    OFFLINE, TIMEOUT, AUTH, RATE_LIMIT, TLS, SERVICE, INVALID_RESPONSE, UNKNOWN,
}

/** Contains fixed diagnostic tokens only; never retains a Throwable, message, URL, body or stack. */
class TranslationFailureDescriptor internal constructor(
    val kind: TranslationFailureKind,
    val diagnosticCode: String,
    causeTypes: List<String>,
    val httpStatus: Int?,
    val causeCycle: Boolean,
    val chainTruncated: Boolean,
) {
    val causeTypes: List<String> = Collections.unmodifiableList(causeTypes.toList())

    override fun toString(): String = diagnosticCode
}
