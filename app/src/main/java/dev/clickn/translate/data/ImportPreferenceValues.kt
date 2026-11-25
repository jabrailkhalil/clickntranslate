package dev.clickn.translate.data

import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.booleanPreferencesKey
import androidx.datastore.preferences.core.doublePreferencesKey
import androidx.datastore.preferences.core.floatPreferencesKey
import androidx.datastore.preferences.core.intPreferencesKey
import androidx.datastore.preferences.core.longPreferencesKey
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.core.stringSetPreferencesKey

/** Exact local Preference values; callers must encrypt this representation before writing it. */
internal object ImportPreferenceValues {
    fun encode(value: Any?): ImportPreferenceValue? = when (value) {
        null -> null
        is String -> ImportPreferenceValue("string", listOf(value))
        is Boolean -> ImportPreferenceValue("boolean", listOf(value.toString()))
        is Int -> ImportPreferenceValue("int", listOf(value.toString()))
        is Long -> ImportPreferenceValue("long", listOf(value.toString()))
        is Float -> ImportPreferenceValue("float", listOf(value.toString()))
        is Double -> ImportPreferenceValue("double", listOf(value.toString()))
        is Set<*> -> {
            check(value.all { it is String }) { "Unsupported private preference set." }
            ImportPreferenceValue("string_set", value.filterIsInstance<String>().sorted())
        }
        else -> error("Unsupported private preference value.")
    }

    fun decode(value: ImportPreferenceValue): Any {
        if (value.kind == "string_set") {
            check(value.values.distinct().size == value.values.size)
            return value.values.toSet()
        }
        val item = value.values.single()
        return when (value.kind) {
            "string" -> item
            "boolean" -> item.toBooleanStrict()
            "int" -> item.toInt()
            "long" -> item.toLong()
            "float" -> item.toFloat()
            "double" -> item.toDouble()
            else -> error("Unsupported private preference kind.")
        }
    }

    fun validate(value: ImportPreferenceValue) { decode(value) }

    fun key(name: String, value: ImportPreferenceValue): Preferences.Key<*> = when (value.kind) {
        "string" -> stringPreferencesKey(name)
        "boolean" -> booleanPreferencesKey(name)
        "int" -> intPreferencesKey(name)
        "long" -> longPreferencesKey(name)
        "float" -> floatPreferencesKey(name)
        "double" -> doublePreferencesKey(name)
        "string_set" -> stringSetPreferencesKey(name)
        else -> error("Unsupported private preference kind.")
    }
}
