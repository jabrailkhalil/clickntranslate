package dev.clickn.translate.gallery

import dev.clickn.translate.data.TranslationPreset
import kotlinx.serialization.decodeFromString
import kotlinx.serialization.json.Json

internal enum class GallerySnapshotProblem { MISSING, INVALID, WRONG_OWNER_OR_ROUTE }

internal class GalleryTaskSnapshotException(val problem: GallerySnapshotProblem) : IllegalStateException(
    "Saved image-task settings are unavailable or invalid. Create a new task."
)

/** Schema 1 and the original 1.8.2 writer both require a gallery_<taskId> snapshot. */
internal fun decodeGalleryTaskSnapshot(task: GalleryTranslationTaskEntity, json: Json): TranslationPreset {
    if (task.settingsSnapshotJson.isBlank()) throw GalleryTaskSnapshotException(GallerySnapshotProblem.MISSING)
    val snapshot = try {
        json.decodeFromString<TranslationPreset>(task.settingsSnapshotJson)
    } catch (_: Exception) {
        // Parser diagnostics can contain stored prompt/endpoint fragments; do not expose them.
        throw GalleryTaskSnapshotException(GallerySnapshotProblem.INVALID)
    }
    if (snapshot.id != "gallery_${task.id}" ||
        !snapshot.sourceLang.equals(task.sourceLang, ignoreCase = true) ||
        !snapshot.targetLang.equals(task.targetLang, ignoreCase = true) ||
        snapshot.ocrEngine.name != task.ocrEngine || snapshot.translatorEngine.name != task.translatorEngine
    ) throw GalleryTaskSnapshotException(GallerySnapshotProblem.WRONG_OWNER_OR_ROUTE)
    return snapshot
}
