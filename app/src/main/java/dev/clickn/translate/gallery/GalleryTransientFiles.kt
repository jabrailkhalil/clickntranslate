package dev.clickn.translate.gallery

import java.io.File
import java.io.IOException
import java.nio.file.DirectoryIteratorException
import java.nio.file.FileAlreadyExistsException
import java.nio.file.Files
import java.nio.file.LinkOption.NOFOLLOW_LINKS
import java.nio.file.Path
import java.nio.file.attribute.BasicFileAttributes
import java.util.UUID
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext

/** Process-local ownership gates for rebuildable preview temps and private export staging only. */
internal object GalleryTransientFiles {
    const val PREVIEW_ROOT = "gallery-translated-previews-v1"
    const val EXPORT_ROOT = "gallery-translation-export-staging-v1"
    const val EXPORT_PREFIX = "encoded-"

    val previewGenerationMutex = Mutex()
    private val exportMutex = Mutex()
    // Each gate protects its prepared root and every temporary file's complete lifetime.
    private var preparedPreviewRoot: Path? = null
    private var preparedExportRoot: Path? = null

    /** Caller holds previewGenerationMutex on IO, before reading or generating a preview. */
    suspend fun preparePreviews(cacheDir: File) {
        val root = namespace(cacheDir, PREVIEW_ROOT)
        if (preparedPreviewRoot == root) return
        val operation = currentCoroutineContext()
        operation.ensureActive()
        ignoreFileSystemFailure {
            if (plainDirectory(root.parent) && plainDirectory(root)) {
                Files.newDirectoryStream(root).use { tasks ->
                    for (task in tasks) {
                        operation.ensureActive()
                        if (!canonicalUuid(task.fileName.toString())) continue
                        ignoreFileSystemFailure {
                            if (plainDirectory(task)) {
                                deleteTemporaryFiles(task, ::previewTemporaryName) { operation.ensureActive() }
                            }
                        }
                    }
                }
            }
        }
        operation.ensureActive()
        preparedPreviewRoot = root
    }

    /** A second exporter cannot scan or create staging files while the first is still using one. */
    suspend fun <T> withExportStaging(cacheDir: File, block: suspend (File) -> T): T =
        withContext(Dispatchers.IO) {
            exportMutex.withLock {
                val root = namespace(cacheDir, EXPORT_ROOT)
                val operation = currentCoroutineContext()
                if (preparedExportRoot != root) {
                    operation.ensureActive()
                    ignoreFileSystemFailure {
                        if (plainDirectory(root.parent) && plainDirectory(root)) {
                            deleteTemporaryFiles(root, ::exportTemporaryName) { operation.ensureActive() }
                        }
                    }
                    operation.ensureActive()
                    preparedExportRoot = root
                }
                ensurePlainDirectory(root.parent, create = false)
                ensurePlainDirectory(root)
                // The caller's finally removes its encoded file before this gate is released.
                block(root.toFile())
            }
        }

    /** Do not let a preexisting root/task symlink redirect a new preview outside private cache. */
    fun previewTaskDirectory(cacheDir: File, taskId: String): File {
        val root = namespace(cacheDir, PREVIEW_ROOT)
        val task = root.resolve(taskId)
        require(task.parent == root && task.fileName.toString() == taskId && taskId != "." && taskId != "..")
        ensurePlainDirectory(root.parent, create = false)
        ensurePlainDirectory(root)
        ensurePlainDirectory(task)
        return task.toFile()
    }

    private fun namespace(cacheDir: File, name: String): Path =
        cacheDir.toPath().toAbsolutePath().normalize().resolve(name)

    private fun plainDirectory(path: Path): Boolean {
        val attrs = Files.readAttributes(path, BasicFileAttributes::class.java, NOFOLLOW_LINKS)
        return attrs.isDirectory && !attrs.isSymbolicLink
    }

    private fun ensurePlainDirectory(path: Path, create: Boolean = true) {
        if (create) {
            try {
                Files.createDirectory(path)
            } catch (_: FileAlreadyExistsException) {
                // Validate the existing object without following links.
            }
        }
        if (!plainDirectory(path)) throw IOException("Gallery private cache directory is unavailable.")
    }

    private fun deleteTemporaryFiles(directory: Path, ownedName: (String) -> Boolean, checkpoint: () -> Unit) {
        Files.newDirectoryStream(directory).use { files ->
            for (file in files) {
                checkpoint()
                if (!ownedName(file.fileName.toString())) continue
                ignoreFileSystemFailure {
                    val attrs = Files.readAttributes(file, BasicFileAttributes::class.java, NOFOLLOW_LINKS)
                    if (attrs.isRegularFile && !attrs.isSymbolicLink) Files.delete(file)
                }
            }
        }
    }

    private fun previewTemporaryName(name: String): Boolean =
        name.length > 41 && name[36] == '-' && canonicalUuid(name.take(36)) && name.endsWith(".tmp")

    private fun exportTemporaryName(name: String): Boolean =
        name.startsWith(EXPORT_PREFIX) && name.endsWith(".png") && name.length > EXPORT_PREFIX.length + 4

    private fun canonicalUuid(name: String): Boolean =
        runCatching { UUID.fromString(name).toString() == name }.getOrDefault(false)

    private fun ignoreFileSystemFailure(block: () -> Unit) {
        try {
            block()
        } catch (_: IOException) {
            // Best effort maintenance must not prevent a new generation/export attempt.
        } catch (_: DirectoryIteratorException) {
            // A directory stream can wrap an I/O failure during iteration.
        } catch (_: SecurityException) {
            // Keep inaccessible objects; never broaden the cleanup boundary.
        }
    }
}
