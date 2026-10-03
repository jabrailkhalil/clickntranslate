package dev.clickn.translate.gallery

import dev.clickn.translate.data.OcrEngineKind
import dev.clickn.translate.data.TranslatorEngine
import java.io.ByteArrayInputStream
import java.io.ByteArrayOutputStream
import org.junit.Assert.*
import org.junit.Test

class GalleryInputSafetyTest {
    @Test fun incomingSharesRejectPrivateFilesAndRemoteUrls() {
        val uris = listOf("file:///data/user/0/dev.clickn.translate/files/private.png", "https://example.com/photo.png",
            "content:/missing-authority", "content://user@provider/1", "content://photos/1")
        assertEquals(listOf("content://photos/1"), GalleryTranslationWorkPolicy.sharedImageSelection(
            GalleryTranslationWorkPolicy.ACTION_SEND_MULTIPLE, "image/png", null, uris))
    }

    @Test fun copyPreservesBytesWithinTheLimitAndRejectsOverflow() {
        val bytes = ByteArray(100) { it.toByte() }
        val output = ByteArrayOutputStream()
        assertEquals(100L, copyGalleryImage(ByteArrayInputStream(bytes), output, 100))
        assertArrayEquals(bytes, output.toByteArray())
        assertTrue(runCatching { copyGalleryImage(ByteArrayInputStream(bytes), ByteArrayOutputStream(), 99) }.isFailure)
    }

    @Test fun everyAddedOnlineEngineRequiresNetworkForGalleryJobs() {
        for (engine in listOf(TranslatorEngine.LINGVA, TranslatorEngine.LIBRETRANSLATE, TranslatorEngine.MYMEMORY, TranslatorEngine.NIUTRANS))
            assertTrue(engine.name, GalleryTranslationWorkPolicy.requiresNetwork(OcrEngineKind.ML_KIT_LATIN, engine))
    }

    @Test fun cyclicExceptionChainsNeverHangRetryClassification() {
        val a = Exception("permanent failure")
        val b = Exception("another failure", a)
        a.initCause(b)
        assertFalse(GalleryTranslationWorkPolicy.shouldRetry(a, 0))
    }
}
