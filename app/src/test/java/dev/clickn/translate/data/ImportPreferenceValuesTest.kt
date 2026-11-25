package dev.clickn.translate.data

import androidx.datastore.preferences.core.mutablePreferencesOf
import androidx.datastore.preferences.core.stringPreferencesKey
import org.junit.Assert.*
import org.junit.Test

class ImportPreferenceValuesTest {
    @Test fun everySupportedPreferenceKindRoundTripsWithoutLosingItsType() {
        val values = listOf<Any>("synthetic secret", "", true, false, 42, Int.MIN_VALUE,
            Long.MAX_VALUE, -0.0f, Float.NaN, Double.POSITIVE_INFINITY, 0.42,
            setOf("Arabic العربية", "x"), emptySet<String>())
        values.forEach { value ->
            val restored = ImportPreferenceValues.decode(requireNotNull(ImportPreferenceValues.encode(value)))
            assertEquals(value::class, restored::class)
            if (value is Float && value.isNaN()) assertTrue((restored as Float).isNaN()) else assertEquals(value, restored)
        }
        assertNull(ImportPreferenceValues.encode(null))
    }

    @Test fun malformedValuesFailClosedInsteadOfChangingTheirTypeOrSilentlyChoosingDefaults() {
        val malformed = listOf(ImportPreferenceValue("unknown", listOf("x")),
            ImportPreferenceValue("boolean", listOf("yes")), ImportPreferenceValue("int", listOf("2147483648")),
            ImportPreferenceValue("string", listOf("one", "two")), ImportPreferenceValue("long", emptyList()),
            ImportPreferenceValue("string_set", listOf("same", "same")))
        malformed.forEach { assertTrue(runCatching { ImportPreferenceValues.validate(it) }.isFailure) }
        assertTrue(runCatching { ImportPreferenceValues.encode(Any()) }.isFailure)
        assertTrue(runCatching { ImportPreferenceValues.encode(setOf(1)) }.isFailure)
    }

    @Test fun restoredLocalTokenRollsBackOnlyStillMatchingValuesAndNeverPrintsThem() {
        val key = stringPreferencesKey("local_credential")
        val other = stringPreferencesKey("unrelated")
        val changes = listOf(ImportPreferenceChange(key.name, ImportPreferenceValues.encode("synthetic-before"),
            ImportPreferenceValues.encode("synthetic-imported")))
        val token = SettingsImportRollback.restoreToken(changes)
        val untouched = mutablePreferencesOf(key to "synthetic-imported", other to "late edit")
        token.restore(untouched) { _, actual, expected -> actual == expected }
        assertEquals("synthetic-before", untouched[key])
        assertEquals("late edit", untouched[other])
        val edited = mutablePreferencesOf(key to "synthetic-later")
        token.restore(edited) { _, actual, expected -> actual == expected }
        assertEquals("synthetic-later", edited[key])
        assertFalse(changes.single().toString().contains("synthetic"))
        assertFalse(changes.single().before.toString().contains("synthetic"))
        assertFalse(token.toString().contains("synthetic"))
    }
}
