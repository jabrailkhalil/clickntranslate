package dev.clickn.translate.gallery

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Test

class GalleryTextExportTest {
    @Test fun transcriptKeepsSeparateRegionsAndDropsUntranslatedOnes() {
        assertEquals("Яркие реки бегут по тихим долинам.\n\nМаленькая оранжевая лиса читает полезную книгу.",
            galleryTranslatedTranscript(listOf("Яркие реки бегут по тихим долинам.", " ", "Маленькая оранжевая лиса читает полезную книгу.")))
    }
    @Test fun arabicAndMixedLanguageTranscriptRoundTripsThroughUtf8WithoutVisualReordering() {
        val expected = "هذا نص عربي واضح.\n\nEnglish stays in logical order.\nرقم 123"
        val transcript = galleryTranslatedTranscript(listOf("هذا نص عربي واضح.", "English stays in logical order.\nرقم 123"))
        assertEquals(expected, transcript)
        assertEquals(expected, transcript.toByteArray(Charsets.UTF_8).toString(Charsets.UTF_8))
    }
    @Test fun documentNameCannotEscapeTheDestinationAndHasATextExtension() {
        val name = galleryTranslatedTextFileName(0, "../../a:b.png")
        assertFalse(name.contains('/')); assertFalse(name.contains(':'))
        assertEquals("_.._a_b_translated_001.txt", name)
        assertEquals("image_translated_001.txt", galleryTranslatedTextFileName(-5, "..."))
    }
    @Test fun emptyTranslationsProduceNoDocumentContent() {
        assertEquals("", galleryTranslatedTranscript(listOf("", "\n\t")))
    }
}
