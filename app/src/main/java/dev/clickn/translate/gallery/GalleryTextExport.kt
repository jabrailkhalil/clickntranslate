package dev.clickn.translate.gallery

import android.net.Uri

/** Each OCR region remains a paragraph; no geometry or original image is needed for a transcript. */
internal fun galleryTranslatedTranscript(translations: List<String>): String =
    translations.map(String::trim).filter(String::isNotEmpty).joinToString("\n\n")

internal fun galleryTranslatedTextFileName(position: Int, displayName: String): String =
    galleryTranslatedFileName(position, displayName).removeSuffix(".png") + ".txt"

/** Pending output is journalled before writing; uncertain provider content is preserved on failure. */
internal suspend fun exportGalleryTextDocument(
    exportReceipts: GalleryExportReceipts,
    parent: Uri,
    position: Int,
    displayName: String,
    segments: List<GalleryTranslationSegment>,
) {
    val text = galleryTranslatedTranscript(segments.map { it.translatedText })
    require(text.isNotEmpty()) { "No translated text to export." }
    exportReceipts.exportText(parent, galleryTranslatedTextFileName(position, displayName), text)
}
