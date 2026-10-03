// Modified for Click'n'Translate on October 3, 2026.
package dev.clickn.translate.ui

import dev.clickn.translate.gallery.GalleryItemStatus
import org.junit.Assert.assertEquals
import org.junit.Test

class GalleryResultThumbnailPolicyTest {

    @Test
    fun `only pending states use the processing placeholder`() {
        data class Case(
            val status: GalleryItemStatus,
            val expected: Boolean,
        )

        listOf(
            Case(GalleryItemStatus.QUEUED, true),
            Case(GalleryItemStatus.RUNNING, true),
            Case(GalleryItemStatus.SUCCEEDED, false),
            Case(GalleryItemStatus.FAILED, false),
            Case(GalleryItemStatus.CANCELED, false),
        ).forEach { case ->
            assertEquals(
                case.status.name,
                case.expected,
                galleryResultThumbnailShowsProcessing(case.status),
            )
        }
    }
}
