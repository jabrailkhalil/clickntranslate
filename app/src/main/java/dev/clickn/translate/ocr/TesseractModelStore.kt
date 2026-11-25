package dev.clickn.translate.ocr

import android.content.Context
import dagger.hilt.android.qualifiers.ApplicationContext
import dev.clickn.translate.download.ModelFileDownloader
import java.io.File
import java.io.IOException
import java.nio.file.Files
import java.nio.file.StandardCopyOption
import java.util.Comparator
import javax.inject.Inject
import javax.inject.Singleton
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.runInterruptible
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext

enum class TesseractModelFailure { DOWNLOAD, INVALID, MISSING }
data class TesseractModelState(val ready: Boolean = false, val busy: Boolean = false,
                               val progress: Float? = null, val error: TesseractModelFailure? = null)
class TesseractModelException(val failure: TesseractModelFailure, cause: Throwable? = null) : IOException(
    when (failure) {
        TesseractModelFailure.MISSING -> "Arabic OCR models are not installed."
        TesseractModelFailure.INVALID -> "Arabic OCR model verification failed."
        TesseractModelFailure.DOWNLOAD -> "Arabic OCR models could not be downloaded."
    }, cause)

/** Downloads only on explicit request. Both verified languages are published as one directory. */
@Singleton
class TesseractModelStore internal constructor(
    private val root: File,
    private val downloader: ModelFileDownloader,
    private val specs: List<TesseractModelSpec>,
) {
    @Inject constructor(@ApplicationContext context: Context, downloader: ModelFileDownloader) :
        this(File(context.filesDir, "models/tesseract-arabic"), downloader, TesseractModelFiles.models)

    private val mutex = Mutex()
    private val mutableState = MutableStateFlow(TesseractModelState())
    val state: StateFlow<TesseractModelState> = mutableState.asStateFlow()
    private val installed = File(root, "verified-${TesseractModelFiles.REVISION}")

    init {
        require(specs.map { it.language }.toSet() == setOf("ara", "eng") && specs.size == 2)
        require(specs.all { it.bytes in 1..32L * 1024 * 1024 && it.sha256.matches(Regex("[a-f0-9]{64}")) })
    }

    suspend fun refresh() = mutex.withLock {
        val failure = checkedInspection()
        mutableState.value = TesseractModelState(ready = failure == null, error = failure)
    }

    suspend fun download() = operation(TesseractModelFailure.DOWNLOAD) {
        if (runInterruptible(Dispatchers.IO) { inspect() } == null) return@operation
        val staging = runInterruptible(Dispatchers.IO) {
            check(root.isDirectory || root.mkdirs())
            // Stable staging paths also keep the shared downloader's destination locks bounded.
            File(root, ".staging-pair").also {
                if (it.exists()) removeOwnedTree(it)
                check(it.mkdir())
                check(File(it, "tessdata").mkdir())
            }
        }
        try {
            var completed = 0L
            val total = specs.sumOf { it.bytes }
            for (spec in specs) {
                currentCoroutineContext().ensureActive()
                val target = File(staging, "tessdata/${spec.language}.traineddata")
                downloader.download(spec.url, target,
                    validate = { candidate ->
                        if (!TesseractModelFiles.verified(candidate, spec)) throw TesseractModelException(TesseractModelFailure.INVALID)
                        null
                    },
                    onProgress = { downloaded, declared ->
                        // Reject oversized declarations immediately and bound unknown-length transfers
                        // at the shared downloader's progress checkpoints. Publication is exact-size.
                        if (downloaded > spec.bytes || declared > spec.bytes) throw TesseractModelException(TesseractModelFailure.INVALID)
                        mutableState.value = mutableState.value.copy(progress = ((completed + downloaded).toDouble() / total).toFloat().coerceIn(0f, 1f))
                    })
                completed += spec.bytes
            }
            currentCoroutineContext().ensureActive()
            runInterruptible(Dispatchers.IO) {
                if (inspect(staging) != null) throw TesseractModelException(TesseractModelFailure.INVALID)
                // A valid existing bundle is never replaced. A corrupt bundle cannot be leased.
                if (installed.exists()) removeOwnedTree(installed)
                Files.move(staging.toPath(), installed.toPath(), StandardCopyOption.ATOMIC_MOVE)
            }
        } finally {
            withContext(NonCancellable + Dispatchers.IO) { if (staging.exists()) removeOwnedTree(staging) }
        }
    }

    suspend fun delete() = operation(TesseractModelFailure.INVALID) {
        runInterruptible(Dispatchers.IO) {
            if (installed.exists()) removeOwnedTree(installed)
            root.listFiles().orEmpty().filter { it.name.startsWith(".staging-") }.forEach(::removeOwnedTree)
        }
    }

    /** The lease covers verification, native init, recognition and native recycle. */
    internal suspend fun <T> withOcrModels(action: suspend (String) -> T): T = mutex.withLock {
        val failure = checkedInspection()
        mutableState.value = mutableState.value.copy(ready = failure == null, error = failure)
        if (failure != null) throw TesseractModelException(failure)
        currentCoroutineContext().ensureActive()
        action(installed.absolutePath)
    }

    private suspend fun operation(fallback: TesseractModelFailure, action: suspend () -> Unit) = mutex.withLock {
        mutableState.value = mutableState.value.copy(busy = true, progress = 0f, error = null)
        var error: TesseractModelFailure? = null
        try {
            action()
        } catch (cancelled: CancellationException) {
            throw cancelled
        } catch (failure: Exception) {
            currentCoroutineContext().ensureActive()
            // The shared downloader wraps validation IO failures. Keep our authoritative
            // missing/invalid classification without trusting messages or unbounded causes.
            val category = generateSequence<Throwable>(failure) { it.cause }.take(8)
                .filterIsInstance<TesseractModelException>().firstOrNull()?.failure ?: fallback
            error = category
            throw if (failure is TesseractModelException) failure else TesseractModelException(category, failure)
        } finally {
            withContext(NonCancellable) {
                val installedFailure = runCatching { runInterruptible(Dispatchers.IO) { inspect() } }
                    .getOrDefault(TesseractModelFailure.INVALID)
                mutableState.value = TesseractModelState(ready = installedFailure == null, error = error)
            }
        }
    }

    private fun inspect(bundle: File = installed): TesseractModelFailure? {
        if (!bundle.exists()) return TesseractModelFailure.MISSING
        if (Files.isSymbolicLink(bundle.toPath()) || !bundle.isDirectory) return TesseractModelFailure.INVALID
        val data = File(bundle, "tessdata")
        if (Files.isSymbolicLink(data.toPath()) || !data.isDirectory) return TesseractModelFailure.INVALID
        for (spec in specs) {
            val file = File(data, "${spec.language}.traineddata")
            if (!file.exists()) return TesseractModelFailure.MISSING
            if (!TesseractModelFiles.verified(file, spec)) return TesseractModelFailure.INVALID
        }
        return null
    }

    private suspend fun checkedInspection(): TesseractModelFailure? = try {
        runInterruptible(Dispatchers.IO) { inspect() }
    } catch (cancelled: CancellationException) { throw cancelled }
    catch (failure: IOException) {
        currentCoroutineContext().ensureActive()
        mutableState.value = mutableState.value.copy(ready = false, error = TesseractModelFailure.INVALID)
        throw TesseractModelException(TesseractModelFailure.INVALID, failure)
    }

    private fun removeOwnedTree(directory: File) {
        val base = root.toPath().toAbsolutePath().normalize()
        val target = directory.toPath().toAbsolutePath().normalize()
        check(target != base && target.startsWith(base))
        // Files.walk does not follow symlinks; no external app directory is traversed.
        Files.walk(target).use { paths -> paths.sorted(Comparator.reverseOrder()).forEach(Files::deleteIfExists) }
    }
}
