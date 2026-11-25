package dev.clickn.translate.update

import android.os.Build
import android.content.Context
import dagger.hilt.android.qualifiers.ApplicationContext
import dev.clickn.translate.AppBrand
import dev.clickn.translate.BuildConfig
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.serialization.json.Json
import okhttp3.OkHttpClient
import okhttp3.Request
import java.io.IOException
import java.io.File
import java.security.MessageDigest
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class UpdateChecker @Inject constructor(
    private val http: OkHttpClient, private val json: Json, @ApplicationContext private val context: Context,
) {
    suspend fun checkLatest(): UpdateInfo = withContext(Dispatchers.IO) {
        val url = AppBrand.mobileReleaseApiUrl
        val latest = json.decodeFromString<GitHubRelease>(metadata(url))
        resolveAndroidUpdate(latest, BuildConfig.VERSION_NAME, BuildConfig.VERSION_CODE.toLong(),
            Build.SUPPORTED_ABIS.toList()) { page ->
            if (!url.endsWith("/releases/latest")) emptyList() else
                json.decodeFromString<List<GitHubRelease>>(metadata(url.removeSuffix("/latest") + "?per_page=$PAGE_SIZE&page=$page"))
        }
    }

    /** Called only during an explicit check of an unlabelled release with the same versionName. */
    suspend fun sameInstalledBuild(apk: ReleaseApk): Boolean = withContext(Dispatchers.IO) {
        val prefs = context.getSharedPreferences("update_checker", Context.MODE_PRIVATE)
        if (prefs.getString("checked_archive", null) == "${BuildConfig.VERSION_CODE}:${apk.sha256}") return@withContext true
        val base = File(context.applicationInfo.sourceDir)
        if (!base.isFile || base.length() != apk.bytes) return@withContext false
        val cacheKey = "${BuildConfig.VERSION_CODE}:${base.absolutePath}:${base.length()}:${base.lastModified()}"
        val installed = if (prefs.getString("digest_key", null) == cacheKey) prefs.getString("base_digest", null) else null
        val hash = installed ?: runCatching {
            val digest = MessageDigest.getInstance("SHA-256")
            base.inputStream().buffered().use { input ->
                val bytes = ByteArray(64 * 1024)
                while (true) {
                    val size = input.read(bytes)
                    if (size < 0) break
                    digest.update(bytes, 0, size)
                }
            }
            digest.digest().hex().also { prefs.edit().putString("digest_key", cacheKey).putString("base_digest", it).apply() }
        }.getOrNull()
        hash == apk.sha256
    }

    private fun metadata(url: String): String {
        val request = Request.Builder().url(url).header("Accept", "application/vnd.github+json")
            .header("User-Agent", "ClicknTranslate/" + BuildConfig.VERSION_NAME).build()
        return http.newCall(request).execute().use { response ->
            if (!response.isSuccessful) throw IOException("GitHub HTTP ${response.code}")
            val source = response.body?.source() ?: throw IOException("GitHub returned an empty response")
            if (source.request(4L * 1024 * 1024 + 1)) throw IOException("GitHub response exceeds 4 MiB")
            source.readUtf8()
        }
    }

    companion object { const val RELEASE_PAGE_URL = "$RELEASES_PAGE/latest" }
}

internal const val PAGE_SIZE = 20
private const val DOWNLOADS_START = "<!-- clickntranslate-downloads:start -->"
private const val DOWNLOADS_END = "<!-- clickntranslate-downloads:end -->"

internal fun mobileReleaseNotes(body: String?): String? {
    if (body.isNullOrBlank()) return null
    var offset = 0
    val notes = buildString {
        while (offset < body.length) {
            val start = body.indexOf(DOWNLOADS_START, offset)
            if (start < 0) {
                append(body.substring(offset))
                break
            }
            append(body, offset, start)
            val end = body.indexOf(DOWNLOADS_END, start + DOWNLOADS_START.length)
            if (end < 0) break
            offset = end + DOWNLOADS_END.length
        }
    }
    return notes.replace(DOWNLOADS_END, "").trim().take(16_000).ifBlank { null }
}

/** The latest desktop release can precede the most recent release that actually contains an Android APK. */
internal fun resolveAndroidUpdate(
    latest: GitHubRelease, current: String, code: Long, abis: List<String>, page: (Int) -> List<GitHubRelease>,
): UpdateInfo {
    val installed = requireNotNull(ReleasePolicy.version(current))
    val upperBound = ReleasePolicy.version(latest.tag)?.takeUnless { latest.draft || latest.prerelease }
    fun result(release: GitHubRelease): UpdateInfo? {
        val version = ReleasePolicy.version(release.tag) ?: return null
        if (upperBound != null && ReleasePolicy.compare(version, upperBound) > 0) return null
        val apk = ReleasePolicy.select(release, abis, current, code) ?: return null
        return UpdateInfo(current, apk.version, apk, mobileReleaseNotes(release.body))
    }
    result(latest)?.let { return it }
    fun order(release: GitHubRelease) = ReleasePolicy.version(release.tag)
        ?.takeUnless { release.draft || release.prerelease }?.let { ReleasePolicy.compare(it, installed) }
    val latestOrder = order(latest)
    if (latestOrder != null && latestOrder <= 0) return UpdateInfo(current, current, null)
    var index = 1
    var best: UpdateInfo? = null
    var newerRelease = (latestOrder ?: 0) > 0
    // Stop before issuing an unbounded series of GitHub requests on malformed/repeating pages.
    val seen = mutableSetOf<String>()
    while (true) {
        val releases = page(index++)
        val unseen = releases.filter { seen.add(it.tag) }
        // Release pages use publication order, so a recently published backport may precede a later Android version.
        for (candidate in unseen.mapNotNull(::result)) {
            val previous = best
            if (previous == null || ReleasePolicy.compare(ReleasePolicy.version(candidate.latestVersion)!!,
                    ReleasePolicy.version(previous.latestVersion)!!) > 0) best = candidate
        }
        newerRelease = newerRelease || unseen.any { (order(it) ?: 0) > 0 }
        if (releases.size < PAGE_SIZE || unseen.isEmpty()) break
    }
    return best ?: UpdateInfo(current, current, null, noCompatiblePackage = newerRelease)
}
