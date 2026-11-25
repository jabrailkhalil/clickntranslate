package dev.clickn.translate.gallery

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext
import kotlinx.serialization.json.Json

/** Older builds called a partly translated image SUCCEEDED. Restore its explicit retry action. */
internal class GalleryLegacyResultRepair(
    private val dao: GalleryTranslationDao,
    private val json: Json,
    private val message: (translated: Int, total: Int) -> String,
) {
    private val mutex = Mutex()
    private var finished = false

    suspend fun run() = withContext(Dispatchers.IO) {
        mutex.withLock {
            if (finished) return@withLock
            var afterId = ""
            while (true) {
                currentCoroutineContext().ensureActive()
                val page = dao.legacyCompletedResults(afterId)
                if (page.isEmpty()) break
                repairItems(page)
                afterId = page.last().id
            }
            finished = true
        }
    }

    /** An old active task may become terminal after the initial history scan. */
    suspend fun repairTask(taskId: String) = withContext(Dispatchers.IO) {
        mutex.withLock { repairItems(dao.getItems(taskId)) }
    }

    private suspend fun repairItems(items: List<GalleryTranslationItemEntity>) {
        for (item in items) {
            currentCoroutineContext().ensureActive()
            if (item.status != GalleryItemStatus.SUCCEEDED) continue
            val segments = GallerySegmentRecovery.decode(item.segmentsJson, json) ?: continue
            val missing = GallerySegmentRecovery.missingIndices(segments).size
            if (missing == 0) continue
            val total = segments.count { it.sourceText.isNotBlank() }
            dao.repairIncompleteResult(item, message(total - missing, total), System.currentTimeMillis())
        }
    }
}
