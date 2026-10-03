package dev.clickn.translate.ui

import android.content.Context
import android.os.Looper
import android.view.View
import android.view.ViewGroup
import android.widget.TextView
import androidx.room.Room
import androidx.test.core.app.ApplicationProvider
import dev.clickn.translate.ClickTranslateApp
import dev.clickn.translate.R
import dev.clickn.translate.data.CompanionPrefs
import dev.clickn.translate.data.Settings
import dev.clickn.translate.glossary.*
import dev.clickn.translate.overlay.FloatingButtonManager
import dev.clickn.translate.overlay.TranslationCardOverlay
import java.time.Duration
import kotlinx.coroutines.*
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.Shadows.shadowOf
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode
import org.robolectric.annotation.LooperMode

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35], application = ClickTranslateApp::class)
@LooperMode(LooperMode.Mode.PAUSED)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
class PreviewLifecycleRuntimeTest {
    private val app get() = ApplicationProvider.getApplicationContext<ClickTranslateApp>()

    @Test fun resultWaitsForCompletionThenClosesAfterReading() {
        val card = TranslationCardOverlay(app)
        try {
            card.show("hello", null, null, Settings(), loading = true)
            assertTrue(card.isShown())
            card.updateTranslation("partial")
            shadowOf(Looper.getMainLooper()).idleFor(Duration.ofSeconds(90))
            assertTrue("streaming result must stay open", card.isShown())
            card.updateTranslation("готово", final = true)
            shadowOf(Looper.getMainLooper()).idleFor(Duration.ofSeconds(70))
            assertFalse(card.isShown())
        } finally { card.dismiss() }
    }

    @Test fun pinKeepsAResultOpenUntilUnpinned() {
        val card = TranslationCardOverlay(app)
        try {
            card.show("hello", "привет", null, Settings())
            val root = TranslationCardOverlay::class.java.getDeclaredField("rootView")
                .apply { isAccessible = true }.get(card) as View
            fun find(view: View): TextView? {
                if (view is TextView && view.text.toString() == app.getString(R.string.overlay_pin)) return view
                if (view is ViewGroup) for (i in 0 until view.childCount) find(view.getChildAt(i))?.let { return it }
                return null
            }
            val pin = requireNotNull(find(root))
            pin.performClick()
            shadowOf(Looper.getMainLooper()).idleFor(Duration.ofSeconds(90))
            assertTrue(card.isShown())
            pin.performClick()
            shadowOf(Looper.getMainLooper()).idleFor(Duration.ofSeconds(70))
            assertFalse(card.isShown())
        } finally { card.dismiss() }
    }

    @Test fun buttonCanHideAndPersistentChoiceKeepsItVisible() {
        val scope = CoroutineScope(SupervisorJob() + Dispatchers.Main.immediate)
        val manager = FloatingButtonManager(app, {}, {}, {}, app.settingsRepository, scope)
        try {
            CompanionPrefs.setKeepVisible(app, false)
            manager.show()
            shadowOf(Looper.getMainLooper()).idleFor(Duration.ofSeconds(46))
            assertFalse(manager.isShown())
            CompanionPrefs.setKeepVisible(app, true)
            manager.show()
            shadowOf(Looper.getMainLooper()).idleFor(Duration.ofSeconds(90))
            assertTrue(manager.isShown())
        } finally { manager.hide(); scope.cancel() }
    }

    @Test fun migrationPreservesEditedRowsAndLaterUserWords() = runBlocking {
        app.getSharedPreferences("source_preservation_presets", Context.MODE_PRIVATE).edit()
            .clear().putBoolean("ja_manga_sfx_v1", true).commit()
        val db = Room.inMemoryDatabaseBuilder(app, TranslationGlossaryDatabase::class.java)
            .allowMainThreadQueries().build()
        try {
            val sounds = app.assets.open("source_preservation_ja.txt").bufferedReader().useLines {
                it.map(String::trim).filter { word -> word.isNotEmpty() && !word.startsWith("#") }.take(2).toList()
            }
            val seed = GlossaryTermEntity(id = 1, sourceLang = "ja", targetLang = "*",
                sourceTerm = sounds[0], targetTerm = sounds[0], category = GlossaryTermCategory.PRESERVE_SOURCE,
                createdAtMs = 10, updatedAtMs = 10)
            val edited = seed.copy(id = 2, sourceTerm = sounds[1], normalizedSourceTerm = normalizeGlossaryTerm(sounds[1], false),
                targetTerm = sounds[1], updatedAtMs = 20)
            db.glossaryDao().insertAll(listOf(seed, edited))
            val repository = TranslationGlossaryRepository(db.glossaryDao(), app)
            assertEquals(listOf(2L), repository.listAll().map { it.id })
            assertEquals(2, db.glossaryDao().listAll().size)
            db.glossaryDao().delete(1)
            db.glossaryDao().insert(seed.copy(id = 99, createdAtMs = 30, updatedAtMs = 30))
            assertEquals(setOf(2L, 99L), repository.listAll().map { it.id }.toSet())
            assertTrue(repository.preservationTerms(false).any { it.id == 99L })
        } finally { db.close() }
    }
}
