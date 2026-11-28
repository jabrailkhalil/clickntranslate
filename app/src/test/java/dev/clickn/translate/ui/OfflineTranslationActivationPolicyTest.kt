package dev.clickn.translate.ui

import dev.clickn.translate.data.Settings
import dev.clickn.translate.data.TranslationSelectionSnapshot
import dev.clickn.translate.data.TranslatorEngine
import java.io.IOException
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.async
import kotlinx.coroutines.cancel
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.launch
import kotlinx.coroutines.test.runCurrent
import kotlinx.coroutines.test.runTest
import org.junit.Assert.*
import org.junit.Test

/** Repository/DataStore CAS behavior is covered by SettingsSelectionRevisionIntegrationTest. */
class OfflineTranslationActivationPolicyTest {
    private val initial = Settings(translatorEngine = TranslatorEngine.GOOGLE, sourceLang = "en", targetLang = "ru")
    private val captured = TranslationSelectionSnapshot(initial, revision = 17)
    private val requested = initial.copy(translatorEngine = TranslatorEngine.GOOGLE_ML_KIT, targetLang = "fr")

    @Test fun installedPairActivatesWithoutSchedulingAnyNetworkWork() = runTest {
        var selected: Settings? = null
        OfflineTranslationActivationPolicy.downloadAndActivate(captured, requested,
            alreadyInstalled = { true }, download = { fail("An installed pair must work without connectivity") },
            activate = { snapshot, pair -> assertEquals(captured, snapshot); selected = pair })
        assertEquals(requested, selected)
    }

    @Test fun completedDownloadPassesTheOriginalSnapshotAndRequestedPairToAtomicActivation() = runTest {
        val download = CompletableDeferred<Unit>()
        val events = mutableListOf<String>()
        val operation = launch {
            OfflineTranslationActivationPolicy.downloadAndActivate(captured, requested, { false }, {
                download.await()
                events += "downloaded"
            }, { snapshot, pair ->
                assertSame("The click-time revision must not be refreshed after waiting.", captured, snapshot)
                assertSame(requested, pair)
                events += "activation"
            })
        }
        runCurrent()
        assertTrue(events.isEmpty())
        download.complete(Unit)
        operation.join()
        assertEquals(listOf("downloaded", "activation"), events)
    }

    @Test fun cancelledDownloadCannotActivateWhenItCompletesLater() = runTest {
        val download = CompletableDeferred<Unit>()
        var activations = 0
        val operation = launch {
            OfflineTranslationActivationPolicy.downloadAndActivate(captured, requested, { false }, {
                download.await()
            }, { _, _ -> activations++ })
        }
        runCurrent()
        operation.cancelAndJoin()
        download.complete(Unit)
        runCurrent()
        assertEquals(0, activations)
    }

    @Test fun failureReachesTheCallerWithoutAttemptingActivation() = runTest {
        val download = CompletableDeferred<Unit>()
        var activations = 0
        val operation = async {
            runCatching {
                OfflineTranslationActivationPolicy.downloadAndActivate(captured, requested, { false }, {
                    download.await()
                    throw IOException("Owned model download failure")
                }, { _, _ -> activations++ })
            }
        }
        runCurrent()
        download.complete(Unit)
        assertTrue(operation.await().exceptionOrNull() is IOException)
        assertEquals(0, activations)
    }

    @Test fun cancellationAtTheDownloadCompletionBoundaryStillPreventsActivation() = runTest {
        var activations = 0
        val operation = launch {
            OfflineTranslationActivationPolicy.downloadAndActivate(captured, requested, { false }, {
                currentCoroutineContext().cancel()
            }, { _, _ -> activations++ })
        }
        operation.join()
        assertTrue(operation.isCancelled)
        assertEquals(0, activations)
    }
}
