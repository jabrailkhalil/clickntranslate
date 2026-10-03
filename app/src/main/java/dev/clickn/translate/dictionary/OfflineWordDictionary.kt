// Modified for Click'n'Translate on October 3, 2026.
package dev.clickn.translate.dictionary

import dev.clickn.translate.translate.WordResult

interface OfflineWordDictionary {
    suspend fun lookup(word: String, languageCode: String): WordResult?
}

object EmptyOfflineWordDictionary : OfflineWordDictionary {
    override suspend fun lookup(word: String, languageCode: String): WordResult? = null
}
