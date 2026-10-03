// Modified for Click'n'Translate on October 3, 2026.
package dev.clickn.translate.download

import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.lifecycleScope
import androidx.work.WorkInfo
import androidx.work.WorkManager
import dev.clickn.translate.data.AppLocalePrefs
import dev.clickn.translate.data.ThemeModePrefs
import dev.clickn.translate.ui.ModelDownloadCancelDialog
import dev.clickn.translate.ui.theme.ClickTranslateTheme
import java.util.UUID
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.launch

/** A notification-only dialog host; never opens or clears the main application's task. */
class ModelDownloadCancelActivity : ComponentActivity() {
    private var showConfirmation by mutableStateOf(false)
    private var handled = false

    override fun attachBaseContext(newBase: Context) {
        super.attachBaseContext(AppLocalePrefs.wrap(newBase))
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val workId = runCatching { UUID.fromString(intent.data?.lastPathSegment) }.getOrNull()
        if (workId == null) {
            finishRequest()
            return
        }
        val workManager = WorkManager.getInstance(applicationContext)
        val work = workManager.getWorkInfoByIdFlow(workId)
        lifecycleScope.launch {
            work.collect { info ->
                if (!canCancelModelDownload(info)) finishRequest()
                else if (!handled) showConfirmation = true
            }
        }
        setContent {
            ClickTranslateTheme(themeMode = ThemeModePrefs.read(this)) {
                if (showConfirmation) {
                    ModelDownloadCancelDialog(
                        onDismiss = ::finishRequest,
                        onConfirm = {
                            if (!handled) {
                                handled = true
                                showConfirmation = false
                                lifecycleScope.launch {
                                    // Re-read on confirmation: a stale notification cannot cancel other work.
                                    if (canCancelModelDownload(work.first())) workManager.cancelWorkById(workId)
                                    finishRequest()
                                }
                            }
                        },
                    )
                }
            }
        }
    }

    private fun finishRequest() {
        handled = true
        showConfirmation = false
        if (isTaskRoot) finishAndRemoveTask() else finish()
    }

    companion object {
        fun pendingIntent(context: Context, workId: UUID): PendingIntent {
            val intent = Intent(context, ModelDownloadCancelActivity::class.java).apply {
                // Intent extras alone do not distinguish PendingIntents for concurrent models.
                data = Uri.parse("clicktranslate-model-download://cancel/$workId")
                addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_NO_ANIMATION)
            }
            return PendingIntent.getActivity(
                context, 0, intent, PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
            )
        }
    }
}

internal fun canCancelModelDownload(info: WorkInfo?): Boolean =
    info != null && !info.state.isFinished && ModelDownloadWorkPolicy.WORK_TAG in info.tags
