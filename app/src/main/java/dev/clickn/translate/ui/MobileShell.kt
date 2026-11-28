package dev.clickn.translate.ui

import android.app.Activity
import android.content.ClipboardManager
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.provider.Settings as AndroidSettings
import androidx.activity.compose.BackHandler
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.selection.selectable
import androidx.compose.foundation.selection.selectableGroup
import androidx.compose.ui.semantics.Role
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.outlined.*
import androidx.compose.material.icons.outlined.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.LocalContext
import androidx.lifecycle.compose.LocalLifecycleOwner
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.input.VisualTransformation
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import dev.clickn.translate.AppBrand
import dev.clickn.translate.BuildConfig
import dev.clickn.translate.R
import dev.clickn.translate.capture.CaptureStartRequestActivity
import dev.clickn.translate.data.*
import dev.clickn.translate.history.TextHistoryEntry
import dev.clickn.translate.history.TextHistoryIssue
import dev.clickn.translate.history.TextHistoryState
import dev.clickn.translate.service.CaptureService
import dev.clickn.translate.service.CaptureServiceState
import dev.clickn.translate.ui.theme.*
import dev.clickn.translate.translate.MlKitLanguagePolicy
import dev.clickn.translate.translate.providerBaseUrl
import dev.clickn.translate.capture.CaptureStartMode
import dev.clickn.translate.capture.CaptureStartPreference
import java.text.DateFormat
import java.text.Collator
import java.util.Date
import java.util.Locale
import kotlinx.coroutines.flow.update

private enum class SetupExplanation(val message: Int) {
    START_CAPTURE(R.string.setup_overlay_body),
    OVERLAY(R.string.setup_overlay_body),
    OCR(R.string.setup_recognition_body),
    ACCESSIBILITY(R.string.setup_accessibility_body),
    NOTIFICATIONS(R.string.setup_notifications_body),
    BATTERY(R.string.setup_background_body),
}

internal enum class MobileTab(val title: Int, val icon: ImageVector) {
    SCREEN(R.string.mobile_nav_screen, Icons.Outlined.CropFree),
    TEXT(R.string.mobile_nav_text, Icons.Outlined.Translate),
    HISTORY(R.string.mobile_nav_history, Icons.Outlined.History),
    SETTINGS(R.string.mobile_nav_settings, Icons.Outlined.Tune),
}

/** The app's primary destinations. Capture, gallery and advanced configuration keep their own flows. */
@Composable
fun MobileShell(
    onAdvanced: () -> Unit,
    onGlossary: () -> Unit,
    onDictionaries: () -> Unit,
    onLogs: () -> Unit,
    onHelp: () -> Unit,
    onImages: (List<String>) -> Unit,
    onImageHistory: () -> Unit,
    onAdvancedSection: (String) -> Unit = { onAdvanced() },
    viewModel: MobileViewModel = hiltViewModel(),
) {
    val context = LocalContext.current
    val updater: dev.clickn.translate.update.UpdateViewModel = hiltViewModel()
    ReleaseUpdateHost(updater)
    val settings by viewModel.settings.collectAsState()
    val translation by viewModel.translation.collectAsState()
    val history by viewModel.history.collectAsState()
    val running by CaptureServiceState.running.collectAsState()
    var tabName by rememberSaveable { mutableStateOf(MobileTab.SCREEN.name) }
    var input by rememberSaveable { mutableStateOf("") }
    var sheet by rememberSaveable { mutableStateOf("") }
    var iconRevision by remember { mutableIntStateOf(0) }
    val iconChoice = remember(iconRevision) { BrandIconPrefs.read(context) }
    val provider by viewModel.providerEditor.collectAsState()
    var confirmClear by remember { mutableStateOf(false) }
    var historyEntryId by rememberSaveable { mutableStateOf<Long?>(null) }
    val modelState by viewModel.modelState.collectAsState()
    val captureMode by CaptureStartPreference.mode.collectAsState()
    val shizukuState by viewModel.shizukuState.collectAsState()
    val shizukuReady = if (shizukuState.checking || shizukuState.authorizing) null
        else shizukuState.availability == dev.clickn.translate.shizuku.ShizukuCapabilities.Availability.READY
    var heroSelected by remember { mutableStateOf(CompanionPrefs.hasSelection(context)) }
    DisposableEffect(context) {
        val stop = CompanionPrefs.observe(context) { heroSelected = CompanionPrefs.hasSelection(context) }
        onDispose { stop() }
    }
    var explanation by rememberSaveable { mutableStateOf<SetupExplanation?>(null) }
    var accessibility by remember { mutableStateOf(dev.clickn.translate.trigger.AccessibilityServiceStatus.isEnabled(context)) }
    var notifications by remember { mutableStateOf(hasMobileNotifications(context)) }
    var battery by remember { mutableStateOf(hasMobileBatteryExemption(context)) }
    val permissionPrefs = remember { context.getSharedPreferences("clickn_permissions", Context.MODE_PRIVATE) }
    val notificationRequest = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { notifications = it }
    LaunchedEffect(settings) { settings?.let(viewModel::refreshModels) }
    var overlayAllowed by remember { mutableStateOf(AndroidSettings.canDrawOverlays(context)) }
    LaunchedEffect(Unit) { viewModel.refreshShizuku() }
    val lifecycle = LocalLifecycleOwner.current.lifecycle
    DisposableEffect(lifecycle, settings) {
        val observer = LifecycleEventObserver { _, event ->
            if (event == Lifecycle.Event.ON_RESUME) {
                overlayAllowed = AndroidSettings.canDrawOverlays(context)
                accessibility = dev.clickn.translate.trigger.AccessibilityServiceStatus.isEnabled(context)
                notifications = hasMobileNotifications(context)
                battery = hasMobileBatteryExemption(context)
                heroSelected = CompanionPrefs.hasSelection(context)
                viewModel.refreshShizuku()
                settings?.let(viewModel::refreshModels)
            }
        }
        lifecycle.addObserver(observer)
        onDispose { lifecycle.removeObserver(observer) }
    }
    val gallery = rememberLauncherForActivityResult(ActivityResultContracts.GetMultipleContents()) { uris ->
        if (uris.isNotEmpty()) onImages(uris.map(Uri::toString))
    }
    val tab = MobileTab.valueOf(tabName)
    fun openService() { sheet = "services" }
    fun editInput(value: String) { input = value; viewModel.resetTranslation() }
    val readinessItems = settings?.let { current -> mobileReadinessItems(current, modelState, overlayAllowed,
        captureMode, shizukuReady, heroSelected, notifications, battery, accessibility) }.orEmpty()
    fun openReadinessItem(item: MobileReadinessKey) {
        sheet = ""
        when (item) {
            MobileReadinessKey.LANGUAGES -> sheet = if (settings?.targetLang.isNullOrBlank() || settings?.targetLang == "auto") "target" else "source"
            MobileReadinessKey.SERVICE -> openService()
            MobileReadinessKey.OCR -> explanation = SetupExplanation.OCR
            MobileReadinessKey.TRANSLATION_MODELS -> sheet = "offline"
            MobileReadinessKey.OVERLAY -> explanation = SetupExplanation.OVERLAY
            MobileReadinessKey.CAPTURE -> sheet = "capture"
            MobileReadinessKey.HERO -> sheet = "floating"
            MobileReadinessKey.ACCESSIBILITY -> explanation = SetupExplanation.ACCESSIBILITY
            MobileReadinessKey.NOTIFICATIONS -> explanation = SetupExplanation.NOTIFICATIONS
            MobileReadinessKey.BATTERY -> explanation = SetupExplanation.BATTERY
        }
    }
    fun configure(prompt: SetupExplanation) {
        explanation = null
        when (prompt) {
            SetupExplanation.START_CAPTURE -> context.startActivity(CaptureStartRequestActivity.newIntent(context))
            SetupExplanation.OVERLAY -> openOverlayPermissionSettings(context)
            SetupExplanation.OCR -> onAdvancedSection("ocr")
            SetupExplanation.ACCESSIBILITY -> {
                openSetupAndroidSettings(context, Intent("android.settings.ACCESSIBILITY_DETAILS_SETTINGS")
                    .putExtra("android.intent.extra.COMPONENT_NAME", android.content.ComponentName(context, dev.clickn.translate.trigger.ClickTranslateAccessibilityService::class.java)),
                    Intent(AndroidSettings.ACTION_ACCESSIBILITY_SETTINGS))
            }
            SetupExplanation.NOTIFICATIONS -> {
                if (android.os.Build.VERSION.SDK_INT >= 33 && !notifications && !permissionPrefs.getBoolean("notifications_requested", false)) {
                    permissionPrefs.edit().putBoolean("notifications_requested", true).apply()
                    notificationRequest.launch(android.Manifest.permission.POST_NOTIFICATIONS)
                } else openSetupAndroidSettings(context, Intent(AndroidSettings.ACTION_APP_NOTIFICATION_SETTINGS).putExtra(AndroidSettings.EXTRA_APP_PACKAGE, context.packageName))
            }
            SetupExplanation.BATTERY -> {
                openSetupAndroidSettings(context, Intent(AndroidSettings.ACTION_APPLICATION_DETAILS_SETTINGS, Uri.parse("package:${context.packageName}")),
                    Intent(AndroidSettings.ACTION_IGNORE_BATTERY_OPTIMIZATION_SETTINGS))
            }
        }
    }
    fun preflight(current: Settings, screen: Boolean): Boolean {
        if (current.sourceLang == "auto" && current.translatorEngine in setOf(TranslatorEngine.MYMEMORY, TranslatorEngine.GOOGLE_ML_KIT)) { sheet = "source"; return false }
        if (translationNeedsConfiguration(current)) { viewModel.openProvider(current, current.translatorEngine); return false }
        if (modelState.checking) return false
        if (current.translatorEngine in offlineTranslationEngines && modelState.translationReady != true) { sheet = "offline"; return false }
        if (screen && modelState.ocrReady != true) { onAdvancedSection("ocr"); return false }
        if (screen && (captureMode == null || captureMode == CaptureStartMode.SHIZUKU && shizukuReady != true)) { sheet = "capture"; return false }
        if (screen && !overlayAllowed) { explanation = SetupExplanation.START_CAPTURE; return false }
        return true
    }
    Scaffold(
        containerColor = Color.Transparent,
        bottomBar = {
            NavigationBar(containerColor = MaterialTheme.colorScheme.surfaceContainerLow, tonalElevation = 0.dp) {
                MobileTab.entries.forEach { destination ->
                    NavigationBarItem(
                        selected = tab == destination,
                        onClick = { tabName = destination.name },
                        icon = { Icon(destination.icon, contentDescription = null) },
                        label = { Text(stringResource(destination.title), maxLines = 1) },
                    )
                }
            }
        },
    ) { padding ->
        Box(Modifier.fillMaxSize().padding(padding), contentAlignment = Alignment.TopCenter) {
            val current = settings
            if (current == null) CircularProgressIndicator(Modifier.padding(64.dp))
            else Column(Modifier.widthIn(max = 640.dp).fillMaxSize()) {
                Row(Modifier.fillMaxWidth().padding(horizontal = 24.dp, vertical = 16.dp),
                    verticalAlignment = Alignment.CenterVertically) {
                    BrandLogo(Modifier.size(44.dp), iconChoice)
                    Column(Modifier.padding(start = 12.dp).weight(1f)) {
                        Text(AppBrand.DISPLAY_NAME, fontWeight = FontWeight.Bold, style = MaterialTheme.typography.titleMedium)
                        Text(stringResource(tab.title), style = MaterialTheme.typography.labelMedium,
                            color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                    IconButton(onClick = onHelp) { Icon(Icons.AutoMirrored.Outlined.HelpOutline, stringResource(R.string.mobile_help)) }
                }
                when (tab) {
                    MobileTab.SCREEN -> ScreenHome(current, running, overlayAllowed,
                        onSource = { sheet = "source" }, onTarget = { sheet = "target" },
                        onSwap = { if (current.sourceLang != "auto") {
                            viewModel.resetTranslation()
                            viewModel.selectTranslation { it.copy(sourceLang = current.targetLang, targetLang = current.sourceLang) }
                        } },
                        onProvider = ::openService,
                        onStart = {
                            if (running) context.startService(Intent(context, CaptureService::class.java).setAction(CaptureService.ACTION_STOP))
                            else if (preflight(current, true)) context.startActivity(CaptureStartRequestActivity.newIntent(context))
                        },
                        onPermission = { explanation = SetupExplanation.OVERLAY },
                        onPhoto = { gallery.launch("image/*") }, onText = { tabName = MobileTab.TEXT.name },
                        checking = modelState.checking,
                        ready = mobileScreenReady(current, modelState, overlayAllowed, captureMode, shizukuReady),
                        onShowButton = { context.startService(Intent(context, CaptureService::class.java).setAction(CaptureService.ACTION_SHOW_BUTTON)) },
                        readiness = {
                            MobileReadinessPanel(readinessItems) { sheet = "readiness" }
                        },
                    )
                    MobileTab.TEXT -> TextWorkspace(current, input, translation,
                        onInput = ::editInput, onSource = { sheet = "source" }, onTarget = { sheet = "target" },
                        onSwap = { if (current.sourceLang != "auto") {
                            viewModel.resetTranslation()
                            viewModel.selectTranslation { it.copy(sourceLang = current.targetLang, targetLang = current.sourceLang) }
                        } },
                        onProvider = ::openService,
                        onTranslate = { if (translation.busy) viewModel.resetTranslation() else if (preflight(current, false)) viewModel.translate(input) },
                        checkingModels = modelState.checking,
                    )
                    MobileTab.HISTORY -> HistoryWorkspace(history, onImageHistory,
                        onClear = { confirmClear = true }, onRetry = viewModel::reloadHistory, onEntry = {
                            historyEntryId = it.id
                        })
                    MobileTab.SETTINGS -> SettingsHub(current, onProvider = ::openService,
                        onAppearance = { sheet = "appearance" }, onLanguage = { sheet = "language" },
                        onAdvanced, onGlossary, onDictionaries, onLogs, onCapture = { sheet = "capture" }, onIcon = { sheet = "icon" }, onOffline = { sheet = "offline" },
                        onFloating = { sheet = "floating" }, updater = updater,
                        readiness = { MobileReadinessPanel(readinessItems) { sheet = "readiness" } })
                }
            }
        }
    }
    val current = settings
    if (current != null && sheet.isNotEmpty()) {
        ModalBottomSheet(onDismissRequest = { sheet = "" }) {
            when (sheet) {
                "source", "target" -> LanguageSheet(
                    isSource = sheet == "source", selected = if (sheet == "source") current.sourceLang else current.targetLang,
                    allowAuto = current.translatorEngine !in setOf(TranslatorEngine.MYMEMORY, TranslatorEngine.GOOGLE_ML_KIT),
                    mlKitOnly = current.translatorEngine == TranslatorEngine.GOOGLE_ML_KIT,
                    onSelect = { code ->
                        val source = sheet == "source"
                        viewModel.resetTranslation()
                        viewModel.selectTranslation { mobileLanguagePair(it, source, code) }
                        sheet = ""
                    })
                "services" -> ServicesSheet(current.translatorEngine, current.targetLang) {
                    viewModel.openProvider(current, it); sheet = ""
                }
                "appearance" -> AppearanceSheet()
                "language" -> InterfaceLanguageSheet { sheet = "" }
                "capture" -> CaptureMethodSheet(viewModel)
                "readiness" -> MobileReadinessSheet(readinessItems, captureMode, ::openReadinessItem)
                "icon" -> BrandIconSheet { iconRevision++ }
                "floating" -> FloatingAppearanceSheet(current, { viewModel.update(it) }) {
                    sheet = ""; onAdvancedSection("floating")
                }
                "offline" -> OfflineLibrarySheet(current, viewModel) { section -> sheet = ""; onAdvancedSection(section) }
            }
        }
    }
    provider?.let { editor ->
        ProviderSheet(editor, viewModel,
            onDismiss = viewModel::closeProvider, onAdvanced = {
                viewModel.closeProvider(); onAdvanced()
            })
    }
    explanation?.let { prompt ->
        val body = prompt.message
        val message = if (body == R.string.setup_overlay_body) {
            stringResource(body, context.applicationInfo.loadLabel(context.packageManager).toString())
        } else stringResource(body)
        AlertDialog(onDismissRequest = { explanation = null },
            title = { Text(stringResource(R.string.refine_readiness)) }, text = { Text(message) },
            confirmButton = { TextButton(onClick = { configure(prompt) }) { Text(stringResource(R.string.mobile_configure)) } },
            dismissButton = { TextButton(onClick = { explanation = null }) { Text(stringResource(R.string.mobile_cancel)) } })
    }
    if (confirmClear) AlertDialog(onDismissRequest = { confirmClear = false },
        title = { Text(stringResource(R.string.mobile_clear_history)) },
        text = { Text(stringResource(R.string.mobile_clear_history_body)) },
        confirmButton = { TextButton(onClick = { viewModel.clearHistory(); confirmClear = false }) { Text(stringResource(R.string.mobile_clear)) } },
        dismissButton = { TextButton(onClick = { confirmClear = false }) { Text(stringResource(R.string.mobile_cancel)) } })
    history.entries.firstOrNull { it.id == historyEntryId }?.let { entry ->
        HistoryEntryDialog(entry, onDismiss = { historyEntryId = null }, onUseSource = {
            editInput(entry.source)
            viewModel.selectTranslation { it.copy(sourceLang = entry.from, targetLang = entry.to) }
            tabName = MobileTab.TEXT.name
            historyEntryId = null
        })
    }
    BackHandler(tab != MobileTab.SCREEN && sheet.isEmpty() && provider == null) { tabName = MobileTab.SCREEN.name }
}

@Composable
internal fun ScreenHome(settings: Settings, running: Boolean, allowed: Boolean,
    onSource: () -> Unit, onTarget: () -> Unit, onSwap: () -> Unit, onProvider: () -> Unit,
    onStart: () -> Unit, onPermission: () -> Unit, onPhoto: () -> Unit, onText: () -> Unit,
    checking: Boolean = false, readiness: @Composable () -> Unit = {}, onShowButton: () -> Unit = {},
    ready: Boolean = allowed) {
    LazyColumn(contentPadding = PaddingValues(24.dp, 4.dp, 24.dp, 24.dp), verticalArrangement = Arrangement.spacedBy(20.dp)) {
        item {
            Column(Modifier.fillMaxWidth().background(
                MaterialTheme.colorScheme.primaryContainer, MaterialTheme.shapes.large).padding(20.dp)) {
                Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    Box(Modifier.size(8.dp).background(if (running) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.onPrimaryContainer.copy(alpha = .4f), CircleShape))
                    Text(stringResource(when {
                        running -> R.string.mobile_running
                        checking -> R.string.refine_checking
                        !ready -> R.string.refine_required
                        else -> R.string.mobile_ready
                    }),
                        style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.onPrimaryContainer)
                }
                Text(stringResource(R.string.mobile_hero_title), Modifier.padding(top = 12.dp),
                    style = MaterialTheme.typography.headlineMedium, fontWeight = FontWeight.Bold, color = MaterialTheme.colorScheme.onPrimaryContainer)
                Text(stringResource(if (running) R.string.mobile_running_next_step else R.string.mobile_hero_body), Modifier.padding(top = 8.dp, bottom = 16.dp),
                    style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onPrimaryContainer)
                Button(onClick = if (running) onShowButton else onStart, enabled = running || !checking, modifier = Modifier.fillMaxWidth().heightIn(min = 56.dp),
                    colors = ButtonDefaults.buttonColors()) {
                    Icon(if (running) Icons.Outlined.Visibility else Icons.Outlined.CropFree, null)
                    Spacer(Modifier.width(10.dp))
                    Text(stringResource(when {
                        running -> R.string.floating_show_button
                        checking -> R.string.mobile_checking_models
                        else -> R.string.mobile_start
                    }), fontWeight = FontWeight.SemiBold)
                }
                if (running) TextButton(onClick = onStart, modifier = Modifier.fillMaxWidth()) {
                    Text(stringResource(R.string.mobile_stop))
                }
            }
        }
        item { readiness() }
        item { LanguagePair(settings, onSource, onTarget, onSwap) }
        item { ServiceRow(settings, onProvider) }
        item { SectionLabel(R.string.mobile_quick_actions) }
        item { Row(Modifier.height(IntrinsicSize.Min), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            ActionTile(R.string.mobile_photo, R.string.mobile_photo_body, Icons.Outlined.Image, onPhoto, Modifier.weight(1f).fillMaxHeight())
            ActionTile(R.string.mobile_text_action, R.string.mobile_text_hint, Icons.Outlined.Translate, onText, Modifier.weight(1f).fillMaxHeight())
        } }
    }
}

@Composable
internal fun LanguagePair(settings: Settings, onSource: () -> Unit, onTarget: () -> Unit, onSwap: () -> Unit) {
    Surface(shape = MaterialTheme.shapes.medium, color = MaterialTheme.colorScheme.surfaceContainerLow) {
        Row(Modifier.fillMaxWidth().padding(8.dp), verticalAlignment = Alignment.Top) {
            LanguageCell(R.string.mobile_source, settings.sourceLang, onSource, Modifier.weight(1f))
            IconButton(onClick = onSwap, enabled = settings.sourceLang != "auto", modifier = Modifier.align(Alignment.CenterVertically)) { Icon(Icons.Outlined.SwapHoriz, stringResource(R.string.mobile_swap)) }
            LanguageCell(R.string.mobile_target, settings.targetLang, onTarget, Modifier.weight(1f))
        }
    }
}

@Composable
private fun LanguageCell(label: Int, code: String, onClick: () -> Unit, modifier: Modifier) {
    Column(modifier.clickable(onClick = onClick).padding(12.dp)) {
        Text(stringResource(label), style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
        Row(Modifier.padding(top = 4.dp), verticalAlignment = Alignment.CenterVertically) {
            Text(languageName(code), Modifier.weight(1f), fontWeight = FontWeight.SemiBold, maxLines = 2, overflow = TextOverflow.Ellipsis)
            Icon(Icons.Outlined.ExpandMore, null, Modifier.size(18.dp))
        }
    }
}

@Composable
internal fun languageName(code: String): String = mobileLanguageName(
    code, LocalContext.current.resources.configuration.locales[0], stringResource(R.string.mobile_auto))

private fun mobileLanguageName(code: String, locale: Locale, autoLabel: String): String =
    if (code == Languages.AUTO.code) autoLabel
    else languageDisplayName(code, locale).replaceFirstChar { it.titlecase(locale) }

@Composable
private fun SectionLabel(id: Int) { Text(stringResource(id), style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.Bold) }

@Composable
internal fun ServiceRow(settings: Settings, onClick: () -> Unit) {
    SettingsRow(Icons.Outlined.CloudQueue, stringResource(R.string.mobile_provider), providerName(settings.translatorEngine), onClick)
}

@Composable
private fun ActionTile(title: Int, body: Int, icon: ImageVector, onClick: () -> Unit, modifier: Modifier) {
    Surface(onClick = onClick, modifier = modifier, shape = MaterialTheme.shapes.medium, color = MaterialTheme.colorScheme.surfaceContainerLow) {
        Column(Modifier.padding(20.dp)) {
            Icon(icon, null, Modifier.size(28.dp), tint = MaterialTheme.colorScheme.primary)
            Text(stringResource(title), Modifier.padding(top = 20.dp), fontWeight = FontWeight.Bold)
            Text(stringResource(body), Modifier.padding(top = 6.dp), style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant, maxLines = 3, overflow = TextOverflow.Ellipsis)
        }
    }
}

@Composable
internal fun TextWorkspace(settings: Settings, input: String, state: MobileTranslationState,
    onInput: (String) -> Unit, onSource: () -> Unit, onTarget: () -> Unit, onSwap: () -> Unit,
    onProvider: () -> Unit, onTranslate: () -> Unit, checkingModels: Boolean = false) {
    val context = LocalContext.current
    val clipboard = context.getSystemService(Context.CLIPBOARD_SERVICE) as? ClipboardManager
    val needsSource = settings.sourceLang == "auto" && settings.translatorEngine in setOf(TranslatorEngine.MYMEMORY, TranslatorEngine.GOOGLE_ML_KIT)
    val preparing = checkingModels && !state.busy
    LazyColumn(contentPadding = PaddingValues(24.dp, 4.dp, 24.dp, 24.dp), verticalArrangement = Arrangement.spacedBy(16.dp), modifier = Modifier.imePadding()) {
        item { LanguagePair(settings, onSource, onTarget, onSwap) }
        item { OutlinedTextField(input, onInput, modifier = Modifier.fillMaxWidth(),
            placeholder = { Text(stringResource(R.string.mobile_text_hint)) }, minLines = 6, maxLines = 12, shape = MaterialTheme.shapes.medium) }
        item { Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
            TextButton(onClick = { clipboard?.primaryClip?.getItemAt(0)?.coerceToText(context)?.toString()?.let(onInput) }) {
                Icon(Icons.Outlined.ContentPaste, null, Modifier.size(18.dp)); Spacer(Modifier.width(8.dp)); Text(stringResource(R.string.mobile_paste))
            }
            TextButton(onClick = { onInput("") }, enabled = input.isNotEmpty()) { Text(stringResource(R.string.mobile_clear)) }
        } }
        item { ServiceRow(settings, onProvider) }
        if (needsSource) item { Text(stringResource(R.string.mobile_explicit_source), color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodyMedium) }
        item { Button(onClick = onTranslate, enabled = input.isNotBlank() && !needsSource && !preparing,
            modifier = Modifier.fillMaxWidth().heightIn(min = 56.dp)) {
            if (state.busy || preparing) { CircularProgressIndicator(Modifier.size(20.dp), color = if (state.busy) MaterialTheme.colorScheme.onPrimary else MaterialTheme.colorScheme.onSurfaceVariant, strokeWidth = 2.dp); Spacer(Modifier.width(12.dp)) }
            else { Icon(Icons.Outlined.Translate, null); Spacer(Modifier.width(12.dp)) }
            Text(stringResource(when { state.busy -> R.string.mobile_cancel; preparing -> R.string.mobile_checking_models; else -> R.string.mobile_translate }))
        } }
        item { Surface(shape = MaterialTheme.shapes.medium, color = MaterialTheme.colorScheme.surfaceContainerLow) {
            Column(Modifier.fillMaxWidth().padding(24.dp)) {
                SectionLabel(R.string.mobile_result)
                if (state.error != null) TranslationFailureNotice(state.error, onTranslate, onProvider, retryEnabled = !checkingModels)
                else Text(state.result.ifEmpty { stringResource(if (state.busy) R.string.mobile_translating else R.string.mobile_result_empty) },
                    Modifier.padding(top = 16.dp), style = MaterialTheme.typography.bodyLarge)
                if (state.result.isNotEmpty()) TextOutputActions(state.result, Modifier.padding(top = 16.dp))
            }
        } }
    }
}

@Composable
internal fun HistoryWorkspace(state: TextHistoryState, onImages: () -> Unit, onClear: () -> Unit,
    onRetry: () -> Unit, onEntry: (TextHistoryEntry) -> Unit) {
    val entries = state.entries
    val locale = LocalContext.current.resources.configuration.locales[0]
    LazyColumn(contentPadding = PaddingValues(24.dp, 4.dp, 24.dp, 24.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        item { SettingsRow(Icons.Outlined.PhotoLibrary, stringResource(R.string.mobile_image_history), stringResource(R.string.mobile_photo_body), onImages) }
        if (state.loading) item {
            LinearProgressIndicator(Modifier.fillMaxWidth())
            Text(stringResource(R.string.mobile_history_loading), Modifier.padding(top = 8.dp))
        }
        state.issue?.let { issue -> item {
            Surface(shape = MaterialTheme.shapes.medium, color = MaterialTheme.colorScheme.errorContainer) {
                Column(Modifier.fillMaxWidth().padding(20.dp)) {
                    Text(stringResource(when (issue) {
                        TextHistoryIssue.LEGACY_IMPORT -> R.string.mobile_history_import_error
                        TextHistoryIssue.LEGACY_ERASE -> R.string.mobile_history_erase_error
                        TextHistoryIssue.STORAGE -> R.string.mobile_history_storage_error
                    }))
                    TextButton(onClick = onRetry) { Text(stringResource(R.string.mobile_history_retry)) }
                }
            }
        } }
        if (entries.isNotEmpty() || state.issue != null) item { Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
            Text(stringResource(R.string.mobile_saved), Modifier.weight(1f), fontWeight = FontWeight.Bold)
            TextButton(onClick = onClear, enabled = !state.loading) { Text(stringResource(R.string.mobile_clear_history)) }
        } }
        if (entries.isEmpty() && !state.loading && state.issue == null) item { Column(Modifier.fillMaxWidth().padding(vertical = 48.dp), horizontalAlignment = Alignment.CenterHorizontally) {
            Icon(Icons.Outlined.History, null, Modifier.size(48.dp), tint = MaterialTheme.colorScheme.primary)
            Text(stringResource(R.string.mobile_history_empty), Modifier.padding(top = 20.dp), style = MaterialTheme.typography.titleLarge)
            Text(stringResource(R.string.mobile_history_body), Modifier.padding(top = 12.dp), color = MaterialTheme.colorScheme.onSurfaceVariant)
        } }
        items(entries, key = { it.id }) { entry ->
            Surface(onClick = { onEntry(entry) }, shape = MaterialTheme.shapes.medium, color = MaterialTheme.colorScheme.surfaceContainerLow) {
                Column(Modifier.fillMaxWidth().padding(20.dp)) {
                    Text("${languageName(entry.from)} → ${languageName(entry.to)}", style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.primary)
                    Text(entry.translated, Modifier.padding(top = 10.dp), maxLines = 3, overflow = TextOverflow.Ellipsis, fontWeight = FontWeight.Medium)
                    Text(entry.source, Modifier.padding(top = 6.dp), maxLines = 2, overflow = TextOverflow.Ellipsis, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    Text(DateFormat.getDateTimeInstance(DateFormat.SHORT, DateFormat.SHORT, locale).format(Date(entry.createdAtMs)),
                        Modifier.padding(top = 12.dp), style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }
        }
    }
}

@Composable
internal fun SettingsHub(settings: Settings, onProvider: () -> Unit, onAppearance: () -> Unit, onLanguage: () -> Unit,
    onAdvanced: () -> Unit, onGlossary: () -> Unit, onDictionaries: () -> Unit, onLogs: () -> Unit, onCapture: () -> Unit = {}, onIcon: () -> Unit = {}, onOffline: () -> Unit = {}, onFloating: () -> Unit = {},
    updater: dev.clickn.translate.update.UpdateViewModel? = null, readiness: @Composable () -> Unit = {}) {
    val context = LocalContext.current
    val capture by CaptureStartPreference.mode.collectAsState()
    fun browse(url: String) = openExternalBrowser(context, url)
    LazyColumn(Modifier.testTag("settings-hub"), contentPadding = PaddingValues(24.dp, 4.dp, 24.dp, 24.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        item { readiness() }
        item { SettingsRow(Icons.Outlined.Download, stringResource(R.string.refine_offline), stringResource(R.string.refine_offline_body), onOffline) }
        item { SettingsRow(Icons.Outlined.Image, stringResource(R.string.refine_icon), stringResource(R.string.refine_brand_logo), onIcon) }
        item { SettingsRow(Icons.Outlined.TouchApp, stringResource(R.string.refine_floating), stringResource(R.string.polish_floating_summary), onFloating) }
        item { SectionLabel(R.string.mobile_services) }
        item { ServiceRow(settings, onProvider) }
        item { SettingsRow(Icons.Outlined.CropFree, stringResource(R.string.setup_capture),
            if (capture == CaptureStartMode.SHIZUKU) "Shizuku" else stringResource(R.string.main_capture_system), onCapture) }
        item { SettingsRow(Icons.Outlined.Palette, stringResource(R.string.mobile_appearance), stringResource(R.string.mobile_appearance_body), onAppearance) }
        item { SettingsRow(Icons.Outlined.Language, stringResource(R.string.mobile_interface_language),
            interfaceLanguages.firstOrNull { it.first == AppLocalePrefs.read(context) }?.second ?: stringResource(R.string.mobile_follow_system), onLanguage) }
        item { Spacer(Modifier.height(8.dp)); SectionLabel(R.string.mobile_advanced) }
        item { SettingsRow(Icons.Outlined.Tune, stringResource(R.string.mobile_advanced), stringResource(R.string.mobile_advanced_body), onAdvanced) }
        item { SettingsRow(Icons.AutoMirrored.Outlined.MenuBook, stringResource(R.string.mobile_glossary), "", onGlossary) }
        item { SettingsRow(Icons.AutoMirrored.Outlined.LibraryBooks, stringResource(R.string.mobile_dictionaries), "", onDictionaries) }
        item { SettingsRow(Icons.Outlined.BugReport, stringResource(R.string.mobile_logs), "", onLogs) }
        item { Spacer(Modifier.height(8.dp)); SectionLabel(R.string.mobile_about) }
        item {
            val task = updater?.transfer?.collectAsState()?.value
            val status = updater?.state?.collectAsState()?.value
            val subtitle = when (val current = task) {
                is dev.clickn.translate.update.UpdateViewModel.State.Downloading -> stringResource(R.string.update_download_progress, current.percent)
                is dev.clickn.translate.update.UpdateViewModel.State.Ready -> stringResource(R.string.update_ready, current.apk.version)
                is dev.clickn.translate.update.UpdateViewModel.State.Failed -> current.errorMessage
                else -> if (status is dev.clickn.translate.update.UpdateViewModel.State.Checking) stringResource(R.string.update_btn_checking)
                    else "${stringResource(R.string.mobile_version)} ${BuildConfig.VERSION_NAME}"
            }
            SettingsRow(Icons.Outlined.SystemUpdate, stringResource(if (AppBrand.updatesEnabled) R.string.update_btn_check else R.string.brand_downloads_label),
                subtitle, {
                    if (AppBrand.updatesEnabled && updater != null) updater.check()
                    else browse(dev.clickn.translate.update.UpdateChecker.RELEASE_PAGE_URL)
                })
        }
        item { SettingsRow(Icons.Outlined.Public, stringResource(R.string.mobile_website), "clickn.dev", { browse(AppBrand.WEBSITE_URL) }) }
        item { SettingsRow(Icons.AutoMirrored.Outlined.Chat, stringResource(R.string.mobile_community), "Telegram", { browse(AppBrand.COMMUNITY_URL) }) }
    }
}

@Composable
private fun SettingsRow(icon: ImageVector, title: String, subtitle: String, onClick: () -> Unit) {
    Surface(onClick = onClick, shape = MaterialTheme.shapes.medium, color = MaterialTheme.colorScheme.surfaceContainerLow) {
        Row(Modifier.fillMaxWidth().padding(20.dp), verticalAlignment = Alignment.CenterVertically) {
            Icon(icon, null, Modifier.size(24.dp), tint = MaterialTheme.colorScheme.primary)
            Column(Modifier.weight(1f).padding(horizontal = 16.dp)) {
                Text(title, fontWeight = FontWeight.SemiBold)
                if (subtitle.isNotEmpty()) Text(subtitle, Modifier.padding(top = 4.dp), style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant, maxLines = 2, overflow = TextOverflow.Ellipsis)
            }
            Icon(Icons.AutoMirrored.Outlined.KeyboardArrowRight, null, Modifier.size(20.dp))
        }
    }
}

@Composable
internal fun LanguageSheet(isSource: Boolean, selected: String, allowAuto: Boolean = true, mlKitOnly: Boolean = false, onSelect: (String) -> Unit) {
    var query by rememberSaveable(isSource) { mutableStateOf("") }
    val locale = LocalContext.current.resources.configuration.locales[0]
    val autoLabel = stringResource(R.string.mobile_auto)
    val options = remember(isSource, allowAuto, mlKitOnly, autoLabel, locale) {
        val collator = Collator.getInstance(locale)
        Languages.ALL.filter { language ->
            (language != Languages.AUTO || isSource && allowAuto) &&
                (!mlKitOnly || MlKitLanguagePolicy.isSupportedLanguageTag(language.code))
        }.map { it.code to mobileLanguageName(it.code, locale, autoLabel) }
            .sortedWith(compareBy<Pair<String, String>> { it.first != Languages.AUTO.code }.thenBy(collator) { it.second })
    }
    val search = query.trim()
    val matches = remember(options, search) {
        if (search.isEmpty()) options
        else options.filter { (code, label) -> code.contains(search, true) || label.contains(search, true) }
    }
    val selectedCode = if (mlKitOnly) when (selected) {
        "zh" -> Languages.ZH_CN.code
        "no" -> "nb"
        else -> selected
    } else selected
    Column(Modifier.fillMaxWidth().fillMaxHeight(.8f).padding(horizontal = 24.dp)) {
        Text(stringResource(if (isSource) R.string.mobile_source else R.string.mobile_target), style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold)
        OutlinedTextField(query, { query = it }, Modifier.fillMaxWidth().padding(vertical = 16.dp), singleLine = true,
            label = { Text(stringResource(R.string.lang_picker_search_placeholder)) },
            leadingIcon = { Icon(Icons.Outlined.Search, null) }, shape = MaterialTheme.shapes.small)
        if (matches.isEmpty()) Text(stringResource(R.string.lang_picker_no_match), style = MaterialTheme.typography.bodyMedium)
        LazyColumn(Modifier.selectableGroup()) { items(matches, key = { it.first }) { (code, label) ->
            val checked = code == selectedCode
            ListItem(headlineContent = { Text(label) }, supportingContent = { Text(code) },
                trailingContent = { if (checked) Icon(Icons.Outlined.Check, null, tint = MaterialTheme.colorScheme.primary) },
                modifier = Modifier.selectable(checked, role = Role.RadioButton) { onSelect(code) })
        } }
    }
}

internal fun providerName(engine: TranslatorEngine): String = when (engine) {
    TranslatorEngine.OPENAI -> "OpenAI / DeepSeek"
    TranslatorEngine.ANTHROPIC -> "Anthropic / Claude"
    TranslatorEngine.DEEPL -> "DeepL"
    TranslatorEngine.NIUTRANS -> "NiuTrans"
    TranslatorEngine.YOUDAO_PICTRANS -> "Youdao"
    TranslatorEngine.GOOGLE -> "Google Translate"
    TranslatorEngine.LINGVA -> "Lingva"
    TranslatorEngine.MYMEMORY -> "MyMemory"
    TranslatorEngine.LIBRETRANSLATE -> "LibreTranslate"
    TranslatorEngine.GOOGLE_ML_KIT -> "Google ML Kit"
    TranslatorEngine.VOLC -> "Volcengine"
    TranslatorEngine.BAIDU_FANYI -> "Baidu Translate"
    TranslatorEngine.TENCENT -> "Tencent Translate"
    TranslatorEngine.LOCAL_SAKURA -> "Sakura"
    TranslatorEngine.LOCAL_HY_MT2 -> "HY-MT2"
}

@Composable
internal fun ServicesSheet(selected: TranslatorEngine, targetLang: String = defaultTranslationTarget(), onSelect: (TranslatorEngine) -> Unit) {
    val locale = LocalContext.current.resources.configuration.locales[0]
    var showAll by rememberSaveable { mutableStateOf(false) }
    val free = setOf(TranslatorEngine.GOOGLE, TranslatorEngine.LINGVA, TranslatorEngine.MYMEMORY, TranslatorEngine.LIBRETRANSLATE)
    val offline = setOf(TranslatorEngine.GOOGLE_ML_KIT, TranslatorEngine.LOCAL_SAKURA, TranslatorEngine.LOCAL_HY_MT2)
    val available = TranslatorEngine.entries.filter { android.os.Build.VERSION.SDK_INT >= 33 || it !in setOf(TranslatorEngine.LOCAL_SAKURA, TranslatorEngine.LOCAL_HY_MT2) }.toSet()
    val visible = if (showAll || chineseToolsRelevant(targetLang, locale)) available
        else available - (specializedTranslationEngines - selected)
    LazyColumn(Modifier.fillMaxWidth().fillMaxHeight(.8f).testTag("translation-services"), contentPadding = PaddingValues(24.dp, 0.dp, 24.dp, 24.dp)) {
        item { Text(stringResource(R.string.mobile_select_service), style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold) }
        listOf(R.string.mobile_free_online to free, R.string.mobile_api_services to (visible - free - offline), R.string.mobile_offline to (offline intersect visible)).forEach { (label, engines) ->
            item { Text(stringResource(label), Modifier.padding(top = 24.dp, bottom = 8.dp), style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.primary) }
            items(engines.toList(), key = { it.name }) { engine ->
                ListItem(headlineContent = { Text(providerName(engine)) },
                    trailingContent = { Icon(if (engine == selected) Icons.Outlined.CheckCircle else Icons.AutoMirrored.Outlined.KeyboardArrowRight, null) },
                    modifier = Modifier.clickable { onSelect(engine) })
            }
        }
        if (visible != available) item {
            TextButton(onClick = { showAll = true }, modifier = Modifier.fillMaxWidth()) {
                Text(stringResource(R.string.polish_more_services))
                Icon(Icons.Outlined.ExpandMore, null)
            }
        }
    }
}

private data class ProviderField(val label: String, val secret: Boolean = false,
    val read: (Settings) -> String, val write: (Settings, String) -> Settings)

@Composable
internal fun ProviderSheet(editor: ProviderEditSession, viewModel: MobileViewModel,
    onDismiss: () -> Unit, onAdvanced: () -> Unit) {
    val draft by editor.draft.collectAsState()
    val engine = draft.translatorEngine
    val pending by editor.pending.collectAsState()
    val saveStatus by viewModel.providerSaveState.collectAsState()
    val saving = pending != null || saveStatus == ProviderSaveStatus.SAVING
    LaunchedEffect(pending) {
        pending?.let { request -> editor.finish(request) { advance -> if (advance) onAdvanced() else onDismiss() } }
    }
    val testing by viewModel.testing.collectAsState()
    val connection by viewModel.connection.collectAsState()
    val server = stringResource(R.string.mobile_server)
    val key = stringResource(R.string.mobile_api_key)
    val model = stringResource(R.string.mobile_model)
    val fields = when (engine) {
        TranslatorEngine.OPENAI -> listOf(ProviderField(server, read = { it.baseUrl }, write = { s,v -> s.copy(baseUrl = v) }), ProviderField(key, true, { it.apiKey }, { s,v -> s.copy(apiKey = v) }), ProviderField(model, read = { it.model }, write = { s,v -> s.copy(model = v) }))
        TranslatorEngine.ANTHROPIC -> listOf(ProviderField(server, read = { it.anthropicBaseUrl }, write = { s,v -> s.copy(anthropicBaseUrl = v) }), ProviderField(key, true, { it.anthropicApiKey }, { s,v -> s.copy(anthropicApiKey = v) }), ProviderField(model, read = { it.anthropicModel }, write = { s,v -> s.copy(anthropicModel = v) }))
        TranslatorEngine.LINGVA -> listOf(ProviderField(server, read = { it.lingvaBaseUrl }, write = { s,v -> s.copy(lingvaBaseUrl = v) }))
        TranslatorEngine.LIBRETRANSLATE -> listOf(ProviderField(server, read = { it.libreTranslateBaseUrl }, write = { s,v -> s.copy(libreTranslateBaseUrl = v) }), ProviderField("$key (${stringResource(R.string.mobile_optional)})", true, { it.libreTranslateApiKey }, { s,v -> s.copy(libreTranslateApiKey = v) }))
        TranslatorEngine.MYMEMORY -> listOf(ProviderField("${stringResource(R.string.mobile_email)} (${stringResource(R.string.mobile_optional)})", read = { it.myMemoryEmail }, write = { s,v -> s.copy(myMemoryEmail = v) }))
        TranslatorEngine.DEEPL -> listOf(ProviderField(key, true, { it.deeplApiKey }, { s,v -> s.copy(deeplApiKey = v) }))
        TranslatorEngine.NIUTRANS -> listOf(ProviderField(key, true, { it.niuTransApiKey }, { s,v -> s.copy(niuTransApiKey = v) }), ProviderField("App ID", read = { it.niuTransAppId }, write = { s,v -> s.copy(niuTransAppId = v) }))
        TranslatorEngine.BAIDU_FANYI -> listOf(ProviderField("App ID", read = { it.baiduFanyiAppId }, write = { s,v -> s.copy(baiduFanyiAppId = v) }), ProviderField(key, true, { it.baiduFanyiSecretKey }, { s,v -> s.copy(baiduFanyiSecretKey = v) }))
        TranslatorEngine.YOUDAO_PICTRANS -> listOf(ProviderField("App Key", true, { it.youdaoAppKey }, { s,v -> s.copy(youdaoAppKey = v) }), ProviderField("App Secret", true, { it.youdaoAppSecret }, { s,v -> s.copy(youdaoAppSecret = v) }))
        TranslatorEngine.VOLC -> listOf(ProviderField("Access Key ID", read = { it.volcAccessKeyId }, write = { s,v -> s.copy(volcAccessKeyId = v) }), ProviderField("Secret Access Key", true, { it.volcSecretAccessKey }, { s,v -> s.copy(volcSecretAccessKey = v) }), ProviderField("Region", read = { it.volcRegion }, write = { s,v -> s.copy(volcRegion = v) }))
        TranslatorEngine.TENCENT -> listOf(ProviderField("Secret ID", read = { it.tencentSecretId }, write = { s,v -> s.copy(tencentSecretId = v) }), ProviderField("Secret Key", true, { it.tencentSecretKey }, { s,v -> s.copy(tencentSecretKey = v) }), ProviderField("Region", read = { it.tencentRegion }, write = { s,v -> s.copy(tencentRegion = v) }))
        else -> emptyList()
    }
    val validConfig = when (engine) {
        TranslatorEngine.LINGVA -> runCatching { providerBaseUrl(draft.lingvaBaseUrl) }.isSuccess
        TranslatorEngine.LIBRETRANSLATE -> runCatching { providerBaseUrl(draft.libreTranslateBaseUrl) }.isSuccess
        else -> true
    }
    val local = engine in setOf(TranslatorEngine.GOOGLE_ML_KIT, TranslatorEngine.LOCAL_SAKURA, TranslatorEngine.LOCAL_HY_MT2)
    fun saveAndConfirm(openAdvanced: Boolean) {
        editor.submit(openAdvanced) {
            val saved = editor.draft.value
            viewModel.saveProvider { existing ->
                fields.fold(if (engine == TranslatorEngine.GOOGLE_ML_KIT) mobileMlKitPair(existing) else existing.copy(translatorEngine = engine)) { s, field ->
                    field.write(s, field.read(saved))
                }.let { if (engine == TranslatorEngine.DEEPL) it.copy(deeplPro = saved.deeplPro) else it }
            }
        }
    }
    val canDismiss by rememberUpdatedState({ editor.pending.value == null && viewModel.providerSaveState.value != ProviderSaveStatus.SAVING })
    val sheetState = rememberModalBottomSheetState(
        skipPartiallyExpanded = true,
        confirmValueChange = { value -> value != SheetValue.Hidden || canDismiss() },
    )
    ModalBottomSheet(onDismissRequest = { if (canDismiss()) onDismiss() }, sheetState = sheetState) {
        LazyColumn(Modifier.fillMaxWidth().heightIn(max = 600.dp).imePadding().testTag("provider-form"), contentPadding = PaddingValues(24.dp, 0.dp, 24.dp, 24.dp), verticalArrangement = Arrangement.spacedBy(16.dp)) {
            item { Text(providerName(engine), style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold) }
            if (fields.isEmpty()) item { Text(stringResource(if (local) R.string.mobile_models_body else R.string.mobile_no_key), color = MaterialTheme.colorScheme.onSurfaceVariant) }
            if (engine == TranslatorEngine.MYMEMORY) item { Text(stringResource(R.string.mobile_explicit_source), style = MaterialTheme.typography.bodyMedium) }
            items(fields) { field ->
                var visible by remember { mutableStateOf(false) }
                OutlinedTextField(field.read(draft), { value -> editor.draft.update { field.write(it, value) }; viewModel.clearConnection() }, Modifier.fillMaxWidth(), enabled = !saving,
                    label = { Text(field.label) }, isError = field.label == server && !validConfig, singleLine = true, shape = MaterialTheme.shapes.small,
                    visualTransformation = if (field.secret && !visible) PasswordVisualTransformation() else VisualTransformation.None,
                    trailingIcon = if (field.secret) ({ IconButton(onClick = { visible = !visible }, enabled = !saving) {
                        Icon(if (visible) Icons.Outlined.VisibilityOff else Icons.Outlined.Visibility,
                            stringResource(if (visible) R.string.mobile_hide_key else R.string.mobile_show_key))
                    } }) else null)
            }
            if (engine == TranslatorEngine.DEEPL) item {
                Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                    Text("DeepL API Pro", Modifier.weight(1f)); Switch(draft.deeplPro, { value -> editor.draft.update { it.copy(deeplPro = value) }; viewModel.clearConnection() }, enabled = !saving)
                }
            }
            item { connection?.let { Text(stringResource(if (it.success) R.string.mobile_test_ok else R.string.mobile_error),
                color = if (it.success) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.error) } }
            if (saveStatus == ProviderSaveStatus.FAILED) item {
                Text(stringResource(R.string.mobile_provider_save_error), color = MaterialTheme.colorScheme.error)
            }
            item { Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                OutlinedButton(onClick = { viewModel.test(draft) }, enabled = !saving && !testing && validConfig, modifier = Modifier.weight(1f).heightIn(min = 52.dp)) {
                    if (testing) CircularProgressIndicator(Modifier.size(18.dp), strokeWidth = 2.dp)
                    else Text(stringResource(R.string.mobile_test))
                }
                Button(onClick = { saveAndConfirm(openAdvanced = false) }, enabled = !saving && !testing && validConfig,
                    modifier = Modifier.weight(1f).heightIn(min = 52.dp).testTag("provider-save")) {
                    if (saving) {
                        CircularProgressIndicator(Modifier.size(18.dp), strokeWidth = 2.dp)
                        Spacer(Modifier.width(8.dp))
                    }
                    Text(stringResource(when {
                        saving -> R.string.mobile_provider_saving
                        saveStatus == ProviderSaveStatus.FAILED -> R.string.mobile_provider_save_retry
                        else -> R.string.mobile_save
                    }))
                }
            } }
            item { TextButton(onClick = { saveAndConfirm(openAdvanced = true) }, enabled = !saving && !testing,
                modifier = Modifier.fillMaxWidth().testTag("provider-advanced")) {
                Text(stringResource(if (local) R.string.mobile_manage_models else R.string.mobile_advanced))
            } }
        }
    }
}

@Composable
internal fun AppearanceSheet() {
    val theme = LocalThemeMode.current
    val accent = LocalThemeAccent.current
    LazyColumn(Modifier.fillMaxWidth().testTag("appearance-options"), contentPadding = PaddingValues(24.dp, 0.dp, 24.dp, 32.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        item { Text(stringResource(R.string.mobile_appearance), style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold) }
        item { SectionLabel(R.string.mobile_mode) }
        themeChoices.chunked(2).forEach { choices -> item { ThemeChoiceRow(choices) } }
        if (theme.mode !in ThemeMode.PAPER_DAY..ThemeMode.PAPER_NORD) {
            item { SectionLabel(R.string.mobile_accent) }
            item { FlowRow(Modifier.fillMaxWidth().selectableGroup(), horizontalArrangement = Arrangement.spacedBy(16.dp)) {
                ThemeAccent.entries.forEach { choice ->
                    Column(horizontalAlignment = Alignment.CenterHorizontally, modifier = Modifier.selectable(accent.accent == choice, role = Role.RadioButton, onClick = { accent.setAccent(choice) }).padding(4.dp)) {
                        Box(Modifier.size(44.dp).background(Color(choice.lightColor), CircleShape), contentAlignment = Alignment.Center) {
                            if (accent.accent == choice) Icon(Icons.Outlined.Check, null, tint = Color.White)
                        }
                        Text(stringResource(choice.label), Modifier.padding(top = 8.dp), style = MaterialTheme.typography.labelMedium, maxLines = 1)
                    }
                }
            } }
        }
    }
}

internal val interfaceLanguages = listOf("en" to "English", "ru" to "Русский", "de" to "Deutsch", "fr" to "Français", "es" to "Español", "zh-CN" to "中文")

@Composable
internal fun InterfaceLanguageSheet(onDismiss: () -> Unit) {
    val context = LocalContext.current
    val current = AppLocalePrefs.read(context)
    val choices = listOf("" to stringResource(R.string.mobile_follow_system)) + interfaceLanguages
    LazyColumn(Modifier.fillMaxWidth(), contentPadding = PaddingValues(24.dp, 0.dp, 24.dp, 32.dp)) {
        item { Text(stringResource(R.string.mobile_interface_language), style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold, modifier = Modifier.padding(bottom = 16.dp)) }
        items(choices) { (tag,label) ->
            ListItem(headlineContent = { Text(label) }, trailingContent = { if (current == tag) Icon(Icons.Outlined.Check, null) },
                modifier = Modifier.clickable {
                    AppLocalePrefs.write(context, tag); onDismiss()
                })
        }
    }
}

@Composable
fun MobileWelcomeScreen(onFinished: () -> Unit) {
    Scaffold { padding ->
        Box(Modifier.fillMaxSize().padding(padding), contentAlignment = Alignment.Center) {
            Column(Modifier.widthIn(max = 560.dp).fillMaxWidth().padding(32.dp), verticalArrangement = Arrangement.spacedBy(24.dp)) {
                BrandLogo(Modifier.size(88.dp))
                Text(stringResource(R.string.mobile_welcome), style = MaterialTheme.typography.headlineLarge, fontWeight = FontWeight.Bold)
                listOf(Icons.Outlined.CropFree to R.string.mobile_welcome_screen, Icons.Outlined.Translate to R.string.mobile_welcome_text, Icons.Outlined.Palette to R.string.mobile_welcome_style).forEach { (icon,text) ->
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Icon(icon, null, tint = MaterialTheme.colorScheme.primary)
                        Text(stringResource(text), Modifier.padding(start = 16.dp), style = MaterialTheme.typography.bodyLarge)
                    }
                }
                Button(onClick = onFinished, modifier = Modifier.fillMaxWidth().heightIn(min = 56.dp)) { Text(stringResource(R.string.mobile_get_started)) }
            }
        }
    }
}


private fun hasMobileNotifications(context: Context): Boolean = android.os.Build.VERSION.SDK_INT < 33 ||
    androidx.core.content.ContextCompat.checkSelfPermission(context, android.Manifest.permission.POST_NOTIFICATIONS) == android.content.pm.PackageManager.PERMISSION_GRANTED
private fun hasMobileBatteryExemption(context: Context): Boolean =
    context.getSystemService(android.os.PowerManager::class.java)?.isIgnoringBatteryOptimizations(context.packageName) == true
