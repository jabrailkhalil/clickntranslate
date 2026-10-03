// Modified for Click'n'Translate on October 3, 2026.
package dev.clickn.translate.onboarding

import android.content.Context

object OnboardingPrefs {
    private const val PREFS_NAME = "onboarding"
    private const val KEY_COMPLETED = "completed_v3"

    fun isCompleted(context: Context): Boolean =
        context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
            .getBoolean(KEY_COMPLETED, false)

    fun markCompleted(context: Context) {
        context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
            .edit()
            .putBoolean(KEY_COMPLETED, true)
            .apply()
    }
}
