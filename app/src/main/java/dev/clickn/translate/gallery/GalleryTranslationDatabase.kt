// Modified for Click'n'Translate on October 3, 2026.
package dev.clickn.translate.gallery

import androidx.room.Dao
import androidx.room.Database
import androidx.room.Entity
import androidx.room.ForeignKey
import androidx.room.Index
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.PrimaryKey
import androidx.room.Query
import androidx.room.RoomDatabase
import androidx.room.Transaction
import androidx.room.TypeConverter
import androidx.room.TypeConverters
import kotlinx.coroutines.flow.Flow

@Entity(tableName = "gallery_translation_tasks")
data class GalleryTranslationTaskEntity(
    @PrimaryKey val id: String,
    val createdAtMs: Long,
    // First processing start, or admission of the latest explicit retry; not cumulative active time.
    val startedAtMs: Long? = null,
    val finishedAtMs: Long? = null,
    val status: GalleryTaskStatus = GalleryTaskStatus.QUEUED,
    val sourceLang: String,
    val targetLang: String,
    val ocrEngine: String,
    val translatorEngine: String,
    val presetName: String,
    val settingsSnapshotJson: String,
    val scopePackage: String = "",
    val scopeLabel: String = "",
    val totalCount: Int,
    val completedCount: Int = 0,
    val successCount: Int = 0,
    val failedCount: Int = 0,
    val currentItemName: String = "",
    val lastError: String = "",
)

@Entity(
    tableName = "gallery_translation_items",
    foreignKeys = [
        ForeignKey(
            entity = GalleryTranslationTaskEntity::class,
            parentColumns = ["id"],
            childColumns = ["taskId"],
            onDelete = ForeignKey.CASCADE,
        ),
    ],
    indices = [
        Index(value = ["taskId", "position"], unique = true),
        Index(value = ["taskId", "status"]),
        Index(value = ["sourceUri"]),
    ],
)
data class GalleryTranslationItemEntity(
    @PrimaryKey val id: String,
    val taskId: String,
    val position: Int,
    val sourceUri: String,
    val localPath: String = "",
    val displayName: String,
    val status: GalleryItemStatus = GalleryItemStatus.QUEUED,
    val attemptCount: Int = 0,
    val originalWidth: Int = 0,
    val originalHeight: Int = 0,
    val processedWidth: Int = 0,
    val processedHeight: Int = 0,
    val sourceText: String = "",
    val translatedText: String = "",
    val segmentsJson: String = "[]",
    val errorMessage: String = "",
    val updatedAtMs: Long,
)

data class GalleryProgressRow(
    val total: Int,
    val succeeded: Int,
    val failed: Int,
    val canceled: Int = 0,
    val partial: Int = 0,
)

@Dao
interface GalleryTranslationDao {
    @Query("SELECT id AS taskId, '' AS localPath FROM gallery_translation_tasks " +
        "UNION ALL SELECT taskId, localPath FROM gallery_translation_items WHERE localPath != ''")
    suspend fun privateInputReferences(): List<GalleryPrivateInputReference>

    @Query("SELECT * FROM gallery_translation_tasks ORDER BY createdAtMs DESC")
    fun observeTasks(): Flow<List<GalleryTranslationTaskEntity>>

    @Query("SELECT * FROM gallery_translation_tasks ORDER BY createdAtMs DESC LIMIT 1")
    fun observeLatestTask(): Flow<GalleryTranslationTaskEntity?>

    @Query(
        "SELECT * FROM gallery_translation_tasks " +
            "ORDER BY CASE WHEN status IN ('QUEUED', 'RUNNING', 'WAITING_RETRY') " +
            "THEN 0 ELSE 1 END, createdAtMs DESC LIMIT 1"
    )
    fun observeFeaturedTask(): Flow<GalleryTranslationTaskEntity?>

    @Query("SELECT * FROM gallery_translation_tasks WHERE id = :taskId LIMIT 1")
    fun observeTask(taskId: String): Flow<GalleryTranslationTaskEntity?>

    @Query("SELECT * FROM gallery_translation_tasks WHERE id = :taskId LIMIT 1")
    suspend fun getTask(taskId: String): GalleryTranslationTaskEntity?

    @Query(
        "SELECT * FROM gallery_translation_items WHERE taskId = :taskId " +
            "ORDER BY position"
    )
    fun observeItems(taskId: String): Flow<List<GalleryTranslationItemEntity>>

    @Query(
        "SELECT * FROM gallery_translation_items WHERE taskId = :taskId " +
            "ORDER BY position"
    )
    suspend fun getItems(taskId: String): List<GalleryTranslationItemEntity>

    @Query("SELECT * FROM gallery_translation_items WHERE id = :itemId LIMIT 1")
    suspend fun getItem(itemId: String): GalleryTranslationItemEntity?

    @Query("SELECT * FROM gallery_translation_items WHERE id = :itemId LIMIT 1")
    fun observeItem(itemId: String): Flow<GalleryTranslationItemEntity?>

    @Query(
        "SELECT * FROM gallery_translation_items WHERE taskId = :taskId " +
            "AND status = 'QUEUED' ORDER BY position LIMIT 1"
    )
    suspend fun nextPendingItem(taskId: String): GalleryTranslationItemEntity?

    @Insert(onConflict = OnConflictStrategy.ABORT)
    suspend fun insertTask(task: GalleryTranslationTaskEntity)

    @Insert(onConflict = OnConflictStrategy.ABORT)
    suspend fun insertItems(items: List<GalleryTranslationItemEntity>)

    @Transaction
    suspend fun insertTaskWithItems(
        task: GalleryTranslationTaskEntity,
        items: List<GalleryTranslationItemEntity>,
    ) {
        insertTask(task)
        insertItems(items)
    }

    @Query(
        "UPDATE gallery_translation_tasks SET status = :status, " +
            "startedAtMs = COALESCE(startedAtMs, :now), finishedAtMs = NULL, lastError = '' " +
            "WHERE id = :taskId AND status IN ('QUEUED', 'RUNNING', 'WAITING_RETRY')"
    )
    suspend fun markTaskRunning(taskId: String, status: GalleryTaskStatus, now: Long): Int

    @Query(
        "UPDATE gallery_translation_tasks SET status = 'WAITING_RETRY', " +
            "currentItemName = '', lastError = :lastError WHERE id = :taskId AND status IN ('QUEUED', 'RUNNING', 'WAITING_RETRY')"
    )
    suspend fun markTaskWaitingRetry(taskId: String, lastError: String)

    @Query(
        "UPDATE gallery_translation_tasks SET status = :status, finishedAtMs = :finishedAtMs, " +
            "currentItemName = '', lastError = :lastError WHERE id = :taskId AND status != 'CANCELED'"
    )
    suspend fun finishTask(
        taskId: String,
        status: GalleryTaskStatus,
        finishedAtMs: Long,
        lastError: String,
    ): Int

    @Query(
        "UPDATE gallery_translation_tasks SET status = 'CANCELED', finishedAtMs = MAX(COALESCE(finishedAtMs, 0) + 1, :now), " +
            "currentItemName = '' WHERE id = :taskId"
    )
    suspend fun cancelTask(taskId: String, now: Long)

    @Query(
        "UPDATE gallery_translation_items SET status = 'CANCELED', updatedAtMs = MAX(updatedAtMs + 1, :now) " +
            "WHERE taskId = :taskId AND status IN ('QUEUED', 'RUNNING')"
    )
    suspend fun cancelPendingItems(taskId: String, now: Long)

    @Transaction
    suspend fun cancelTaskAndItems(taskId: String, now: Long) {
        cancelTask(taskId, now)
        cancelPendingItems(taskId, now)
    }

    @Query(
        "UPDATE gallery_translation_items SET status = 'QUEUED', updatedAtMs = MAX(updatedAtMs + 1, :now) " +
            "WHERE taskId = :taskId AND status = 'RUNNING' AND EXISTS " +
            "(SELECT 1 FROM gallery_translation_tasks t WHERE t.id = :taskId AND t.status IN ('QUEUED', 'RUNNING', 'WAITING_RETRY'))"
    )
    suspend fun resetInterruptedItems(taskId: String, now: Long)

    @Query(
        "UPDATE gallery_translation_items SET status = 'RUNNING', " +
            "attemptCount = attemptCount + 1, errorMessage = '', updatedAtMs = MAX(updatedAtMs + 1, :now) " +
            "WHERE id = :itemId AND taskId = :taskId AND status = 'QUEUED' AND updatedAtMs = :expectedVersion " +
            "AND EXISTS (SELECT 1 FROM gallery_translation_tasks t WHERE t.id = :taskId " +
            "AND t.status IN ('QUEUED', 'RUNNING', 'WAITING_RETRY'))"
    )
    suspend fun markItemRunning(itemId: String, taskId: String, expectedVersion: Long, now: Long): Int

    /** Claim and read its monotonic version in one Room transaction. No new schema column is needed. */
    @Transaction
    suspend fun claimItem(item: GalleryTranslationItemEntity, now: Long): GalleryTranslationItemEntity? {
        if (markItemRunning(item.id, item.taskId, item.updatedAtMs, now) != 1) return null
        updateCurrentItem(item.taskId, item.displayName)
        return getItem(item.id)
    }

    @Query(
        "UPDATE gallery_translation_tasks SET currentItemName = :displayName WHERE id = :taskId AND status != 'CANCELED'"
    )
    suspend fun updateCurrentItem(taskId: String, displayName: String)

    @Query(
        "UPDATE gallery_translation_items SET status = :status, " +
            "originalWidth = :originalWidth, originalHeight = :originalHeight, " +
            "processedWidth = :processedWidth, processedHeight = :processedHeight, " +
            "sourceText = :sourceText, translatedText = :translatedText, " +
            "segmentsJson = :segmentsJson, errorMessage = '', updatedAtMs = MAX(updatedAtMs + 1, :now) " +
            "WHERE id = :itemId AND status = 'RUNNING' AND updatedAtMs = :expectedVersion " +
            "AND EXISTS (SELECT 1 FROM gallery_translation_tasks t WHERE t.id = gallery_translation_items.taskId " +
            "AND t.status IN ('QUEUED', 'RUNNING', 'WAITING_RETRY'))"
    )
    suspend fun completeItem(
        itemId: String,
        expectedVersion: Long,
        originalWidth: Int,
        originalHeight: Int,
        processedWidth: Int,
        processedHeight: Int,
        sourceText: String,
        translatedText: String,
        segmentsJson: String,
        now: Long,
        status: GalleryItemStatus = GalleryItemStatus.SUCCEEDED,
    ): Int

    @Query(
        "UPDATE gallery_translation_items SET status = :status, errorMessage = :message, " +
            "updatedAtMs = MAX(updatedAtMs + 1, :now) WHERE id = :itemId AND status = 'RUNNING' " +
            "AND updatedAtMs = :expectedVersion AND EXISTS (SELECT 1 FROM gallery_translation_tasks t " +
            "WHERE t.id = gallery_translation_items.taskId AND t.status IN ('QUEUED', 'RUNNING', 'WAITING_RETRY'))"
    )
    suspend fun markItemFailed(
        itemId: String,
        expectedVersion: Long,
        status: GalleryItemStatus,
        message: String,
        now: Long,
    ): Int

    @Query(
        "SELECT COUNT(*) AS total, " +
            "COALESCE(SUM(CASE WHEN status = 'SUCCEEDED' THEN 1 ELSE 0 END), 0) AS succeeded, " +
            "COALESCE(SUM(CASE WHEN status = 'FAILED' THEN 1 ELSE 0 END), 0) AS failed, " +
            "COALESCE(SUM(CASE WHEN status = 'CANCELED' THEN 1 ELSE 0 END), 0) AS canceled " +
            ", COALESCE(SUM(CASE WHEN status = 'FAILED' AND translatedText != '' THEN 1 ELSE 0 END), 0) AS partial " +
            "FROM gallery_translation_items WHERE taskId = :taskId"
    )
    suspend fun progress(taskId: String): GalleryProgressRow

    @Query(
        "UPDATE gallery_translation_tasks SET totalCount = :total, " +
            "completedCount = :completed, successCount = :succeeded, failedCount = :failed, " +
            "lastError = CASE WHEN status = 'CANCELED' THEN lastError ELSE :lastError END WHERE id = :taskId"
    )
    suspend fun updateProgress(
        taskId: String,
        total: Int,
        completed: Int,
        succeeded: Int,
        failed: Int,
        lastError: String,
    )

    @Query(
        "UPDATE gallery_translation_items SET status = 'QUEUED', errorMessage = '', " +
            "attemptCount = 0, updatedAtMs = MAX(updatedAtMs + 1, :now) WHERE taskId = :taskId AND status = 'FAILED'"
    )
    suspend fun resetFailedItems(taskId: String, now: Long): Int

    @Query(
        "UPDATE gallery_translation_tasks SET status = 'QUEUED', startedAtMs = :now, finishedAtMs = NULL, " +
            "lastError = '', currentItemName = '', " +
            "totalCount = (SELECT COUNT(*) FROM gallery_translation_items WHERE taskId = :taskId), " +
            "completedCount = (SELECT COUNT(*) FROM gallery_translation_items WHERE taskId = :taskId AND status IN ('SUCCEEDED', 'FAILED')), " +
            "successCount = (SELECT COUNT(*) FROM gallery_translation_items WHERE taskId = :taskId AND status = 'SUCCEEDED'), " +
            "failedCount = (SELECT COUNT(*) FROM gallery_translation_items WHERE taskId = :taskId AND status = 'FAILED') " +
            "WHERE id = :taskId"
    )
    suspend fun resetTaskForRetry(taskId: String, now: Long)

    @Transaction
    suspend fun resetFailedTask(taskId: String, now: Long): Int {
        val count = resetFailedItems(taskId, now)
        if (count > 0) resetTaskForRetry(taskId, now)
        return count
    }

    @Query(
        "UPDATE gallery_translation_items SET status = 'FAILED', errorMessage = :message, " +
            "updatedAtMs = MAX(updatedAtMs + 1, :now) WHERE taskId = :taskId " +
            "AND status IN ('QUEUED', 'RUNNING') AND EXISTS (SELECT 1 FROM gallery_translation_tasks t " +
            "WHERE t.id = :taskId AND t.status != 'CANCELED')"
    )
    suspend fun failPendingConfiguration(taskId: String, message: String, now: Long)

    @Query(
        "UPDATE gallery_translation_items SET status = 'QUEUED', errorMessage = '', attemptCount = 0, " +
            "updatedAtMs = MAX(updatedAtMs + 1, :now) WHERE taskId = :taskId AND id = :itemId " +
            "AND status = 'FAILED' AND updatedAtMs = :expectedVersion"
    )
    suspend fun resetFailedItemIfUnchanged(taskId: String, itemId: String, expectedVersion: Long, now: Long): Int

    @Transaction
    suspend fun failedRetrySelection(taskId: String): GalleryRetrySelection? {
        val task = getTask(taskId) ?: return null
        if (task.status !in setOf(GalleryTaskStatus.FAILED, GalleryTaskStatus.PARTIAL, GalleryTaskStatus.CANCELED)) return null
        val finishedAt = task.finishedAtMs ?: return null
        val items = getItems(taskId).filter { it.status == GalleryItemStatus.FAILED }
            .map { GalleryRetryItem(it.id, it.updatedAtMs) }
        return items.takeIf { it.isNotEmpty() }?.let { GalleryRetrySelection(task.status, finishedAt, it) }
    }

    /** Replaying a WorkRequest cannot reset a newer failure or undo a subsequent user cancellation. */
    @Transaction
    suspend fun resetSelectedFailures(taskId: String, selection: GalleryRetrySelection, now: Long): Int {
        val task = getTask(taskId) ?: return 0
        if (task.status != selection.taskStatus || task.finishedAtMs != selection.finishedAtMs) return 0
        var changed = 0
        selection.items.forEach { changed += resetFailedItemIfUnchanged(taskId, it.id, it.version, now) }
        if (changed > 0) resetTaskForRetry(taskId, now)
        return changed
    }

    @Query("SELECT i.* FROM gallery_translation_items i JOIN gallery_translation_tasks t ON t.id = i.taskId " +
        "WHERE i.status = 'SUCCEEDED' AND i.id > :afterId AND t.status IN ('SUCCEEDED','PARTIAL','FAILED') " +
        "ORDER BY i.id LIMIT 32")
    suspend fun legacyCompletedResults(afterId: String): List<GalleryTranslationItemEntity>

    @Query("UPDATE gallery_translation_items SET status = 'FAILED', errorMessage = :message, " +
        "updatedAtMs = MAX(updatedAtMs + 1, :now) WHERE id = :itemId AND status = 'SUCCEEDED' AND updatedAtMs = :expectedVersion " +
        "AND EXISTS (SELECT 1 FROM gallery_translation_tasks t WHERE t.id = gallery_translation_items.taskId " +
        "AND t.status IN ('SUCCEEDED','PARTIAL','FAILED'))")
    suspend fun reclassifyIncompleteResult(itemId: String, expectedVersion: Long, message: String, now: Long): Int

    @Query("UPDATE gallery_translation_tasks SET status = :status, totalCount = :total, completedCount = :completed, " +
        "successCount = :succeeded, failedCount = :failed, lastError = :message WHERE id = :taskId " +
        "AND status IN ('SUCCEEDED','PARTIAL','FAILED')")
    suspend fun repairTerminalSummary(taskId: String, status: GalleryTaskStatus, total: Int,
        completed: Int, succeeded: Int, failed: Int, message: String)

    /** Repair only terminal metadata; retained content, finish time and canceled tasks stay intact. */
    @Transaction
    suspend fun repairIncompleteResult(item: GalleryTranslationItemEntity, message: String, now: Long): Boolean {
        if (reclassifyIncompleteResult(item.id, item.updatedAtMs, message, now) != 1) return false
        val row = progress(item.taskId)
        val summary = GalleryTaskProgress(row.total, row.succeeded, row.failed, row.canceled, row.partial)
        repairTerminalSummary(item.taskId, GalleryTranslationWorkPolicy.terminalStatus(summary, false),
            summary.total, summary.completed, summary.succeeded, summary.failed, message)
        return true
    }

    @Query("SELECT COUNT(*) FROM gallery_translation_items WHERE sourceUri = :sourceUri")
    suspend fun countSourceUriReferences(sourceUri: String): Int

    @Query("DELETE FROM gallery_translation_tasks WHERE id = :taskId")
    suspend fun deleteTask(taskId: String)
}

class GalleryTranslationTypeConverters {
    @TypeConverter
    fun fromTaskStatus(value: GalleryTaskStatus): String = value.name

    @TypeConverter
    fun toTaskStatus(value: String): GalleryTaskStatus =
        GalleryTaskStatus.entries.firstOrNull { it.name == value } ?: GalleryTaskStatus.FAILED

    @TypeConverter
    fun fromItemStatus(value: GalleryItemStatus): String = value.name

    @TypeConverter
    fun toItemStatus(value: String): GalleryItemStatus =
        GalleryItemStatus.entries.firstOrNull { it.name == value } ?: GalleryItemStatus.FAILED
}

@Database(
    entities = [GalleryTranslationTaskEntity::class, GalleryTranslationItemEntity::class],
    version = 1,
    exportSchema = false,
)
@TypeConverters(GalleryTranslationTypeConverters::class)
abstract class GalleryTranslationDatabase : RoomDatabase() {
    abstract fun galleryTranslationDao(): GalleryTranslationDao
}
