package dev.clickn.translate.ui

import dev.clickn.translate.gallery.GalleryTranslationWorkPolicy

/** A consumed share stays consumed after rotation, including when its selection was cleared. */
internal data class PhotoSelectionState(
    val handledShareId: Long = 0,
    val uris: List<String> = emptyList(),
) {
    fun acceptShare(id: Long, incoming: List<String>): PhotoSelectionState =
        if (id <= 0 || id == handledShareId || incoming.isEmpty()) this
        else PhotoSelectionState(id, GalleryTranslationWorkPolicy.normalizeSelection(incoming))

    fun select(next: List<String>): PhotoSelectionState =
        copy(uris = GalleryTranslationWorkPolicy.normalizeSelection(next))

    fun save(): List<String> = listOf(handledShareId.toString()) + uris

    companion object {
        fun restore(saved: List<String>): PhotoSelectionState = PhotoSelectionState(
            handledShareId = saved.firstOrNull()?.toLongOrNull()?.coerceAtLeast(0) ?: 0,
            uris = GalleryTranslationWorkPolicy.normalizeSelection(saved.drop(1)),
        )
    }
}
