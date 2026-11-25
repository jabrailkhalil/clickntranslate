// Modified for Click'n'Translate on October 3, 2026.
package dev.clickn.translate.gallery

import android.content.Context
import androidx.work.BackoffPolicy
import androidx.work.Constraints
import androidx.work.ExistingWorkPolicy
import androidx.work.NetworkType
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.workDataOf
import dagger.hilt.android.qualifiers.ApplicationContext
import java.util.concurrent.TimeUnit
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class GalleryTranslationManager @Inject constructor(
    @ApplicationContext context: Context,
    private val repository: GalleryTranslationRepository,
) {
    private val workManager = WorkManager.getInstance(context)

    fun enqueue(task: GalleryPreparedTask) = enqueue(task, ExistingWorkPolicy.KEEP)

    private fun enqueue(
        task: GalleryPreparedTask,
        policy: ExistingWorkPolicy,
        retrySelection: GalleryRetrySelection? = null,
    ) {
        val constraints = Constraints.Builder().apply {
            if (
                GalleryTranslationWorkPolicy.requiresNetwork(
                    task.ocrEngine,
                    task.translatorEngine,
                )
            ) {
                setRequiredNetworkType(NetworkType.CONNECTED)
            }
        }.build()
        val request = OneTimeWorkRequestBuilder<GalleryTranslationWorker>()
            .setInputData(workDataOf(
                GalleryTranslationWorker.KEY_TASK_ID to task.id,
                GalleryTranslationWorker.KEY_RETRY_ITEM_IDS to retrySelection?.items.orEmpty().map { it.id }.toTypedArray(),
                GalleryTranslationWorker.KEY_RETRY_ITEM_VERSIONS to retrySelection?.items.orEmpty().map { it.version }.toLongArray(),
                GalleryTranslationWorker.KEY_RETRY_TASK_STATUS to retrySelection?.taskStatus?.name.orEmpty(),
                GalleryTranslationWorker.KEY_RETRY_TASK_FINISHED_AT to (retrySelection?.finishedAtMs ?: 0L),
            ))
            .setConstraints(constraints)
            .setBackoffCriteria(
                BackoffPolicy.EXPONENTIAL,
                10,
                TimeUnit.SECONDS,
            )
            .addTag(GalleryTranslationWorkPolicy.WORK_TAG)
            .addTag(task.id)
            .build()
        workManager.enqueueUniqueWork(
            GalleryTranslationWorkPolicy.uniqueWorkName(task.id),
            policy,
            request,
        )
    }

    suspend fun cancel(taskId: String) {
        repository.cancelTask(taskId)
        workManager.cancelUniqueWork(GalleryTranslationWorkPolicy.uniqueWorkName(taskId))
    }

    suspend fun retryFailed(taskId: String): Boolean {
        val retrySelection = repository.failedRetrySelection(taskId) ?: return false
        val task = repository.getTask(taskId) ?: return false
        enqueue(
            GalleryPreparedTask(
                id = task.id,
                sourceLang = task.sourceLang,
                targetLang = task.targetLang,
                ocrEngine = enumValueOrDefault(task.ocrEngine),
                translatorEngine = enumValueOrDefault(task.translatorEngine),
                imageCount = task.totalCount,
            ),
            // The preceding worker can still be returning after its Room result is visible.
            // KEEP would drop this explicit retry; append it without cancelling that owner.
            policy = ExistingWorkPolicy.APPEND_OR_REPLACE,
            retrySelection = retrySelection,
        )
        return true
    }

    suspend fun delete(taskId: String) {
        workManager.cancelUniqueWork(GalleryTranslationWorkPolicy.uniqueWorkName(taskId))
        repository.deleteTask(taskId)
    }
}

private inline fun <reified T : Enum<T>> enumValueOrDefault(value: String): T =
    enumValues<T>().firstOrNull { it.name == value } ?: enumValues<T>().first()
