package dev.clickn.translate.gallery

import android.content.Context
import android.content.ContextWrapper
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.Color
import androidx.datastore.preferences.core.PreferenceDataStoreFactory
import androidx.room.Room
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import dev.clickn.translate.data.OverlayFontManager
import dev.clickn.translate.data.Settings
import dev.clickn.translate.data.SettingsRepository
import dev.clickn.translate.data.SettingsSecretCipher
import java.io.File
import java.io.IOException
import java.nio.file.FileVisitResult
import java.nio.file.Files
import java.nio.file.LinkOption.NOFOLLOW_LINKS
import java.nio.file.Path
import java.nio.file.SimpleFileVisitor
import java.nio.file.attribute.BasicFileAttributes
import java.util.UUID
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.async
import kotlinx.coroutines.cancel
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.job
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeout
import kotlinx.coroutines.withTimeoutOrNull
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith

/** Owned cache/files and isolated Room only; no app tasks, credentials, URI grants or SAF outputs. */
@RunWith(AndroidJUnit4::class)
class GalleryTransientFilesIntegrationTest {
    private val target = InstrumentationRegistry.getInstrumentation().targetContext

    @Test fun realPreviewAccessClearsOldTempsAndRetainsJpgBeforeGeneratingItsReplacement() = runBlocking {
        withOwnedCache { owned ->
            val database = Room.inMemoryDatabaseBuilder(owned.context, GalleryTranslationDatabase::class.java).build()
            val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
            val dataStore = PreferenceDataStoreFactory.create(scope = scope) {
                owned.base.resolve("settings.preferences_pb").toFile()
            }
            val secretCipher = object : SettingsSecretCipher {
                override fun encrypt(plainText: String): String = error("No credentials belong to this fixture")
                override fun decrypt(cipherText: String): String = error("No credentials belong to this fixture")
            }
            val settingsRepository = SettingsRepository(owned.context, secretCipher, dataStore)
            val json = Json { encodeDefaults = true }
            val decoder = GalleryImageDecoder(owned.context)
            val renderer = GalleryTranslatedImageRenderer(owned.context, OverlayFontManager(owned.context, settingsRepository))
            val dao = database.galleryTranslationDao()
            val taskId = uuid()
            val itemId = uuid()
            val segment = GalleryTranslationSegment("source", "Перевод عربي", GalleryRect(1, 1, 63, 47),
                listOf(GalleryRect(1, 1, 63, 47)), 1f)
            val item = GalleryTranslationItemEntity(itemId, taskId, 0, "", displayName = "owned.png",
                status = GalleryItemStatus.SUCCEEDED, processedWidth = 64, processedHeight = 48,
                segmentsJson = json.encodeToString(listOf(segment)), updatedAtMs = 7)
            val directory = Files.createDirectories(owned.cache.resolve(GalleryTransientFiles.PREVIEW_ROOT).resolve(taskId))
            val seedCache = Files.createDirectory(owned.base.resolve("preview-seed-cache"))
            val seedContext = object : ContextWrapper(owned.context) {
                override fun getCacheDir(): File = seedCache.toFile()
            }
            val source = Bitmap.createBitmap(64, 48, Bitmap.Config.ARGB_8888).apply { eraseColor(Color.WHITE) }
            try {
                dao.insertTaskWithItems(task(taskId), listOf(item))
                val seedStore = GalleryTranslatedPreviewStore(seedContext, decoder, renderer, json, dao)
                assertTrue(seedStore.storeTranslatedPreview(item, source, 64, 48, listOf(segment), Settings()))
                val seedDirectory = seedCache.resolve(GalleryTransientFiles.PREVIEW_ROOT).resolve(taskId)
                val seed = Files.newDirectoryStream(seedDirectory, "*.jpg").use { it.single() }
                val jpg = Files.move(seed, directory.resolve(seed.fileName))
                val before = Files.readAllBytes(jpg)
                val oldTemp = tempPreview(directory)

                val store = GalleryTranslatedPreviewStore(owned.context, decoder, renderer, json, dao)
                val thumbnail = requireNotNull(store.loadTranslatedThumbnail(item, Settings()))
                thumbnail.recycle()
                assertFalse(Files.exists(oldTemp, NOFOLLOW_LINKS))
                assertArrayEquals(before, Files.readAllBytes(jpg))

                assertTrue(store.storeTranslatedPreview(item, source, 64, 48, listOf(segment), Settings()))
                val generated = requireNotNull(BitmapFactory.decodeFile(jpg.toString()))
                assertEquals(64, generated.width)
                assertEquals(48, generated.height)
                generated.recycle()
            } finally {
                source.recycle()
                database.close()
                scope.cancel()
                scope.coroutineContext.job.join()
            }
        }
    }

    @Test fun previewCleanupNeverTraversesNestedDirectoriesOrSymlinksAndKeepsUnknownNames() = runBlocking {
        withOwnedCache { owned ->
            val root = Files.createDirectories(owned.cache.resolve(GalleryTransientFiles.PREVIEW_ROOT))
            val task = Files.createDirectory(root.resolve(uuid()))
            val stale = tempPreview(task)
            val unknown = task.resolve("user-retained.tmp").also { Files.write(it, PAYLOAD) }
            val nested = tempPreview(Files.createDirectory(task.resolve("nested")))
            val outside = tempPreview(Files.createDirectory(owned.base.resolve("outside")))
            val taskLink = root.resolve(uuid())
            Files.createSymbolicLink(taskLink, outside.parent)
            val fileLink = task.resolve("${uuid()}-123.tmp")
            Files.createSymbolicLink(fileLink, outside)
            preparePreviews(owned)
            assertFalse(Files.exists(stale, NOFOLLOW_LINKS))
            for (path in listOf(unknown, nested, outside)) assertArrayEquals(PAYLOAD, Files.readAllBytes(path))
            assertTrue(Files.isSymbolicLink(taskLink))
            assertTrue(Files.isSymbolicLink(fileLink))
        }
    }

    @Test fun symlinkedPreviewAndExportRootsAreRetainedAndCannotRedirectNewTemporaryFiles() = runBlocking {
        withOwnedCache { owned ->
            val outside = Files.createDirectory(owned.base.resolve("outside"))
            val retained = outside.resolve("encoded-saved.png").also { Files.write(it, PAYLOAD) }
            Files.createSymbolicLink(owned.cache.resolve(GalleryTransientFiles.PREVIEW_ROOT), outside)
            Files.createSymbolicLink(owned.cache.resolve(GalleryTransientFiles.EXPORT_ROOT), outside)
            preparePreviews(owned)
            try {
                GalleryTransientFiles.previewTaskDirectory(owned.cache.toFile(), uuid())
                fail("A symlink cannot become a preview directory")
            } catch (_: IOException) { }
            var exportEntered = false
            try {
                GalleryTransientFiles.withExportStaging(owned.cache.toFile()) { exportEntered = true }
                fail("A symlink cannot become an export staging directory")
            } catch (_: IOException) { }
            assertFalse(exportEntered)
            assertArrayEquals(PAYLOAD, Files.readAllBytes(retained))
            assertEquals(listOf(retained.fileName.toString()), Files.newDirectoryStream(outside).use { paths ->
                paths.map { it.fileName.toString() }.toList()
            })
        }
    }

    @Test fun exportCleanupOnlyDeletesDedicatedEncodedPngsAndRetainsLegacyCacheFiles() = runBlocking {
        withOwnedCache { owned ->
            val root = Files.createDirectory(owned.cache.resolve(GalleryTransientFiles.EXPORT_ROOT))
            val stale = File.createTempFile(GalleryTransientFiles.EXPORT_PREFIX, ".png", root.toFile()).toPath()
            Files.write(stale, PAYLOAD)
            val legacy = owned.cache.resolve("gallery_translated_123.png").also { Files.write(it, PAYLOAD) }
            val jpg = root.resolve("retained.jpg").also { Files.write(it, PAYLOAD) }
            val unknown = root.resolve("user-retained.png").also { Files.write(it, PAYLOAD) }
            val nested = Files.createDirectory(root.resolve("nested")).resolve("encoded-retained.png")
                .also { Files.write(it, PAYLOAD) }
            val outside = owned.base.resolve("user.png").also { Files.write(it, PAYLOAD) }
            val link = root.resolve("encoded-link.png")
            Files.createSymbolicLink(link, outside)
            GalleryTransientFiles.withExportStaging(owned.cache.toFile()) { directory ->
                assertEquals(root, directory.toPath())
                assertFalse(Files.exists(stale, NOFOLLOW_LINKS))
                val bitmap = Bitmap.createBitmap(3, 2, Bitmap.Config.ARGB_8888).apply { eraseColor(0x80402010.toInt()) }
                val currentFile = File.createTempFile(GalleryTransientFiles.EXPORT_PREFIX, ".png", directory)
                try {
                    currentFile.outputStream().use {
                        assertTrue(bitmap.compress(Bitmap.CompressFormat.PNG, 100, it))
                    }
                    val decoded = requireNotNull(BitmapFactory.decodeFile(currentFile.absolutePath))
                    assertEquals(3, decoded.width)
                    assertEquals(2, decoded.height)
                    assertTrue(decoded.hasAlpha())
                    decoded.recycle()
                } finally {
                    bitmap.recycle()
                    assertTrue(currentFile.delete())
                }
            }
            for (path in listOf(legacy, jpg, unknown, nested, outside)) assertArrayEquals(PAYLOAD, Files.readAllBytes(path))
            assertTrue(Files.isSymbolicLink(link))
        }
    }

    @Test fun concurrentExportAndCancelledWaiterNeverDeleteAnActiveEncodedPng() = runBlocking {
        withOwnedCache { owned -> withTimeout(5_000) {
            val active = CompletableDeferred<File>()
            val release = CompletableDeferred<Unit>()
            val first = async(Dispatchers.IO) {
                GalleryTransientFiles.withExportStaging(owned.cache.toFile()) { directory ->
                    val file = File.createTempFile(GalleryTransientFiles.EXPORT_PREFIX, ".png", directory)
                    try {
                        file.writeBytes(PAYLOAD)
                        active.complete(file)
                        release.await() // The real gate remains held through the encoded file's lifetime.
                        assertArrayEquals(PAYLOAD, file.readBytes())
                    } finally { assertTrue(file.delete()) }
                }
            }
            val live = active.await()
            val waiting = CompletableDeferred<Unit>()
            val entered = CompletableDeferred<Unit>()
            val second = async(Dispatchers.IO) {
                waiting.complete(Unit)
                GalleryTransientFiles.withExportStaging(owned.cache.toFile()) { entered.complete(Unit) }
            }
            try {
                waiting.await()
                assertNull(withTimeoutOrNull(200) { entered.await() })
                second.cancelAndJoin()
                assertArrayEquals(PAYLOAD, live.readBytes())
            } finally { release.complete(Unit) }
            first.await()
            assertFalse(live.exists())
            GalleryTransientFiles.withExportStaging(owned.cache.toFile()) { assertTrue(it.isDirectory) }
        } }
    }

    @Test fun cancelledPreviewPreparationDoesNotPublishReadyAndNextAccessCanRemoveOldTemp() = runBlocking {
        withOwnedCache { owned -> withTimeout(5_000) {
            val stale = tempPreview(Files.createDirectories(owned.cache.resolve(GalleryTransientFiles.PREVIEW_ROOT).resolve(uuid())))
            val held = CompletableDeferred<Unit>()
            val release = CompletableDeferred<Unit>()
            val owner = async(Dispatchers.IO) {
                GalleryTransientFiles.previewGenerationMutex.withLock { held.complete(Unit); release.await() }
            }
            held.await()
            val requested = CompletableDeferred<Unit>()
            val canceled = async(Dispatchers.IO) {
                requested.complete(Unit)
                preparePreviews(owned)
            }
            try {
                requested.await()
                canceled.cancelAndJoin()
                assertArrayEquals(PAYLOAD, Files.readAllBytes(stale))
            } finally { release.complete(Unit) }
            owner.await()
            preparePreviews(owned)
            assertFalse(Files.exists(stale, NOFOLLOW_LINKS))
        } }
    }

    private suspend fun preparePreviews(owned: OwnedCache) = withContext(Dispatchers.IO) {
        GalleryTransientFiles.previewGenerationMutex.withLock {
            GalleryTransientFiles.preparePreviews(owned.cache.toFile())
        }
    }

    private fun task(id: String) = GalleryTranslationTaskEntity(id = id, createdAtMs = 1,
        status = GalleryTaskStatus.SUCCEEDED, sourceLang = "en", targetLang = "ru", ocrEngine = "ML_KIT_LATIN",
        translatorEngine = "GOOGLE", presetName = "owned", settingsSnapshotJson = "{}", totalCount = 1)

    private fun tempPreview(directory: Path): Path = File.createTempFile("${uuid()}-", ".tmp", directory.toFile())
        .toPath().also { Files.write(it, PAYLOAD) }

    private suspend fun withOwnedCache(block: suspend (OwnedCache) -> Unit) {
        val base = Files.createTempDirectory(target.cacheDir.toPath(), "gallery-transient-owned-")
        val cache = Files.createDirectory(base.resolve("cache"))
        val files = Files.createDirectory(base.resolve("files"))
        val context = object : ContextWrapper(target) {
            override fun getCacheDir(): File = cache.toFile()
            override fun getFilesDir(): File = files.toFile()
        }
        try { block(OwnedCache(base, cache, context)) }
        finally { withContext(NonCancellable + Dispatchers.IO) {
            Files.walkFileTree(base, object : SimpleFileVisitor<Path>() {
                override fun visitFile(file: Path, attrs: BasicFileAttributes): FileVisitResult {
                    check(file.startsWith(base))
                    Files.delete(file)
                    return FileVisitResult.CONTINUE
                }
                override fun postVisitDirectory(dir: Path, failure: IOException?): FileVisitResult {
                    if (failure != null) throw failure
                    check(dir.startsWith(base))
                    Files.delete(dir)
                    return FileVisitResult.CONTINUE
                }
            })
        } }
    }

    private data class OwnedCache(val base: Path, val cache: Path, val context: Context)
    private fun uuid() = UUID.randomUUID().toString()
    private companion object { val PAYLOAD = byteArrayOf(17, 31, 47, 61) }
}
