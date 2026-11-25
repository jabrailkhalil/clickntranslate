package dev.clickn.translate.gallery

import dev.clickn.translate.data.OcrEngineKind
import dev.clickn.translate.data.TranslatorEngine
import java.io.ByteArrayInputStream
import java.io.ByteArrayOutputStream
import java.io.IOException
import kotlinx.coroutines.CancellationException
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

    @Test fun persistableInputsKeepTheirFormerLargeAdmissionWhileEveryCopyReservesPrivateStorage() {
        val usable = GALLERY_COPY_STORAGE_RESERVE + 200L * 1024 * 1024
        assertEquals(200L * 1024 * 1024, galleryImageCopyBudget(true, usable))
        assertEquals(MAX_GALLERY_IMAGE_BYTES, galleryImageCopyBudget(false, usable))
        assertEquals(123L, galleryImageCopyBudget(true, GALLERY_COPY_STORAGE_RESERVE + 123L))
        assertEquals(123L, galleryImageCopyBudget(false, GALLERY_COPY_STORAGE_RESERVE + 123L))
        for (space in listOf(0L, GALLERY_COPY_STORAGE_RESERVE - 1, GALLERY_COPY_STORAGE_RESERVE)) {
            assertTrue(runCatching { galleryImageCopyBudget(true, space) }.exceptionOrNull() is IOException)
        }
    }

    @Test fun cancellationObservedAfterAProviderReadPreventsWritingThatChunk() {
        val bytes = ByteArray(40_000) { it.toByte() }
        val output = ByteArrayOutputStream()
        var checks = 0
        val canceled = runCatching {
            copyGalleryImage(ByteArrayInputStream(bytes), output, checkpoint = {
                checks++
                if (checks == 4) throw CancellationException("owned fixture")
            })
        }.exceptionOrNull()
        assertTrue(canceled is CancellationException)
        assertEquals(16 * 1024, output.size())
        assertArrayEquals(bytes.copyOf(output.size()), output.toByteArray())
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
