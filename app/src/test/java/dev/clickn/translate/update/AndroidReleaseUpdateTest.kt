package dev.clickn.translate.update

import java.io.ByteArrayInputStream
import java.io.ByteArrayOutputStream
import java.security.MessageDigest
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.serialization.json.Json
import org.junit.Assert.*
import org.junit.Test

class AndroidReleaseUpdateTest {
    private val repo = "https://github.com/jabrailkhalil/clickntranslate/releases/download"
    private val digest = "sha256:3a8d5d6ce41b368642f0b03bd1745e9764908aa9a1229660bd67b1557b114d63"
    private val arm = listOf("arm64-v8a", "armeabi-v7a")
    private fun asset(tag: String, abi: String, label: String? = null): GitHubAsset {
        val name = "ClicknTranslate-${tag.removePrefix("v")}-$abi.apk"
        return GitHubAsset(name, "$repo/$tag/$name", 60_487_261, digest, "uploaded", label)
    }
    private fun release(tag: String, vararg assets: GitHubAsset) = GitHubRelease(tag, assets = assets.toList())
    private fun select(r: GitHubRelease, current: String = "1.8.1", code: Long = 6, abi: List<String> = arm) =
        ReleasePolicy.select(r, abi, current, code)

    @Test fun onlyOneTapCanClaimTheApkFromTheVisibleReleaseOffer() {
        val apk = select(release("v1.8.3", asset("v1.8.3", "arm64")))!!
        val offer = UpdateViewModel.State.Loaded(UpdateInfo("1.8.1", apk.version, apk))
        val visible = MutableStateFlow<UpdateViewModel.State>(offer)
        assertFalse(visible.claimUpdateDownload(apk.copy(sha256 = "f".repeat(64))))
        assertSame(offer, visible.value)
        assertTrue(visible.claimUpdateDownload(apk))
        assertEquals(UpdateViewModel.State.Downloading(apk, 0), visible.value)
        assertFalse("Repeated tap before the work id is registered", visible.claimUpdateDownload(apk))
        for (state in listOf(UpdateViewModel.State.Checking, UpdateViewModel.State.Idle, UpdateViewModel.State.Ready(apk))) {
            visible.value = state
            assertFalse("Obsolete button callback in $state", visible.claimUpdateDownload(apk))
            assertSame(state, visible.value)
        }
    }

    @Test fun publishedArm64AssetRoundtripsThroughJsonAndSelectsExactBinary() {
        val json = Json { ignoreUnknownKeys = true }
        val r = json.decodeFromString<GitHubRelease>("""{
           "tag_name":"v1.8.2","draft":false,"prerelease":false,"irrelevant":true,"assets":[
           {"name":"ClicknTranslate-1.8.2-arm64.apk","size":60487261,"state":"uploaded",
           "digest":"$digest","browser_download_url":"$repo/v1.8.2/ClicknTranslate-1.8.2-arm64.apk"}]}""")
        val apk = select(r)!!
        assertEquals("1.8.2", apk.version)
        assertEquals(r.assets.single().url, apk.url)
        assertEquals(digest.substringAfter(':'), apk.sha256)
        assertNull(select(r, abi = listOf("x86_64")))
    }

    @Test fun prefersNativeAbiThenUniversalAndRejectsAmbiguousBuilds() {
        val tag = "v1.8.2"
        val armApk = asset(tag, "arm64")
        val universal = asset(tag, "universal")
        val r = release(tag, universal, asset(tag, "armv7"), armApk)
        assertEquals(armApk.name, select(r)!!.name)
        assertEquals(universal.name, select(r, abi = listOf("x86_64"))!!.name)
        assertNull(select(release(tag, armApk, asset(tag, "arm64-v8a"))))
        for (name in listOf("app-release.apk", "ClicknTranslate-1.8.2.apk", "ClicknTranslate-1.8.2-arm64-debug.apk"))
            assertNull(ReleasePolicy.abi(name, "1.8.2"))
    }

    @Test fun ignoresDraftPrereleaseUnreadyWrongHashLinkOrLength() {
        val good = asset("v1.8.3", "arm64")
        for (bad in listOf(good.copy(size = 0), good.copy(size = Long.MAX_VALUE), good.copy(state = "starter"),
            good.copy(digest = null), good.copy(digest = "sha256:abc"), good.copy(url = "https://example.com/file.apk"),
            good.copy(url = good.url.replace("jabrailkhalil", "someone")), good.copy(name = "../${good.name}")))
            assertNull(select(release("v1.8.3", bad)))
        val release = release("v1.8.3", good)
        assertNull(select(release.copy(draft = true)))
        assertNull(select(release.copy(prerelease = true)))
        assertNull(select(release.copy(tag = "v1.8.3-rc1")))
        assertNull(select(release, current = "1.10.0"))
        assertNotNull(select(release("v1.10.0", asset("v1.10.0","arm64")), current = "1.9.9"))
    }

    @Test fun sameVersionUsesCodeWhenPresentAndManualBuildComparisonOtherwise() {
        val newer = release("v1.8.3", asset("v1.8.3", "arm64", "Android versionCode=46"))
        val apk = select(newer, "1.8.3", 45)!!
        assertEquals(46L, apk.advertisedCode)
        assertNull(select(newer, "1.8.3", 46))
        assertNull(select(newer, "1.8.2", 47))
        val unlabelled = release("v1.8.3", asset("v1.8.3","arm64"))
        val info = resolveAndroidUpdate(unlabelled, "1.8.3", 45, arm) { error("unexpected page") }
        assertTrue(info.compareBuild)
        assertFalse(UpdateInfo("1.8.2","1.8.3",apk).compareBuild)
    }

    @Test fun handlesDesktopOnlyLatestAndActuallyWalksReleasePages() {
        val tag = "v2.0.0"
        val desktop = release(tag)
        val compatible = release("v1.8.3", asset("v1.8.3", "arm64"))
        val pages = mutableListOf<Int>()
        val result = resolveAndroidUpdate(desktop,"1.8.2",7,arm) { n ->
            pages.add(n)
            when (n) {
                1 -> (1..PAGE_SIZE).map { release("v1.9.$it") }
                2 -> listOf(compatible, release("v1.8.2"))
                else -> error("extra request")
            }
        }
        assertEquals(listOf(1, 2), pages)
        assertEquals("1.8.3", result.latestVersion)
        assertTrue(result.hasUpdate)
        val none = resolveAndroidUpdate(desktop, "1.8.2", 7, listOf("x86_64")) { listOf(compatible) }
        assertFalse(none.hasUpdate)
        assertTrue(none.noCompatiblePackage)
        val newerLocal = resolveAndroidUpdate(compatible, "1.10.0", 100, arm) { error("unexpected page") }
        assertFalse(newerLocal.hasUpdate)
        assertFalse(newerLocal.noCompatiblePackage)
    }

    @Test fun verifiesStreamingBytesAndRejectsTruncationExtraOrCorruptBytes() {
        val content = ByteArray(80000) { it.toByte() }
        val apk = select(release("v1.8.3", asset("v1.8.3", "arm64")))!!.copy(
            bytes = content.size.toLong(), sha256 = MessageDigest.getInstance("SHA-256").digest(content).hex())
        val out = ByteArrayOutputStream()
        val progress = mutableListOf<Long>()
        copyVerified(ByteArrayInputStream(content), out, apk, progress::add)
        assertArrayEquals(content, out.toByteArray())
        assertEquals(content.size.toLong(), progress.last())
        copyVerified(content.inputStream(), null, apk) {}
        for (bad in listOf(content.copyOf(79999), content.copyOf(80001), content.clone().also { it[37]++ }))
            assertThrows(InvalidApk::class.java) { copyVerified(bad.inputStream(), ByteArrayOutputStream(), apk) {} }
        assertThrows(java.util.concurrent.CancellationException::class.java) {
            copyVerified(content.inputStream(), null, apk) { throw java.util.concurrent.CancellationException() }
        }
    }

    @Test fun searchesPastBackportsWithoutUndoingAnExplicitLatestRollback() {
        val latest = release("v9.3.0")
        fun android(tag: String) = release(tag, asset(tag, "arm64"))
        val result = resolveAndroidUpdate(latest, "1.8.2", 7, arm) { page ->
            when (page) {
                1 -> listOf(android("v2.0.0"), android("v1.7.0"), android("v10.0.0")) +
                    (4..PAGE_SIZE).map { release("v1.6.$it") }
                2 -> listOf(android("v9.2.0"))
                else -> error("extra page")
            }
        }
        assertEquals("9.2.0", result.latestVersion)
    }

    @Test fun mobileNotesOmitTheDownloadTableBeforeTruncatingButKeepReleaseText() {
        val start = "<!-- clickntranslate-downloads:start -->"
        val end = "<!-- clickntranslate-downloads:end -->"
        val downloads = start + "badge-url".repeat(3500) + end
        val r = release("v1.8.3", asset("v1.8.3", "arm64")).copy(body = "Before\n$downloads\nAfter")
        val result = resolveAndroidUpdate(r, "1.8.2", 7, arm) { error("unnecessary request") }
        assertEquals("Before\n\nAfter", result.changelog)
        assertNull(mobileReleaseNotes(downloads))
        assertNull(mobileReleaseNotes(null))
        assertEquals("Before", mobileReleaseNotes("Before\n$start unfinished table"))
        assertEquals("After", mobileReleaseNotes("$end\nAfter"))
        assertEquals("normal <!-- other comment --> prose", mobileReleaseNotes("normal <!-- other comment --> prose"))
        assertEquals(16_000, mobileReleaseNotes(downloads + "x".repeat(16_400))?.length)
    }

    @Test fun confirmsPackageSignedByInstalledSignerAndMoreRecentActualVersionCode() {
        val apk = select(release("v1.8.3", asset("v1.8.3","arm64", "Android versionCode=46")))!!
        val installed = ApkIdentity("dev.clickn.translate", "1.8.2", 7, setOf("release"))
        val expected = installed.copy(version = "1.8.3", code = 46)
        validateIdentity(installed, expected, apk)
        validateIdentity(installed.copy(version = "1.8.3", code = 45), expected, apk.copy(advertisedCode = null))
        for (bad in listOf(expected.copy(packageName = "dev.clickn.translate.debug"), expected.copy(signers = emptySet()),
            expected.copy(signers = setOf("other")), expected.copy(version="1.8.4"), expected.copy(code=45)))
            assertThrows(InvalidApk::class.java) { validateIdentity(installed, bad, apk) }
        assertThrows(InvalidApk::class.java) { validateIdentity(installed.copy(code = 47), expected, apk) }
        assertThrows(AlreadyInstalled::class.java) { validateIdentity(expected, expected, apk.copy(advertisedCode=null)) }
        assertThrows(AlreadyInstalled::class.java) { validateIdentity(expected.copy(code=47), expected, apk.copy(advertisedCode=null)) }
    }
}
