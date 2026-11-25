package dev.clickn.translate.gallery

import dev.clickn.translate.data.OcrEngineKind
import dev.clickn.translate.data.Settings
import dev.clickn.translate.data.TranslationPresetCatalog
import dev.clickn.translate.data.TranslatorEngine
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import org.junit.Assert.*
import org.junit.Test

class GalleryTaskSnapshotTest {
    private val json = Json { ignoreUnknownKeys = true }

    @Test fun originalSchemaOneSnapshotStillDecodesWhenDefaultFieldsWereOmitted() {
        val settings = Settings()
        val task = task(settings)
        val snapshot = decodeGalleryTaskSnapshot(task, json)
        assertEquals(settings.ocrEngine, snapshot.ocrEngine)
        assertEquals(settings.translatorEngine, snapshot.translatorEngine)
        assertEquals("gallery_owned", snapshot.id)
    }

    @Test fun persistedRegionalRouteIsKeptRatherThanReplacedByCurrentDefaults() {
        val original = Settings(sourceLang = "ar", targetLang = "en-GB", translatorEngine = TranslatorEngine.GOOGLE)
        val snapshot = decodeGalleryTaskSnapshot(task(original), json)
        assertEquals("ar", snapshot.sourceLang)
        assertEquals("en-GB", snapshot.targetLang)
        assertEquals(TranslatorEngine.GOOGLE, snapshot.translatorEngine)
    }

    @Test fun blankSnapshotHasNoInventedLegacyProviderFallback() {
        val task = task(Settings()).copy(settingsSnapshotJson = "   ")
        assertProblem(task, GallerySnapshotProblem.MISSING)
    }

    @Test fun malformedSnapshotFailsWithoutExposingStoredPromptOrEndpoint() {
        val fragment = "private-stored-prompt"
        val failure = assertProblem(task(Settings()).copy(settingsSnapshotJson = "{\"$fragment\":"), GallerySnapshotProblem.INVALID)
        assertFalse(failure.message.orEmpty().contains(fragment))
        assertNull(failure.cause)
    }

    @Test fun anotherTaskCredentialOwnerOrContradictoryRouteIsRejected() {
        val original = task(Settings(sourceLang = "ar", targetLang = "en", translatorEngine = TranslatorEngine.GOOGLE))
        assertProblem(original.copy(id = "successor"), GallerySnapshotProblem.WRONG_OWNER_OR_ROUTE)
        assertProblem(original.copy(translatorEngine = TranslatorEngine.OPENAI.name), GallerySnapshotProblem.WRONG_OWNER_OR_ROUTE)
        assertProblem(original.copy(ocrEngine = OcrEngineKind.BAIDU.name), GallerySnapshotProblem.WRONG_OWNER_OR_ROUTE)
        assertProblem(original.copy(sourceLang = "ja"), GallerySnapshotProblem.WRONG_OWNER_OR_ROUTE)
        assertProblem(original.copy(targetLang = "zh-CN"), GallerySnapshotProblem.WRONG_OWNER_OR_ROUTE)
    }

    private fun task(settings: Settings): GalleryTranslationTaskEntity {
        val snapshot = TranslationPresetCatalog.fromSettings("gallery_owned", "owned", "owned", settings)
        return GalleryTranslationTaskEntity(
            id = "owned", createdAtMs = 1, sourceLang = settings.sourceLang, targetLang = settings.targetLang,
            ocrEngine = settings.ocrEngine.name, translatorEngine = settings.translatorEngine.name,
            presetName = "owned", settingsSnapshotJson = json.encodeToString(snapshot), totalCount = 1,
        )
    }

    private fun assertProblem(task: GalleryTranslationTaskEntity, expected: GallerySnapshotProblem): GalleryTaskSnapshotException {
        val failure = runCatching { decodeGalleryTaskSnapshot(task, json) }.exceptionOrNull()
        assertTrue(failure is GalleryTaskSnapshotException)
        failure as GalleryTaskSnapshotException
        assertEquals(expected, failure.problem)
        return failure
    }
}
