package dev.clickn.translate.util

import java.nio.ByteBuffer
import java.nio.charset.CodingErrorAction

/** Validate imported bytes without silently replacing a user's text. BOM handling belongs to the format. */
internal fun decodeStrictUtf8(bytes: ByteArray): String = Charsets.UTF_8.newDecoder()
    .onMalformedInput(CodingErrorAction.REPORT)
    .onUnmappableCharacter(CodingErrorAction.REPORT)
    .decode(ByteBuffer.wrap(bytes))
    .toString()
