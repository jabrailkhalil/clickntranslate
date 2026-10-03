// Modified for Click'n'Translate on October 3, 2026.
package dev.clickn.translate.service

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.os.Build
import androidx.core.app.NotificationCompat
import dev.clickn.translate.R
import dev.clickn.translate.ui.MainActivity

internal object CaptureNotification {
    const val CHANNEL_ID = "clickntranslate_capture"
    const val NOTIF_ID = 0x0C42

    fun ensureChannel(context: Context) {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return
        val nm = context.getSystemService(NotificationManager::class.java) ?: return
        if (nm.getNotificationChannel(CHANNEL_ID) != null) return
        val channel = NotificationChannel(
            CHANNEL_ID,
            context.getString(R.string.notif_channel_name),
            NotificationManager.IMPORTANCE_LOW
        ).apply {
            description = context.getString(R.string.notif_channel_desc)
            setShowBadge(false)
        }
        nm.createNotificationChannel(channel)
    }

    fun build(context: Context): Notification {
        ensureChannel(context)
        val openMain = PendingIntent.getActivity(
            context, 0,
            Intent(context, MainActivity::class.java),
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )
        fun actionIntent(action: String, request: Int) = PendingIntent.getService(context, request,
            Intent(context, CaptureService::class.java).setAction(action),
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
        return NotificationCompat.Builder(context, CHANNEL_ID)
            .setSmallIcon(android.R.drawable.ic_menu_camera)
            .setContentTitle(context.getString(R.string.notif_title))
            .setContentText(context.getString(R.string.notif_text))
            .setOngoing(true)
            .setSilent(true)
            .setContentIntent(openMain)
            .addAction(android.R.drawable.ic_menu_view, context.getString(R.string.floating_show_button),
                actionIntent(CaptureService.ACTION_SHOW_BUTTON, 21))
            .addAction(android.R.drawable.ic_menu_close_clear_cancel, context.getString(R.string.btn_stop),
                actionIntent(CaptureService.ACTION_STOP, 22))
            .setPriority(NotificationCompat.PRIORITY_LOW)
            .build()
    }
}
