package dev.clickn.translate.update

import android.app.NotificationChannel
import android.app.NotificationManager
import android.content.Context
import android.content.Intent
import android.content.pm.PackageInfo
import android.content.pm.PackageManager
import android.content.pm.ServiceInfo
import android.os.Build
import android.os.SystemClock
import androidx.core.app.NotificationCompat
import androidx.core.content.FileProvider
import androidx.core.content.pm.PackageInfoCompat
import androidx.hilt.work.HiltWorker
import androidx.work.ForegroundInfo
import androidx.work.WorkManager
import androidx.work.Worker
import androidx.work.WorkerParameters
import androidx.work.workDataOf
import dagger.assisted.Assisted
import dagger.assisted.AssistedInject
import dev.clickn.translate.R
import kotlinx.serialization.json.Json
import okhttp3.Call
import okhttp3.OkHttpClient
import okhttp3.Request
import java.io.File
import java.io.IOException
import java.io.InputStream
import java.io.OutputStream
import java.nio.file.Files
import java.nio.file.StandardCopyOption
import java.security.MessageDigest
import java.util.zip.ZipFile

internal class InvalidApk : IOException("Invalid application update")
internal class AlreadyInstalled : IOException("Installed build is current")

internal fun copyVerified(input: InputStream, output: OutputStream?, apk: ReleaseApk, progress: (Long) -> Unit) {
    val hash = MessageDigest.getInstance("SHA-256")
    val buffer = ByteArray(64 * 1024)
    var total = 0L
    while (true) {
        val count = input.read(buffer)
        if (count < 0) break
        total += count
        if (total > apk.bytes) throw InvalidApk()
        hash.update(buffer, 0, count)
        output?.write(buffer, 0, count)
        progress(total)
    }
    if (total != apk.bytes || hash.digest().hex() != apk.sha256) throw InvalidApk()
}

internal fun ByteArray.hex() = joinToString("") { "%02x".format(it) }

internal fun verifiedApkFile(context: Context, apk: ReleaseApk) =
    File(context.cacheDir, "app-updates/ready/${apk.sha256}.apk")

internal fun verifiedInstallerIntent(context: Context, apk: ReleaseApk): Intent {
    val file = verifiedApkFile(context, apk)
    if (!file.isFile) throw InvalidApk()
    file.inputStream().buffered().use { copyVerified(it, null, apk) {} }
    verifyArchive(context, file, apk)
    val uri = FileProvider.getUriForFile(context, "${context.packageName}.logfileprovider", file)
    return Intent(Intent.ACTION_VIEW).setDataAndType(uri, "application/vnd.android.package-archive")
        .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
}

internal data class ApkIdentity(val packageName: String, val version: String?, val code: Long, val signers: Set<String>)

internal fun validateIdentity(installed: ApkIdentity, candidate: ApkIdentity, apk: ReleaseApk) {
    if (candidate.packageName != installed.packageName || candidate.version != apk.version ||
        (apk.advertisedCode != null && candidate.code != apk.advertisedCode) ||
        candidate.signers.isEmpty() || candidate.signers != installed.signers) throw InvalidApk()
    if (candidate.code <= installed.code) {
        if (candidate.version == installed.version) throw AlreadyInstalled()
        throw InvalidApk()
    }
}

@Suppress("DEPRECATION")
internal fun verifyArchive(context: Context, file: File, apk: ReleaseApk) {
    if (!apk.isValid() || file.length() != apk.bytes) throw InvalidApk()
    val pm = context.packageManager
    val flags = if (Build.VERSION.SDK_INT >= 28) PackageManager.GET_SIGNING_CERTIFICATES else PackageManager.GET_SIGNATURES
    val archive = pm.getPackageArchiveInfo(file.absolutePath, flags) ?: throw InvalidApk()
    val installed = pm.getPackageInfo(context.packageName, flags)
    fun identity(info: PackageInfo): ApkIdentity {
        val certificates = if (Build.VERSION.SDK_INT >= 28) info.signingInfo?.apkContentsSigners else info.signatures
        val signers = certificates.orEmpty().map { MessageDigest.getInstance("SHA-256").digest(it.toByteArray()).hex() }.toSet()
        return ApkIdentity(info.packageName, info.versionName, PackageInfoCompat.getLongVersionCode(info), signers)
    }
    if (archive.applicationInfo?.let { it.minSdkVersion > Build.VERSION.SDK_INT } != false) throw InvalidApk()
    val nativeAbis = ZipFile(file).use { zip ->
        zip.entries().asSequence().map { it.name }
            .filter { it.startsWith("lib/") && it.endsWith(".so") }
            .map { it.substringAfter("lib/").substringBefore('/') }.toSet()
    }
    val assetAbi = ReleasePolicy.abi(apk.name, apk.version)
    if (nativeAbis.isNotEmpty() && (nativeAbis.none { it in Build.SUPPORTED_ABIS } ||
        (assetAbi != "universal" && assetAbi !in nativeAbis))) throw InvalidApk()
    validateIdentity(identity(installed), identity(archive), apk)
}

@HiltWorker
class ApkUpdateWorker @AssistedInject constructor(
    @Assisted context: Context, @Assisted parameters: WorkerParameters, private val http: OkHttpClient, private val json: Json,
) : Worker(context, parameters) {
    @Volatile private var call: Call? = null

    override fun doWork(): Result {
        val apk = runCatching { json.decodeFromString<ReleaseApk>(inputData.getString(APK) ?: "") }
            .getOrNull()?.takeIf(ReleaseApk::isValid) ?: return Result.failure()
        val ready = verifiedApkFile(applicationContext, apk)
        val stage = File(applicationContext.cacheDir, "app-updates/$id.pending.apk")
        try {
            if (!ready.parentFile!!.isDirectory && !ready.parentFile!!.mkdirs()) throw IOException()
            ready.parentFile!!.listFiles()?.filter { it.name != ready.name }?.forEach(File::delete)
            // A killed process may leave a partial file before WorkManager can invoke finally.
            stage.parentFile?.listFiles()?.filter { it != stage && it.isFile && it.name.endsWith(".pending.apk") }?.forEach(File::delete)
            setForegroundAsync(notification(apk, 0)).get()
            val client = http.newBuilder().followSslRedirects(false).addNetworkInterceptor { chain ->
                val url = chain.request().url
                if (!url.isHttps || url.port != 443 || url.host !in RELEASE_HOSTS) throw InvalidApk()
                chain.proceed(chain.request())
            }.build()
            val request = client.newCall(Request.Builder().url(apk.url).build())
            call = request
            if (isStopped) request.cancel()
            request.execute().use { response ->
                val body = response.body ?: throw IOException()
                if (!response.isSuccessful) throw IOException("HTTP ${response.code}")
                val length = body.contentLength()
                if (length >= 0 && length != apk.bytes) throw InvalidApk()
                var lastPercent = -1
                var lastUpdate = 0L
                stage.outputStream().use { out ->
                    copyVerified(body.byteStream(), out, apk) { bytes ->
                        if (isStopped) throw IOException()
                        val percent = (bytes * 100 / apk.bytes).toInt()
                        val now = SystemClock.elapsedRealtime()
                        if (percent != lastPercent && (percent == 100 || now - lastUpdate >= 600)) {
                            setProgressAsync(workDataOf(PROGRESS to percent))
                            setForegroundAsync(notification(apk, percent))
                            lastPercent = percent
                            lastUpdate = now
                        }
                    }
                }
            }
            verifyArchive(applicationContext, stage, apk)
            if (isStopped) return Result.failure()
            Files.move(stage.toPath(), ready.toPath(), StandardCopyOption.ATOMIC_MOVE, StandardCopyOption.REPLACE_EXISTING)
            return Result.success()
        } catch (_: AlreadyInstalled) {
            applicationContext.getSharedPreferences("update_checker", Context.MODE_PRIVATE).edit()
                .putString("checked_archive", "${dev.clickn.translate.BuildConfig.VERSION_CODE}:${apk.sha256}").apply()
            return Result.success(workDataOf(CURRENT to true))
        } catch (error: Exception) {
            return Result.failure(workDataOf(INVALID to (error is InvalidApk)))
        } finally {
            call = null
            stage.delete()
        }
    }

    override fun onStopped() {
        call?.cancel()
        super.onStopped()
    }

    private fun notification(apk: ReleaseApk, percent: Int): ForegroundInfo {
        val context = applicationContext
        context.getSystemService(NotificationManager::class.java).createNotificationChannel(
            NotificationChannel(CHANNEL, context.getString(R.string.update_notification_channel), NotificationManager.IMPORTANCE_LOW))
        val notification = NotificationCompat.Builder(context, CHANNEL)
            .setSmallIcon(android.R.drawable.stat_sys_download)
            .setContentTitle("ClicknTranslate ${apk.version}")
            .setContentText(context.getString(R.string.update_download_progress, percent))
            .setProgress(100, percent, false).setOngoing(true).setOnlyAlertOnce(true)
            .addAction(android.R.drawable.ic_menu_close_clear_cancel, context.getString(R.string.model_download_cancel),
                WorkManager.getInstance(context).createCancelPendingIntent(id)).build()
        return ForegroundInfo(243183, notification, ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC)
    }

    companion object {
        internal const val APK = "releaseApk"
        internal const val PROGRESS = "percent"
        internal const val INVALID = "invalidApk"
        internal const val CURRENT = "current"
        internal const val WORK_NAME = "clickntranslate-app-update"
        private const val CHANNEL = "app_updates"
        private val RELEASE_HOSTS = setOf("github.com", "release-assets.githubusercontent.com", "objects.githubusercontent.com")
    }
}
