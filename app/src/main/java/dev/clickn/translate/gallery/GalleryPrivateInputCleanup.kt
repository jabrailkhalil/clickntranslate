package dev.clickn.translate.gallery

import java.io.IOException
import java.nio.file.FileVisitResult
import java.nio.file.Files
import java.nio.file.LinkOption.NOFOLLOW_LINKS
import java.nio.file.NoSuchFileException
import java.nio.file.Path
import java.nio.file.SimpleFileVisitor
import java.nio.file.attribute.BasicFileAttributes
import java.util.UUID
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext

/** One SQL snapshot of references, without loading OCR/translation payloads. */
data class GalleryPrivateInputReference(val taskId: String, val localPath: String)

/** All repository instances share this gate. It does not introduce a new work queue. */
internal object GalleryPrivateInputAccess {
    private val mutex = Mutex()
    // The app has one files directory per process. Keep no unbounded root/URI registry.
    @Volatile private var preparedFilesDir: Path? = null

    suspend fun prepare(filesDir: Path, references: suspend () -> List<GalleryPrivateInputReference>) {
        withContext(Dispatchers.IO) {
            // Ordinary reads must not wait behind a long input copy after the startup scan.
            if (preparedFilesDir != filesDir.toAbsolutePath().normalize()) {
                mutex.withLock { prepareLocked(filesDir, references) }
            }
        }
    }

    suspend fun <T> publication(
        filesDir: Path,
        references: suspend () -> List<GalleryPrivateInputReference>,
        block: suspend () -> T,
    ): T = withContext(Dispatchers.IO) {
        mutex.withLock {
            prepareLocked(filesDir, references)
            block()
        }
    }

    suspend fun <T> rollback(block: suspend () -> T): T = withContext(Dispatchers.IO) {
        mutex.withLock { block() }
    }

    private suspend fun prepareLocked(filesDir: Path, references: suspend () -> List<GalleryPrivateInputReference>) {
        val normalized = filesDir.toAbsolutePath().normalize()
        if (preparedFilesDir == normalized) return
        // Failure/cancellation while reading Room proves nothing, so no file deletion can start.
        val savedReferences = references()
        val operation = currentCoroutineContext()
        try {
            removeOrphanGalleryInputs(normalized, savedReferences) { operation.ensureActive() }
        } catch (_: IOException) {
            // Best effort private-file maintenance must not disable the existing Gallery workflow.
        } catch (_: SecurityException) {
            // Never broaden the scan because a path could not be inspected.
        }
        operation.ensureActive()
        preparedFilesDir = normalized
    }
}

/** Only immediate UUID directories of the exact input root are eligible; never the root itself. */
internal fun removeOrphanGalleryInputs(
    filesDir: Path,
    references: List<GalleryPrivateInputReference>,
    checkpoint: () -> Unit = {},
) {
    val files = filesDir.toAbsolutePath().normalize()
    val root = files.resolve("gallery_translation")
    if (!Files.isDirectory(root, NOFOLLOW_LINKS) || Files.isSymbolicLink(files)) return
    val taskIds = references.mapTo(HashSet()) { it.taskId }
    val paths = ArrayList<Path>()
    for (reference in references) {
        checkpoint()
        if (reference.localPath.isBlank()) continue // A legacy URI is never opened or revoked.
        val path = try {
            files.fileSystem.getPath(reference.localPath)
        } catch (_: IllegalArgumentException) { return }
        if (!path.isAbsolute) return // Cannot prove the target of a legacy relative path.
        val normalized = path.normalize()
        if (path != normalized) return // Do not collapse a possible symlink/.. reference.
        if (!referenceHasOnlyUnlinkedParents(normalized, files)) return
        paths.add(normalized)
    }
    Files.newDirectoryStream(root).use { children ->
        for (child in children) {
            checkpoint()
            val candidate = child.toAbsolutePath().normalize()
            if (candidate.parent != root || !canonicalUuid(candidate.fileName.toString())) continue
            if (candidate.fileName.toString() in taskIds) continue // Every status, even an empty task.
            if (paths.any { it.startsWith(candidate) || candidate.startsWith(it) }) continue
            if (!Files.isDirectory(candidate, NOFOLLOW_LINKS)) continue
            try {
                if (plainPrivateTree(candidate, checkpoint)) deletePlainPrivateTree(root, candidate, checkpoint)
            } catch (_: IOException) {
                // Leave an unreadable candidate in place; never guess or broaden ownership.
            } catch (_: SecurityException) {
                // Other candidates remain independently eligible.
            }
        }
    }
}

private fun canonicalUuid(name: String): Boolean =
    runCatching { UUID.fromString(name).toString() == name }.getOrDefault(false)

/** Metadata checks only: no toRealPath, canonical-path resolution or symlink target traversal. */
private fun referenceHasOnlyUnlinkedParents(path: Path, trustedFiles: Path): Boolean {
    // A foreign absolute path can alias this root through its ancestors (/data/data vs /data/user/0).
    // Without following/canonicalizing those aliases, absence of a lexical overlap proves nothing.
    if (!path.startsWith(trustedFiles)) return false
    var cursor = trustedFiles
    val remainder = cursor.relativize(path)
    return try {
        if (Files.readAttributes(cursor, BasicFileAttributes::class.java, NOFOLLOW_LINKS).isSymbolicLink) return false
        for (part in remainder) {
            cursor = cursor.resolve(part)
            val attrs = Files.readAttributes(cursor, BasicFileAttributes::class.java, NOFOLLOW_LINKS)
            if (attrs.isSymbolicLink) return false
        }
        true
    } catch (_: NoSuchFileException) {
        true // This currently missing path cannot alias existing orphan data.
    } catch (_: IOException) {
        false
    } catch (_: SecurityException) {
        false
    }
}

/** A directory containing even one symlink/special file is retained as a whole. */
private fun plainPrivateTree(candidate: Path, checkpoint: () -> Unit): Boolean {
    var plain = true
    Files.walkFileTree(candidate, object : SimpleFileVisitor<Path>() {
        override fun preVisitDirectory(dir: Path, attrs: BasicFileAttributes): FileVisitResult {
            checkpoint()
            if (attrs.isSymbolicLink || !attrs.isDirectory) {
                plain = false
                return FileVisitResult.TERMINATE
            }
            return FileVisitResult.CONTINUE
        }
        override fun visitFile(file: Path, attrs: BasicFileAttributes): FileVisitResult {
            checkpoint()
            if (!attrs.isRegularFile || attrs.isSymbolicLink) {
                plain = false
                return FileVisitResult.TERMINATE
            }
            return FileVisitResult.CONTINUE
        }
    })
    return plain
}

private fun deletePlainPrivateTree(root: Path, candidate: Path, checkpoint: () -> Unit) {
    check(candidate.parent == root && candidate != root)
    if (!Files.isDirectory(root, NOFOLLOW_LINKS) || !Files.isDirectory(candidate, NOFOLLOW_LINKS)) return
    Files.walkFileTree(candidate, object : SimpleFileVisitor<Path>() {
        private fun checkOwned(path: Path) {
            checkpoint()
            check(path.startsWith(candidate) && path.startsWith(root) && path != root)
            if (Files.isSymbolicLink(path)) throw IOException("Changed private input tree")
        }
        override fun preVisitDirectory(dir: Path, attrs: BasicFileAttributes): FileVisitResult {
            checkOwned(dir)
            return FileVisitResult.CONTINUE
        }
        override fun visitFile(file: Path, attrs: BasicFileAttributes): FileVisitResult {
            checkOwned(file)
            if (!attrs.isRegularFile) throw IOException("Changed private input tree")
            Files.delete(file)
            return FileVisitResult.CONTINUE
        }
        override fun postVisitDirectory(dir: Path, failure: IOException?): FileVisitResult {
            if (failure != null) throw failure
            checkOwned(dir)
            Files.delete(dir)
            return FileVisitResult.CONTINUE
        }
    })
}
