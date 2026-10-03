// Modified for Click'n'Translate on October 3, 2026.
package dev.clickn.translate.ui

import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.SideEffect
import androidx.compose.ui.platform.LocalConfiguration
import androidx.compose.ui.graphics.luminance
import androidx.core.view.WindowCompat
import dev.clickn.translate.ui.theme.komiPaperGrid
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.State
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveableStateHolder
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.core.content.IntentCompat
import dev.clickn.translate.gallery.GalleryTranslationWorkPolicy
import dev.clickn.translate.data.AppLocalePrefs
import dev.clickn.translate.data.ThemeModePrefs
import dev.clickn.translate.onboarding.OnboardingPrefs
import dev.clickn.translate.onboarding.OnboardingScreen
import dev.clickn.translate.onboarding.FloatingTourRerunPolicy
import dev.clickn.translate.overlay.FloatingMenuTourPrefs
import dev.clickn.translate.service.CaptureService
import dev.clickn.translate.service.CaptureServiceState
import dev.clickn.translate.ui.theme.ClickTranslateTheme
import dev.clickn.translate.ui.theme.LocalThemeMode
import dev.clickn.translate.ui.theme.ThemeModeController
import dev.clickn.translate.ui.theme.ThemeAccentPrefs
import dev.clickn.translate.ui.theme.ThemeAccentController
import dev.clickn.translate.ui.theme.LocalThemeAccent
import dagger.hilt.android.AndroidEntryPoint

@AndroidEntryPoint
class MainActivity : ComponentActivity() {
    private val routeRequest = mutableStateOf<String?>(null)
    private val galleryShareRequest = mutableStateOf(GalleryShareRequest())
    private var galleryShareRequestId = 0L

    companion object {
        const val EXTRA_START_ROUTE: String = "dev.clickn.translate.extra.START_ROUTE"
        const val ROUTE_SETTINGS: String = "Settings"
    }

    /**
     * 在 Activity 的 baseContext 被设置之前，用持久化的 locale 包装它。
     * 重写在 [onCreate] 之前就被调用，确保整个 Activity 生命周期内 Resources 用对的 locale。
     */
    override fun attachBaseContext(newBase: Context) {
        super.attachBaseContext(AppLocalePrefs.wrap(newBase))
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        acceptLaunchIntent(intent)
        enableEdgeToEdge()
        setContent {
            val activityContext = this@MainActivity
            var localeTag by remember { mutableStateOf(AppLocalePrefs.read(activityContext)) }
            DisposableEffect(activityContext) {
                val stop = AppLocalePrefs.observe(activityContext) {
                    val chosen = AppLocalePrefs.read(activityContext)
                    if (chosen != localeTag) {
                        localeTag = chosen
                        activityContext.recreate()
                    }
                }
                onDispose { stop() }
            }
            val systemConfiguration = LocalConfiguration.current
            val context = remember(localeTag, systemConfiguration) { AppLocalePrefs.uiContext(activityContext) }
            // 主题模式：从 prefs 初始化；切换后通过 CompositionLocal 透传到 ClickTranslateTheme，
            // 无需重建 Activity 即可瞬时生效。
            var themeMode by remember { mutableIntStateOf(ThemeModePrefs.read(context)) }
            val controller = ThemeModeController(
                mode = themeMode,
                setMode = { newMode ->
                    themeMode = newMode
                    ThemeModePrefs.write(context, newMode)
                }
            )
            var accent by remember { mutableStateOf(ThemeAccentPrefs.read(context)) }
            val accentController = ThemeAccentController(accent) { choice ->
                accent = choice
                ThemeAccentPrefs.write(context, choice)
            }
            CompositionLocalProvider(LocalContext provides context, LocalConfiguration provides context.resources.configuration, LocalThemeMode provides controller, LocalThemeAccent provides accentController) {
                ClickTranslateTheme(themeMode = themeMode, accent = accent) {
                    val lightBars = MaterialTheme.colorScheme.background.luminance() > .5f
                    SideEffect {
                        WindowCompat.getInsetsController(window, window.decorView).apply {
                            isAppearanceLightStatusBars = lightBars
                            isAppearanceLightNavigationBars = lightBars
                        }
                    }
                    AppRoot(routeRequest, galleryShareRequest)
                }
            }
        }
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        acceptLaunchIntent(intent)
    }

    private fun acceptLaunchIntent(intent: Intent?) {
        val sharedUris = sharedGalleryImageUris(intent)
        if (sharedUris.isNotEmpty()) {
            galleryShareRequestId += 1
            galleryShareRequest.value = GalleryShareRequest(
                id = galleryShareRequestId,
                uris = sharedUris,
            )
            routeRequest.value = Route.GalleryConfirm.name
        } else {
            routeRequest.value = intent?.getStringExtra(EXTRA_START_ROUTE)
        }
    }
}

private data class GalleryShareRequest(
    val id: Long = 0,
    val uris: List<String> = emptyList(),
)

private fun sharedGalleryImageUris(intent: Intent?): List<String> {
    intent ?: return emptyList()
    val singleUri = IntentCompat.getParcelableExtra(
        intent,
        Intent.EXTRA_STREAM,
        Uri::class.java,
    )?.toString()
    val multipleUris = IntentCompat.getParcelableArrayListExtra(
        intent,
        Intent.EXTRA_STREAM,
        Uri::class.java,
    ).orEmpty().map(Uri::toString)
    return GalleryTranslationWorkPolicy.sharedImageSelection(
        action = intent.action,
        mimeType = intent.type,
        singleUri = singleUri,
        multipleUris = multipleUris,
    )
}

private enum class Route {
    Main,
    Onboarding,
    Settings,
    Glossary,
    DictionaryLibrary,
    Logs,
    GalleryConfirm,
    GalleryTasks,
    GalleryTaskDetail,
}

@Composable
private fun AppRoot(
    routeRequest: State<String?>,
    galleryShareRequest: State<GalleryShareRequest>,
) {
    val context = LocalContext.current
    var onboardingFirstRun by rememberSaveable {
        mutableStateOf(!OnboardingPrefs.isCompleted(context))
    }
    var onboardingOpenedFromHelp by rememberSaveable {
        mutableStateOf(false)
    }
    // 用 rememberSaveable：语言切换会触发系统 recreate Activity，route 须跨重建保留。
    var routeName by rememberSaveable {
        mutableStateOf(
            routeRequest.value ?: if (onboardingFirstRun) {
                Route.Onboarding.name
            } else {
                Route.Main.name
            }
        )
    }
    val settingsListState = rememberLazyListState()
    val screenState = rememberSaveableStateHolder()
    var settingsReturn by rememberSaveable { mutableStateOf(Route.Main.name) }
    var settingsSection by rememberSaveable { mutableStateOf<String?>(null) }
    var selectedGalleryUris by rememberSaveable {
        mutableStateOf(galleryShareRequest.value.uris)
    }
    var selectedGalleryTaskId by rememberSaveable { mutableStateOf("") }
    LaunchedEffect(routeRequest.value) {
        val requested = routeRequest.value ?: return@LaunchedEffect
        if (Route.entries.any { it.name == requested }) {
            routeName = requested
        }
    }
    LaunchedEffect(galleryShareRequest.value.id) {
        val sharedUris = galleryShareRequest.value.uris
        if (sharedUris.isNotEmpty()) {
            selectedGalleryUris = sharedUris
            routeName = Route.GalleryConfirm.name
        }
    }
    val route = Route.entries.firstOrNull { it.name == routeName } ?: Route.Main
    Box(
        modifier = Modifier
            .fillMaxSize()
            .background(MaterialTheme.colorScheme.background)
            .komiPaperGrid(LocalThemeMode.current.mode, MaterialTheme.colorScheme.onBackground)
    ) {
        when (route) {
            Route.Main -> screenState.SaveableStateProvider("mobile") { MobileShell(
                onAdvanced = { settingsReturn = Route.Main.name; settingsSection = null; routeName = Route.Settings.name },
                onLogs = { routeName = Route.Logs.name },
                onHelp = {
                    val decision = FloatingTourRerunPolicy.onHelpOpened()
                    if (decision.resetCompletion) {
                        FloatingMenuTourPrefs.reset(context)
                    }
                    onboardingOpenedFromHelp = true
                    onboardingFirstRun = false
                    routeName = Route.Onboarding.name
                },
                onImages = { uris ->
                    selectedGalleryUris = uris
                    routeName = Route.GalleryConfirm.name
                },
                onImageHistory = { routeName = Route.GalleryTasks.name },
                onGlossary = { routeName = Route.Glossary.name },
                onDictionaries = { routeName = Route.DictionaryLibrary.name },
            ) }
            Route.Onboarding -> screenState.SaveableStateProvider("setup") { MobileSetupScreen(
                onAdvanced = { section -> settingsSection = section; settingsReturn = Route.Onboarding.name; routeName = Route.Settings.name },
                onFinished = {
                    val decision = FloatingTourRerunPolicy.onOnboardingExit(
                        openedFromHelp = onboardingOpenedFromHelp,
                        completed = true,
                        captureServiceRunning = CaptureServiceState.running.value,
                    )
                    OnboardingPrefs.markCompleted(context)
                    onboardingFirstRun = false
                    onboardingOpenedFromHelp = false
                    routeName = Route.Main.name
                    if (decision.notifyRunningService) {
                        context.startService(
                            CaptureService.runFloatingTourIntent(context)
                        )
                    }
                },
            ) }
            Route.Settings -> SettingsScreen(
                initialSection = settingsSection,
                onBack = { routeName = settingsReturn },
                onOpenGlossary = { routeName = Route.Glossary.name },
                onOpenDictionaryLibrary = { routeName = Route.DictionaryLibrary.name },
                listState = settingsListState,
            )
            Route.Glossary -> GlossaryScreen(onBack = { routeName = Route.Main.name })
            Route.DictionaryLibrary -> DictionaryLibraryScreen(
                onBack = { routeName = Route.Main.name }
            )
            Route.Logs -> LogScreen(onBack = { routeName = Route.Main.name })
            Route.GalleryConfirm -> GalleryTranslationConfirmScreen(
                selectedUris = selectedGalleryUris,
                onSelectionChanged = { selectedGalleryUris = it },
                onBack = {
                    selectedGalleryUris = emptyList()
                    routeName = Route.Main.name
                },
                onCreated = { taskId ->
                    selectedGalleryUris = emptyList()
                    selectedGalleryTaskId = taskId
                    routeName = Route.GalleryTaskDetail.name
                },
            )
            Route.GalleryTasks -> GalleryTranslationTasksScreen(
                onBack = { routeName = Route.Main.name },
                onImagesSelected = { uris ->
                    selectedGalleryUris = uris
                    routeName = Route.GalleryConfirm.name
                },
                onOpenTask = { taskId ->
                    selectedGalleryTaskId = taskId
                    routeName = Route.GalleryTaskDetail.name
                },
            )
            Route.GalleryTaskDetail -> GalleryTranslationTaskDetailScreen(
                taskId = selectedGalleryTaskId,
                onBack = { routeName = Route.GalleryTasks.name },
                onDeleted = {
                    selectedGalleryTaskId = ""
                    routeName = Route.GalleryTasks.name
                },
            )
        }
    }
}
