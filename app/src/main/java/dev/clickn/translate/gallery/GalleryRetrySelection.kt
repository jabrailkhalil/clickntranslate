package dev.clickn.translate.gallery

/** Durable retry intent contains only app-owned row IDs/versions, never URI/text/settings/secrets. */
data class GalleryRetryItem(val id: String, val version: Long)

data class GalleryRetrySelection(
    val taskStatus: GalleryTaskStatus,
    val finishedAtMs: Long,
    val items: List<GalleryRetryItem>,
)
