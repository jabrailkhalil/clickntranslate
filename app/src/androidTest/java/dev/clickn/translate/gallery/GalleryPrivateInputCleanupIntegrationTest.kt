package dev.clickn.translate.gallery

import androidx.room.Room
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import java.io.IOException
import java.nio.file.FileVisitResult
import java.nio.file.Files
import java.nio.file.LinkOption.NOFOLLOW_LINKS
import java.nio.file.Path
import java.nio.file.SimpleFileVisitor
import java.nio.file.attribute.BasicFileAttributes
import java.util.UUID
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitCancellation
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withTimeout
import kotlinx.coroutines.withTimeoutOrNull
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith

/** Isolated Room and private files only; no app tasks, URI access, grants, settings or network. */
@RunWith(AndroidJUnit4::class)
class GalleryPrivateInputCleanupIntegrationTest {
    private val context = InstrumentationRegistry.getInstrumentation().targetContext

    @Test fun retainsEveryDatabaseTaskStatusAndDeletesOnlyAnUnreferencedUuidDirectory() = runBlocking {
        withStore { store ->
            val kept = GalleryTaskStatus.entries.map { status ->
                val id = uuid()
                val input = store.input(id)
                store.dao.insertTask(task(id, status)) // Even an empty QUEUED task is a reference.
                input
            }
            val orphan = store.input(uuid())
            val unknown = store.input("not-an-owned-task-id")
            val unrelated = store.files.resolve("user-retained.bin")
            Files.write(unrelated, PAYLOAD)
            GalleryPrivateInputAccess.prepare(store.files, store.dao::privateInputReferences)
            assertFalse(Files.exists(orphan, NOFOLLOW_LINKS))
            for (path in kept + listOf(unknown, unrelated)) assertArrayEquals(PAYLOAD, Files.readAllBytes(path))
            assertEquals(GalleryTaskStatus.entries.size, store.dao.privateInputReferences().size)
        }
    }

    @Test fun aCrossTaskLocalPathAndLegacyExternalAndUriOnlyRowsRemainUntouched() = runBlocking {
        withStore { store ->
            val crossInput = store.input(uuid()) // No task with this directory name exists.
            val crossOwner = uuid()
            val external = store.files.resolve("legacy-user-image.bin")
            Files.write(external, PAYLOAD)
            val legacyOwner = uuid()
            val uriOwner = uuid()
            store.dao.insertTaskWithItems(task(crossOwner), listOf(item(crossOwner, crossInput.toString())))
            store.dao.insertTaskWithItems(task(legacyOwner), listOf(item(legacyOwner, external.toString())))
            store.dao.insertTaskWithItems(task(uriOwner), listOf(item(uriOwner, "", "content://owned-legacy/image")))
            val before = listOf(crossOwner, legacyOwner, uriOwner).associateWith { store.dao.getItems(it) }
            val orphan = store.input(uuid())
            GalleryPrivateInputAccess.prepare(store.files, store.dao::privateInputReferences)
            assertFalse(Files.exists(orphan, NOFOLLOW_LINKS))
            assertArrayEquals(PAYLOAD, Files.readAllBytes(crossInput))
            assertArrayEquals(PAYLOAD, Files.readAllBytes(external))
            before.forEach { (id, rows) -> assertEquals(rows, store.dao.getItems(id)) }
        }
    }

    @Test fun aNestedSymlinkRetainsItsWholeCandidateAndNeverTouchesItsTarget() = runBlocking {
        withStore { store ->
            val input = store.input(uuid())
            val outside = store.files.resolve("saved-user-image.bin")
            Files.write(outside, PAYLOAD)
            Files.createSymbolicLink(input.parent.resolve("nested-link"), outside)
            val orphan = store.input(uuid())
            GalleryPrivateInputAccess.prepare(store.files, store.dao::privateInputReferences)
            assertArrayEquals(PAYLOAD, Files.readAllBytes(input))
            assertTrue(Files.isSymbolicLink(input.parent.resolve("nested-link")))
            assertArrayEquals(PAYLOAD, Files.readAllBytes(outside))
            assertFalse(Files.exists(orphan, NOFOLLOW_LINKS))
        }
    }

    @Test fun aSymlinkAtTheOwnedRootIsNeverTraversed() = runBlocking {
        withStore { store ->
            val externalRoot = Files.createDirectories(store.base.resolve("saved-external-tree"))
            val outside = Files.createDirectories(externalRoot.resolve(uuid())).resolve("saved.bin")
            Files.write(outside, PAYLOAD)
            Files.createSymbolicLink(store.files.resolve("gallery_translation"), externalRoot)
            GalleryPrivateInputAccess.prepare(store.files, store.dao::privateInputReferences)
            assertArrayEquals(PAYLOAD, Files.readAllBytes(outside))
            assertTrue(Files.isSymbolicLink(store.files.resolve("gallery_translation")))
        }
    }

    @Test fun externalAndAmbiguousRelativeDotAndSymlinkReferencesFailClosed() = runBlocking {
        for (mode in listOf("external", "relative", "dot", "symlink")) withStore { store ->
            val candidate = store.input(uuid())
            val reference = when (mode) {
                "external" -> store.base.resolve("legacy-outside-files.bin").also { Files.write(it, PAYLOAD) }.toString()
                "relative" -> "legacy/relative-image.bin"
                "dot" -> store.files.resolve("legacy/../gallery_translation").resolve(candidate.parent.parent.fileName)
                    .resolve("source/input.bin").toString()
                else -> store.files.resolve("legacy-alias.bin").also { Files.createSymbolicLink(it, candidate) }.toString()
            }
            val owner = uuid()
            store.dao.insertTaskWithItems(task(owner), listOf(item(owner, reference)))
            GalleryPrivateInputAccess.prepare(store.files, store.dao::privateInputReferences)
            assertArrayEquals(PAYLOAD, Files.readAllBytes(candidate))
            assertEquals(reference, store.dao.getItems(owner).single().localPath)
            if (mode == "external") assertArrayEquals(PAYLOAD, Files.readAllBytes(store.base.resolve("legacy-outside-files.bin")))
        }
    }

    @Test fun anUnlinkedPhysicalReferenceProtectsInputReachedThroughAnAncestorAlias() = runBlocking {
        withStore { store ->
            // Resolve only the owned fixture's base so the DB path has no symlink components.
            // The production cleaner never canonicalizes or follows a symlink.
            val physicalBase = store.base.toRealPath()
            val physicalParent = Files.createDirectory(physicalBase.resolve("physical-parent"))
            val physicalFiles = Files.createDirectory(physicalParent.resolve("files"))
            val aliasParent = physicalBase.resolve("alias-parent")
            Files.createSymbolicLink(aliasParent, physicalParent)
            val aliasFiles = aliasParent.resolve("files")
            assertFalse(Files.isSymbolicLink(aliasFiles)) // The symlink is an ancestor, not this directory.
            val folder = uuid()
            val input = Files.createDirectories(physicalFiles.resolve("gallery_translation").resolve(folder).resolve("source"))
                .resolve("input.bin")
            Files.write(input, PAYLOAD)
            val owner = uuid()
            store.dao.insertTaskWithItems(task(owner), listOf(item(owner, input.toString())))
            GalleryPrivateInputAccess.prepare(aliasFiles, store.dao::privateInputReferences)
            assertArrayEquals(PAYLOAD, Files.readAllBytes(input))
            assertEquals(input.toString(), store.dao.getItems(owner).single().localPath)
        }
    }

    @Test fun aPausedFirstScanAndALiveImportPublicationUseTheSameProcessMutex() = runBlocking {
        withStore { store -> withTimeout(5_000) {
            val orphan = store.input(uuid())
            val referencesRead = CompletableDeferred<Unit>()
            val resumeScan = CompletableDeferred<Unit>()
            val scan = async {
                GalleryPrivateInputAccess.prepare(store.files) {
                    val snapshot = store.dao.privateInputReferences() // Actual Room read, not a fake count.
                    referencesRead.complete(Unit)
                    resumeScan.await()
                    snapshot
                }
            }
            referencesRead.await()
            val id = uuid()
            val requested = CompletableDeferred<Unit>()
            val published = CompletableDeferred<Path>()
            val writer = async {
                requested.complete(Unit)
                GalleryPrivateInputAccess.publication(store.files, store.dao::privateInputReferences) {
                    val input = store.input(id)
                    store.dao.insertTaskWithItems(task(id, GalleryTaskStatus.QUEUED), listOf(item(id, input.toString())))
                    published.complete(input)
                    input
                }
            }
            try {
                requested.await()
                assertNull(withTimeoutOrNull(200) { published.await() })
                assertFalse(Files.exists(store.files.resolve("gallery_translation").resolve(id), NOFOLLOW_LINKS))
            } finally { resumeScan.complete(Unit) }
            scan.await()
            val input = writer.await()
            assertArrayEquals(PAYLOAD, Files.readAllBytes(input))
            assertEquals(GalleryTaskStatus.QUEUED, store.dao.getTask(id)?.status)
            assertFalse(Files.exists(orphan, NOFOLLOW_LINKS))
        } }
    }

    @Test fun canceledReferenceReadDoesNotDeleteAndTheNextAccessRetriesMaintenance() = runBlocking {
        withStore { store -> withTimeout(5_000) {
            val orphan = store.input(uuid())
            val reading = CompletableDeferred<Unit>()
            val first = async {
                GalleryPrivateInputAccess.prepare(store.files) {
                    store.dao.privateInputReferences()
                    reading.complete(Unit)
                    awaitCancellation()
                }
            }
            reading.await()
            first.cancelAndJoin()
            assertArrayEquals(PAYLOAD, Files.readAllBytes(orphan))
            GalleryPrivateInputAccess.prepare(store.files, store.dao::privateInputReferences)
            assertFalse(Files.exists(orphan, NOFOLLOW_LINKS))
        } }
    }

    private fun task(id: String, status: GalleryTaskStatus = GalleryTaskStatus.FAILED) = GalleryTranslationTaskEntity(
        id = id, createdAtMs = 1, status = status, sourceLang = "en", targetLang = "ru",
        ocrEngine = "ML_KIT_LATIN", translatorEngine = "GOOGLE", presetName = "owned",
        settingsSnapshotJson = "{}", totalCount = 0,
    )

    private fun item(owner: String, path: String, sourceUri: String = "") = GalleryTranslationItemEntity(
        id = uuid(), taskId = owner, position = 0, sourceUri = sourceUri, localPath = path,
        displayName = "owned.bin", status = GalleryItemStatus.CANCELED, updatedAtMs = 1,
    )

    private suspend fun withStore(body: suspend (Store) -> Unit) {
        val base = Files.createTempDirectory(context.cacheDir.toPath(), "gallery-cleanup-owned-")
        val files = Files.createDirectory(base.resolve("files"))
        val database = Room.inMemoryDatabaseBuilder(context, GalleryTranslationDatabase::class.java).build()
        try { body(Store(base, files, database.galleryTranslationDao())) }
        finally {
            database.close()
            // Test fixture cleanup also never follows links into a different tree.
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
        }
    }

    private class Store(val base: Path, val files: Path, val dao: GalleryTranslationDao) {
        fun input(id: String): Path {
            val directory = Files.createDirectories(files.resolve("gallery_translation").resolve(id).resolve("source"))
            return directory.resolve("input.bin").also { Files.write(it, PAYLOAD) }
        }
    }

    private fun uuid() = UUID.randomUUID().toString()

    private companion object { val PAYLOAD = byteArrayOf(11, 29, 47, 83) }
}
