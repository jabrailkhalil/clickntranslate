// Modified for Click'n'Translate on October 3, 2026.
package dev.clickn.translate.gallery

import org.junit.Assert.assertEquals
import org.junit.Test

class GalleryExportMetadataTest {

    @Test
    fun `export metadata identifies the author and generating software`() {
        val metadata = galleryExportMetadata()

        data class Case(
            val field: String,
            val actual: String,
        )

        listOf(
            Case("artist", metadata.artist),
            Case("software", metadata.software),
        ).forEach { case ->
            assertEquals(
                case.field,
                "Click'n'Translate",
                case.actual,
            )
        }
    }
}
