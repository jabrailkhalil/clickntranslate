package dev.clickn.translate.update

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

internal const val RELEASE_REPOSITORY = "jabrailkhalil/clickntranslate"
internal const val RELEASES_PAGE = "https://github.com/$RELEASE_REPOSITORY/releases"

@Serializable
internal data class GitHubRelease(
    @SerialName("tag_name") val tag: String,
    val draft: Boolean = false,
    val prerelease: Boolean = false,
    val body: String? = null,
    val assets: List<GitHubAsset> = emptyList(),
)

@Serializable
internal data class GitHubAsset(
    val name: String,
    @SerialName("browser_download_url") val url: String,
    val size: Long = 0,
    val digest: String? = null,
    val state: String = "",
    val label: String? = null,
)

@Serializable
data class ReleaseApk(
    val tag: String,
    val name: String,
    val bytes: Long,
    val sha256: String,
    val advertisedCode: Long? = null,
) {
    val version get() = tag.removePrefix("v")
    val url get() = "https://github.com/$RELEASE_REPOSITORY/releases/download/$tag/$name"
    fun isValid() = ReleasePolicy.version(tag) != null && ReleasePolicy.abi(name, version) != null &&
        bytes in 1..Int.MAX_VALUE.toLong() && sha256.matches(Regex("[a-f0-9]{64}")) &&
        (advertisedCode == null || advertisedCode in 1..Int.MAX_VALUE.toLong())
}

data class UpdateInfo(
    val currentVersion: String,
    val latestVersion: String,
    val apk: ReleaseApk?,
    val changelog: String? = null,
    val noCompatiblePackage: Boolean = false,
) {
    val hasUpdate get() = apk != null
    val compareBuild get() = apk != null && apk.version == currentVersion && apk.advertisedCode == null
}

internal object ReleasePolicy {
    private val stable = Regex("""v?(0|[1-9]\d{0,8})\.(0|[1-9]\d{0,8})\.(0|[1-9]\d{0,8})""")
    private val codeLabel = Regex("""\bversionCode=(\d{1,10})\b""", RegexOption.IGNORE_CASE)
    fun version(tag: String): List<Int>? = stable.matchEntire(tag)?.groupValues?.drop(1)?.map { it.toInt() }
    fun compare(left: List<Int>, right: List<Int>) =
        left.indices.asSequence().map { left[it].compareTo(right[it]) }.firstOrNull { it != 0 } ?: 0

    fun abi(name: String, version: String): String? {
        val prefix = "ClicknTranslate-$version-"
        if (!name.startsWith(prefix) || !name.endsWith(".apk")) return null
        return when (name.removePrefix(prefix).removeSuffix(".apk")) {
            "arm64", "arm64-v8a" -> "arm64-v8a"
            "armv7", "armeabi-v7a" -> "armeabi-v7a"
            "x64", "x86_64" -> "x86_64"
            "x86" -> "x86"
            "universal" -> "universal"
            else -> null
        }
    }

    fun select(release: GitHubRelease, supported: List<String>, current: String, currentCode: Long): ReleaseApk? {
        val candidate = version(release.tag) ?: return null
        val installed = version(current) ?: return null
        val order = compare(candidate, installed)
        if (release.draft || release.prerelease || order < 0) return null
        val byRank = release.assets.mapNotNull { entry ->
            if (entry.state != "uploaded" || entry.digest?.startsWith("sha256:") != true) return@mapNotNull null
            val code = entry.label?.let { codeLabel.find(it)?.groupValues?.get(1)?.toLongOrNull() }
            if (code != null && code <= currentCode) return@mapNotNull null
            val apk = ReleaseApk(release.tag, entry.name, entry.size, entry.digest.substringAfter(':').lowercase(), code)
            if (!apk.isValid() || entry.url != apk.url) return@mapNotNull null
            val abi = abi(entry.name, apk.version)
            val rank = if (abi == "universal") supported.size else supported.indexOf(abi)
            if (rank < 0) null else rank to apk
        }
        val bestRank = byRank.minOfOrNull { it.first } ?: return null
        return byRank.filter { it.first == bestRank }.singleOrNull()?.second
    }
}
