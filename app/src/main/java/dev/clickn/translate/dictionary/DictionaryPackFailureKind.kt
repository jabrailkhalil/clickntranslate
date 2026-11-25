package dev.clickn.translate.dictionary

/** Stable UI reasons; provider/SQLite exception messages are never presentation text. */
enum class DictionaryPackFailureKind {
    STORAGE,
    READ,
    TOO_LARGE,
    CORRUPT,
    SCHEMA,
    WRONG_PACK,
    VERSION,
    UNKNOWN,
}
