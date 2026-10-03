// Modified for Click'n'Translate on October 3, 2026.
package dev.clickn.translate.dictionary

import java.io.File
import org.junit.Assert.*
import org.junit.Test

class OfflineDictionaryRepositoryWiringTest {
    @Test
    fun lookup_preserves_database_errors_and_cancellation_instead_of_returning_a_miss() {
        val path = "src/main/java/dev/clickn/translate/dictionary/OfflineDictionaryRepository.kt"
        val source = listOf(File(path), File("app/$path")).first { it.isFile }.readText()
        val lookup = source.substringAfter("override suspend fun lookup(").substringBefore("private fun query(")
        assertFalse(lookup.contains("getOrNull()"))
        assertTrue(lookup.contains("catch (cancellation: CancellationException)"))
        assertTrue(lookup.contains("throw cancellation"))
        assertTrue(lookup.contains("Timber.e(error,"))
        assertTrue(lookup.contains("throw error"))
        assertFalse(source.contains("ORDER BY position, rowid"))
        assertTrue(source.contains("ORDER BY position"))
    }
}
