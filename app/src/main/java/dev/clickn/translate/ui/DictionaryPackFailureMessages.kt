package dev.clickn.translate.ui

import androidx.annotation.StringRes
import dev.clickn.translate.R
import dev.clickn.translate.dictionary.DictionaryPackFailureKind

@StringRes
internal fun dictionaryPackFailureMessageResource(kind: DictionaryPackFailureKind): Int = when (kind) {
    DictionaryPackFailureKind.STORAGE -> R.string.dictionary_error_storage
    DictionaryPackFailureKind.READ -> R.string.dictionary_error_read
    DictionaryPackFailureKind.TOO_LARGE -> R.string.dictionary_error_too_large
    DictionaryPackFailureKind.CORRUPT -> R.string.dictionary_error_corrupt
    DictionaryPackFailureKind.SCHEMA -> R.string.dictionary_error_schema
    DictionaryPackFailureKind.WRONG_PACK -> R.string.dictionary_error_wrong_pack
    DictionaryPackFailureKind.VERSION -> R.string.dictionary_error_version
    DictionaryPackFailureKind.UNKNOWN -> R.string.dictionary_error_unknown
}
