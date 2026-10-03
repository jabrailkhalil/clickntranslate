package dev.clickn.translate.ui

import android.app.Activity
import android.content.ClipData
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
import androidx.compose.ui.graphics.Brush
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
import dev.clickn.translate.service.CaptureService
import dev.clickn.translate.service.CaptureServiceState
import dev.clickn.translate.ui.theme.*
import dev.clickn.translate.translate.MlKitLanguagePolicy
import dev.clickn.translate.translate.providerBaseUrl
import dev.clickn.translate.capture.CaptureStartMode
import dev.clickn.translate.capture.CaptureStartPreference
import java.text.DateFormat
import java.util.Date
import java.util.Locale

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
    viewModel: MobileViewModel = hiltViewModel(),
) {
    val context = LocalContext.current
    val settings by viewModel.settings.collectAsState()
    val translation by viewModel.translation.collectAsState()
    val history by viewModel.history.collectAsState()
    val running by CaptureServiceState.running.collectAsState()
    var tabName by rememberSaveable { mutableStateOf(MobileTab.SCREEN.name) }
    var input by rememberSaveable { mutableStateOf("") }
    var sheet by rememberSaveable { mutableStateOf("") }
    var iconRevision by remember { mutableIntStateOf(0) }
    val iconChoice = remember(iconRevision) { BrandIconPrefs.read(context) }
    var iconBitmap by remember { mutableStateOf<android.graphics.Bitmap?>(null) }
    LaunchedEffect(iconRevision) { iconBitmap = kotlinx.coroutines.withContext(kotlinx.coroutines.Dispatchers.IO) { BrandIconPrefs.bitmap(context) } }
    var provider by remember { mutableStateOf<TranslatorEngine?>(null) }
    var confirmClear by remember { mutableStateOf(false) }
    var overlayAllowed by remember { mutableStateOf(AndroidSettings.canDrawOverlays(context)) }
    LaunchedEffect(Unit) {
        if (CaptureStartPreference.mode.value == null) CaptureStartPreference.select(CaptureStartMode.SYSTEM)
    }
    val lifecycle = LocalLifecycleOwner.current.lifecycle
    DisposableEffect(lifecycle) {
        val observer = LifecycleEventObserver { _, event ->
            if (event == Lifecycle.Event.ON_RESUME) overlayAllowed = AndroidSettings.canDrawOverlays(context)
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
    fun grantOverlay() {
        openOverlayPermissionSettings(context)
    }
    Scaffold(
        containerColor = MaterialTheme.colorScheme.background,
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
                    BrandLogo(Modifier.size(44.dp), iconChoice, iconBitmap)
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
                            viewModel.update { it.copy(sourceLang = current.targetLang, targetLang = current.sourceLang) }
                        } },
                        onProvider = ::openService,
                        onStart = {
                            if (running) context.startService(Intent(context, CaptureService::class.java).setAction(CaptureService.ACTION_STOP))
                            else if (current.sourceLang == "auto" && current.translatorEngine in setOf(TranslatorEngine.MYMEMORY, TranslatorEngine.GOOGLE_ML_KIT)) sheet = "source"
                            else if (!overlayAllowed) grantOverlay()
                            else context.startActivity(CaptureStartRequestActivity.newIntent(context))
                        },
                        onPermission = ::grantOverlay,
                        onPhoto = { gallery.launch("image/*") }, onText = { tabName = MobileTab.TEXT.name },
                    )
                    MobileTab.TEXT -> TextWorkspace(current, input, translation,
                        onInput = ::editInput, onSource = { sheet = "source" }, onTarget = { sheet = "target" },
                        onSwap = { if (current.sourceLang != "auto") {
                            viewModel.resetTranslation()
                            viewModel.update { it.copy(sourceLang = current.targetLang, targetLang = current.sourceLang) }
                        } },
                        onProvider = ::openService,
                        onTranslate = { if (translation.busy) viewModel.resetTranslation() else viewModel.translate(input) },
                    )
                    MobileTab.HISTORY -> HistoryWorkspace(history, onImageHistory,
                        onClear = { confirmClear = true }, onEntry = {
                            editInput(it.source)
                            viewModel.update { currentSettings -> currentSettings.copy(sourceLang = it.from, targetLang = it.to) }
                            tabName = MobileTab.TEXT.name
                        })
                    MobileTab.SETTINGS -> SettingsHub(current, onProvider = ::openService,
                        onAppearance = { sheet = "appearance" }, onLanguage = { sheet = "language" },
                        onAdvanced, onGlossary, onDictionaries, onLogs, onCapture = { sheet = "capture" }, onIcon = { sheet = "icon" }, onOffline = { sheet = "offline" })
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
                    allowedCodes = if (current.translatorEngine == TranslatorEngine.GOOGLE_ML_KIT) MlKitLanguagePolicy.supportedLanguageTags else null,
                    onSelect = { code ->
                        val source = sheet == "source"
                        viewModel.resetTranslation()
                        viewModel.update { mobileLanguagePair(it, source, code) }
                        sheet = ""
                    })
                "services" -> ServicesSheet(current.translatorEngine) {
                    provider = it; sheet = ""; viewModel.clearConnection()
                }
                "appearance" -> AppearanceSheet()
                "language" -> InterfaceLanguageSheet { sheet = "" }
                "capture" -> CaptureMethodSheet(viewModel)
                "icon" -> BrandIconSheet { iconRevision++ }
            }
        }
    }
    provider?.let { selected ->
        ProviderSheet(current ?: Settings(), selected, viewModel,
            onDismiss = { provider = null; viewModel.clearConnection() }, onAdvanced = {
                provider = null; viewModel.clearConnection(); onAdvanced()
            })
    }
    if (confirmClear) AlertDialog(onDismissRequest = { confirmClear = false },
        title = { Text(stringResource(R.string.mobile_clear_history)) },
        text = { Text(stringResource(R.string.mobile_clear_history_body)) },
        confirmButton = { TextButton(onClick = { viewModel.clearHistory(); confirmClear = false }) { Text(stringResource(R.string.mobile_clear)) } },
        dismissButton = { TextButton(onClick = { confirmClear = false }) { Text(stringResource(R.string.mobile_cancel)) } })
    BackHandler(tab != MobileTab.SCREEN && sheet.isEmpty() && provider == null) { tabName = MobileTab.SCREEN.name }
}

@Composable
internal fun ScreenHome(settings: Settings, running: Boolean, allowed: Boolean,
    onSource: () -> Unit, onTarget: () -> Unit, onSwap: () -> Unit, onProvider: () -> Unit,
    onStart: () -> Unit, onPermission: () -> Unit, onPhoto: () -> Unit, onText: () -> Unit) {
    LazyColumn(contentPadding = PaddingValues(24.dp, 4.dp, 24.dp, 24.dp), verticalArrangement = Arrangement.spacedBy(20.dp)) {
        item {
            Column(Modifier.fillMaxWidth().background(
                Brush.linearGradient(listOf(MaterialTheme.colorScheme.primaryContainer, MaterialTheme.colorScheme.secondaryContainer)),
                MaterialTheme.shapes.large).padding(24.dp)) {
                Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    Box(Modifier.size(8.dp).background(if (running) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.onPrimaryContainer.copy(alpha = .4f), CircleShape))
                    Text(stringResource(if (running) R.string.mobile_running else R.string.mobile_ready),
                        style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.onPrimaryContainer)
                }
                Text(stringResource(R.string.mobile_hero_title), Modifier.padding(top = 20.dp),
                    style = MaterialTheme.typography.headlineLarge, fontWeight = FontWeight.Bold, color = MaterialTheme.colorScheme.onPrimaryContainer)
                Text(stringResource(R.string.mobile_hero_body), Modifier.padding(top = 12.dp, bottom = 24.dp),
                    style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onPrimaryContainer)
                Button(onClick = onStart, modifier = Modifier.fillMaxWidth().heightIn(min = 56.dp)) {
                    Icon(if (running) Icons.Outlined.Stop else Icons.Outlined.CropFree, null)
                    Spacer(Modifier.width(10.dp))
                    Text(stringResource(if (running) R.string.mobile_stop else R.string.mobile_start), fontWeight = FontWeight.SemiBold)
                }
            }
        }
        item { LanguagePair(settings, onSource, onTarget, onSwap) }
        item { ServiceRow(settings, onProvider) }
        if (!allowed) item {
            Surface(color = MaterialTheme.colorScheme.surfaceContainer, shape = MaterialTheme.shapes.medium) {
                Column(Modifier.padding(20.dp)) {
                    Text(stringResource(R.string.mobile_permission_title), fontWeight = FontWeight.SemiBold)
                    Text(stringResource(R.string.mobile_permission_body), Modifier.padding(top = 8.dp), style = MaterialTheme.typography.bodyMedium)
                    TextButton(onClick = onPermission, modifier = Modifier.align(Alignment.End)) { Text(stringResource(R.string.mobile_permission_enable)) }
                }
            }
        }
        item { SectionLabel(R.string.mobile_quick_actions) }
        item { Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            ActionTile(R.string.mobile_photo, R.string.mobile_photo_body, Icons.Outlined.Image, onPhoto, Modifier.weight(1f))
            ActionTile(R.string.mobile_text_action, R.string.mobile_text_hint, Icons.Outlined.Translate, onText, Modifier.weight(1f))
        } }
    }
}

@Composable
internal fun LanguagePair(settings: Settings, onSource: () -> Unit, onTarget: () -> Unit, onSwap: () -> Unit) {
    Surface(shape = MaterialTheme.shapes.medium, color = MaterialTheme.colorScheme.surfaceContainerLow) {
        Row(Modifier.fillMaxWidth().padding(8.dp), verticalAlignment = Alignment.CenterVertically) {
            LanguageCell(R.string.mobile_source, settings.sourceLang, onSource, Modifier.weight(1f))
            IconButton(onClick = onSwap, enabled = settings.sourceLang != "auto") { Icon(Icons.Outlined.SwapHoriz, stringResource(R.string.mobile_swap)) }
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
private fun languageName(code: String): String = if (code == "auto") stringResource(R.string.mobile_auto)
    else Locale.forLanguageTag(code).getDisplayName(LocalContext.current.resources.configuration.locales[0]).replaceFirstChar { it.titlecase() }

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
    onProvider: () -> Unit, onTranslate: () -> Unit) {
    val context = LocalContext.current
    val clipboard = context.getSystemService(Context.CLIPBOARD_SERVICE) as? ClipboardManager
    var copied by remember { mutableStateOf(false) }
    LaunchedEffect(state.result) { copied = false }
    val needsSource = settings.sourceLang == "auto" && settings.translatorEngine in setOf(TranslatorEngine.MYMEMORY, TranslatorEngine.GOOGLE_ML_KIT)
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
        item { Button(onClick = onTranslate, enabled = input.isNotBlank() && !needsSource,
            modifier = Modifier.fillMaxWidth().heightIn(min = 56.dp)) {
            if (state.busy) { CircularProgressIndicator(Modifier.size(20.dp), color = MaterialTheme.colorScheme.onPrimary, strokeWidth = 2.dp); Spacer(Modifier.width(12.dp)) }
            else { Icon(Icons.Outlined.Translate, null); Spacer(Modifier.width(12.dp)) }
            Text(stringResource(if (state.busy) R.string.mobile_cancel else R.string.mobile_translate))
        } }
        item { Surface(shape = MaterialTheme.shapes.medium, color = MaterialTheme.colorScheme.surfaceContainerLow) {
            Column(Modifier.fillMaxWidth().padding(24.dp)) {
                SectionLabel(R.string.mobile_result)
                Text(if (state.error != null) stringResource(R.string.mobile_error)
                    else state.result.ifEmpty { stringResource(if (state.busy) R.string.mobile_translating else R.string.mobile_result_empty) },
                    Modifier.padding(top = 16.dp), style = MaterialTheme.typography.bodyLarge,
                    color = if (state.error != null) MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.onSurface)
                if (state.error != null) TextButton(onClick = onProvider) { Text(stringResource(R.string.mobile_configure)) }
                if (state.result.isNotEmpty()) Row(Modifier.padding(top = 16.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    TextButton(onClick = { clipboard?.setPrimaryClip(ClipData.newPlainText(AppBrand.DISPLAY_NAME, state.result)); copied = clipboard != null }) {
                        Icon(Icons.Outlined.ContentCopy, null, Modifier.size(18.dp)); Spacer(Modifier.width(8.dp)); Text(stringResource(if (copied) R.string.mobile_copied else R.string.mobile_copy))
                    }
                    TextButton(onClick = { context.startActivity(Intent.createChooser(Intent(Intent.ACTION_SEND).apply {
                        type = "text/plain"; putExtra(Intent.EXTRA_TEXT, state.result)
                    }, null)) }) { Icon(Icons.Outlined.Share, null, Modifier.size(18.dp)); Spacer(Modifier.width(8.dp)); Text(stringResource(R.string.mobile_share)) }
                }
            }
        } }
    }
}

@Composable
internal fun HistoryWorkspace(entries: List<MobileHistoryEntry>, onImages: () -> Unit, onClear: () -> Unit, onEntry: (MobileHistoryEntry) -> Unit) {
    val locale = LocalContext.current.resources.configuration.locales[0]
    LazyColumn(contentPadding = PaddingValues(24.dp, 4.dp, 24.dp, 24.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        item { SettingsRow(Icons.Outlined.PhotoLibrary, stringResource(R.string.mobile_image_history), stringResource(R.string.mobile_photo_body), onImages) }
        if (entries.isEmpty()) item { Column(Modifier.fillMaxWidth().padding(vertical = 48.dp), horizontalAlignment = Alignment.CenterHorizontally) {
            Icon(Icons.Outlined.History, null, Modifier.size(48.dp), tint = MaterialTheme.colorScheme.primary)
            Text(stringResource(R.string.mobile_history_empty), Modifier.padding(top = 20.dp), style = MaterialTheme.typography.titleLarge)
            Text(stringResource(R.string.mobile_history_body), Modifier.padding(top = 12.dp), color = MaterialTheme.colorScheme.onSurfaceVariant)
        } } else {
            item { Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                Text(stringResource(R.string.mobile_saved), Modifier.weight(1f), fontWeight = FontWeight.Bold)
                TextButton(onClick = onClear) { Text(stringResource(R.string.mobile_clear_history)) }
            } }
            items(entries, key = { it.id }) { entry ->
                Surface(onClick = { onEntry(entry) }, shape = MaterialTheme.shapes.medium, color = MaterialTheme.colorScheme.surfaceContainerLow) {
                    Column(Modifier.fillMaxWidth().padding(20.dp)) {
                        Text("${languageName(entry.from)} → ${languageName(entry.to)}", style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.primary)
                        Text(entry.translated, Modifier.padding(top = 10.dp), maxLines = 3, overflow = TextOverflow.Ellipsis, fontWeight = FontWeight.Medium)
                        Text(entry.source, Modifier.padding(top = 6.dp), maxLines = 2, overflow = TextOverflow.Ellipsis, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        Text(DateFormat.getDateTimeInstance(DateFormat.SHORT, DateFormat.SHORT, locale).format(Date(entry.id)),
                            Modifier.padding(top = 12.dp), style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                }
            }
        }
    }
}

@Composable
internal fun SettingsHub(settings: Settings, onProvider: () -> Unit, onAppearance: () -> Unit, onLanguage: () -> Unit,
    onAdvanced: () -> Unit, onGlossary: () -> Unit, onDictionaries: () -> Unit, onLogs: () -> Unit, onCapture: () -> Unit = {}, onIcon: () -> Unit = {}, onOffline: () -> Unit = {}) {
    val context = LocalContext.current
    val capture by CaptureStartPreference.mode.collectAsState()
    fun browse(url: String) { context.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(url))) }
    LazyColumn(contentPadding = PaddingValues(24.dp, 4.dp, 24.dp, 24.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        item { SettingsRow(Icons.Outlined.Download, stringResource(R.string.refine_offline), stringResource(R.string.refine_offline_body), onOffline) }
        item { SettingsRow(Icons.Outlined.Image, stringResource(R.string.refine_icon), stringResource(R.string.refine_brand_logo), onIcon) }
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
        item { SettingsRow(Icons.Outlined.Public, stringResource(R.string.mobile_website), "clickn.dev", { browse(AppBrand.WEBSITE_URL) }) }
        item { SettingsRow(Icons.AutoMirrored.Outlined.Chat, stringResource(R.string.mobile_community), "Telegram", { browse(AppBrand.COMMUNITY_URL) }) }
        item { Text("${stringResource(R.string.mobile_version)} ${BuildConfig.VERSION_NAME}",
            Modifier.fillMaxWidth().padding(vertical = 16.dp), style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant) }
    }
}

@Composable
private fun CaptureMethodSheet(viewModel: MobileViewModel) {
    val context = LocalContext.current
    val selected by CaptureStartPreference.mode.collectAsState()
    val ready by viewModel.captureReady.collectAsState()
    Column(Modifier.fillMaxWidth().padding(24.dp), verticalArrangement = Arrangement.spacedBy(16.dp)) {
        Text(stringResource(R.string.setup_capture), style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold)
        ListItem(headlineContent = { Text(stringResource(R.string.main_capture_system)) },
            supportingContent = { Text(stringResource(R.string.setup_capture_body)) },
            leadingContent = { RadioButton(selected != CaptureStartMode.SHIZUKU, null) },
            modifier = Modifier.clickable { CaptureStartPreference.select(CaptureStartMode.SYSTEM) })
        ListItem(headlineContent = { Text("Shizuku") },
            supportingContent = { Text(stringResource(R.string.main_hint_shizuku_not_paired)) },
            leadingContent = { RadioButton(selected == CaptureStartMode.SHIZUKU, null) },
            modifier = Modifier.clickable { viewModel.prepareShizuku() })
        ready?.let { Text(stringResource(if (it) R.string.main_hint_shizuku_ready else R.string.main_snack_shizuku_unavailable),
            color = if (it) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.error) }
        OutlinedButton(onClick = {
            val launch = context.packageManager.getLaunchIntentForPackage("moe.shizuku.privileged.api")
            if (launch != null) openSetupAndroidSettings(context, launch)
            else android.widget.Toast.makeText(context, R.string.main_hint_shizuku_not_installed, android.widget.Toast.LENGTH_LONG).show()
        }, modifier = Modifier.fillMaxWidth()) { Text("Shizuku") }
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
internal fun LanguageSheet(isSource: Boolean, selected: String, allowAuto: Boolean = true, allowedCodes: Set<String>? = null, onSelect: (String) -> Unit) {
    var query by remember { mutableStateOf("") }
    val locale = LocalContext.current.resources.configuration.locales[0]
    Column(Modifier.fillMaxWidth().fillMaxHeight(.8f).padding(horizontal = 24.dp)) {
        Text(stringResource(if (isSource) R.string.mobile_source else R.string.mobile_target), style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold)
        OutlinedTextField(query, { query = it }, Modifier.fillMaxWidth().padding(vertical = 16.dp), singleLine = true,
            leadingIcon = { Icon(Icons.Outlined.Search, null) }, shape = MaterialTheme.shapes.small)
        val choices = Languages.ALL.filter { (isSource && allowAuto || it.code != "auto") &&
            (allowedCodes == null || it.code.substringBefore('-') in allowedCodes) &&
            (query.isBlank() || it.code.contains(query, true) || Locale.forLanguageTag(it.code).getDisplayName(locale).contains(query, true)) }
            .sortedBy { if (it.code == "auto") "" else Locale.forLanguageTag(it.code).getDisplayName(locale) }
        LazyColumn { items(choices, key = { it.code }) { language ->
            ListItem(headlineContent = { Text(languageName(language.code)) }, supportingContent = { Text(language.code) },
                trailingContent = { if (selected == language.code) Icon(Icons.Outlined.Check, null, tint = MaterialTheme.colorScheme.primary) },
                modifier = Modifier.clickable { onSelect(language.code) })
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
internal fun ServicesSheet(selected: TranslatorEngine, onSelect: (TranslatorEngine) -> Unit) {
    val free = setOf(TranslatorEngine.GOOGLE, TranslatorEngine.LINGVA, TranslatorEngine.MYMEMORY, TranslatorEngine.LIBRETRANSLATE)
    val offline = setOf(TranslatorEngine.GOOGLE_ML_KIT, TranslatorEngine.LOCAL_SAKURA, TranslatorEngine.LOCAL_HY_MT2)
    val available = TranslatorEngine.entries.filter { android.os.Build.VERSION.SDK_INT >= 33 || it !in setOf(TranslatorEngine.LOCAL_SAKURA, TranslatorEngine.LOCAL_HY_MT2) }.toSet()
    LazyColumn(Modifier.fillMaxWidth().fillMaxHeight(.8f), contentPadding = PaddingValues(24.dp, 0.dp, 24.dp, 24.dp)) {
        item { Text(stringResource(R.string.mobile_select_service), style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold) }
        listOf(R.string.mobile_free_online to free, R.string.mobile_api_services to (available - free - offline), R.string.mobile_offline to (offline intersect available)).forEach { (label, engines) ->
            item { Text(stringResource(label), Modifier.padding(top = 24.dp, bottom = 8.dp), style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.primary) }
            items(engines.toList(), key = { it.name }) { engine ->
                ListItem(headlineContent = { Text(providerName(engine)) },
                    trailingContent = { Icon(if (engine == selected) Icons.Outlined.CheckCircle else Icons.AutoMirrored.Outlined.KeyboardArrowRight, null) },
                    modifier = Modifier.clickable { onSelect(engine) })
            }
        }
    }
}

private data class ProviderField(val label: String, val secret: Boolean = false,
    val read: (Settings) -> String, val write: (Settings, String) -> Settings)

@Composable
internal fun ProviderSheet(current: Settings, engine: TranslatorEngine, viewModel: MobileViewModel,
    onDismiss: () -> Unit, onAdvanced: () -> Unit) {
    var draft by remember(engine) { mutableStateOf(current.copy(translatorEngine = engine)) }
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
    ModalBottomSheet(onDismissRequest = onDismiss) {
        LazyColumn(Modifier.fillMaxWidth().heightIn(max = 600.dp).imePadding(), contentPadding = PaddingValues(24.dp, 0.dp, 24.dp, 24.dp), verticalArrangement = Arrangement.spacedBy(16.dp)) {
            item { Text(providerName(engine), style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold) }
            if (fields.isEmpty()) item { Text(stringResource(if (local) R.string.mobile_models_body else R.string.mobile_no_key), color = MaterialTheme.colorScheme.onSurfaceVariant) }
            if (engine == TranslatorEngine.MYMEMORY) item { Text(stringResource(R.string.mobile_explicit_source), style = MaterialTheme.typography.bodyMedium) }
            items(fields) { field ->
                var visible by remember { mutableStateOf(false) }
                OutlinedTextField(field.read(draft), { draft = field.write(draft, it); viewModel.clearConnection() }, Modifier.fillMaxWidth(),
                    label = { Text(field.label) }, isError = field.label == server && !validConfig, singleLine = true, shape = MaterialTheme.shapes.small,
                    visualTransformation = if (field.secret && !visible) PasswordVisualTransformation() else VisualTransformation.None,
                    trailingIcon = if (field.secret) ({ IconButton(onClick = { visible = !visible }) {
                        Icon(if (visible) Icons.Outlined.VisibilityOff else Icons.Outlined.Visibility,
                            stringResource(if (visible) R.string.mobile_hide_key else R.string.mobile_show_key))
                    } }) else null)
            }
            if (engine == TranslatorEngine.DEEPL) item {
                Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                    Text("DeepL API Pro", Modifier.weight(1f)); Switch(draft.deeplPro, { draft = draft.copy(deeplPro = it); viewModel.clearConnection() })
                }
            }
            item { connection?.let { Text(stringResource(if (it.success) R.string.mobile_test_ok else R.string.mobile_error),
                color = if (it.success) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.error) } }
            item { Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                OutlinedButton(onClick = { viewModel.test(draft) }, enabled = !testing && validConfig, modifier = Modifier.weight(1f).heightIn(min = 52.dp)) {
                    if (testing) CircularProgressIndicator(Modifier.size(18.dp), strokeWidth = 2.dp)
                    else Text(stringResource(R.string.mobile_test))
                }
                Button(onClick = {
                    viewModel.resetTranslation()
                    val saved = draft
                    viewModel.update { existing ->
                        fields.fold(existing.copy(translatorEngine = engine)) { s,field -> field.write(s, field.read(saved)) }
                            .let { if (engine == TranslatorEngine.DEEPL) it.copy(deeplPro = saved.deeplPro) else it }
                    }
                    onDismiss()
                }, enabled = validConfig, modifier = Modifier.weight(1f).heightIn(min = 52.dp)) { Text(stringResource(R.string.mobile_save)) }
            } }
            item { TextButton(onClick = onAdvanced, modifier = Modifier.fillMaxWidth()) { Text(stringResource(if (local) R.string.mobile_manage_models else R.string.mobile_advanced)) } }
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
        listOf(ThemeMode.FOLLOW_SYSTEM to R.string.mobile_system, ThemeMode.LIGHT to R.string.mobile_light,
            ThemeMode.DARK to R.string.mobile_dark, ThemeMode.AMOLED to R.string.mobile_amoled,
            ThemeMode.PAPER_DAY to R.string.refine_paper_day, ThemeMode.PAPER_NIGHT to R.string.refine_paper_night,
            ThemeMode.PAPER_NORD to R.string.refine_paper_nord).forEach { (mode, label) ->
            item { ListItem(headlineContent = { Text(stringResource(label)) }, leadingContent = {
                RadioButton(selected = theme.mode == mode, onClick = null)
            }, modifier = Modifier.clickable { theme.setMode(mode) }) }
        }
        item { Text(stringResource(R.string.refine_theme_source), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant) }
        if (theme.mode !in ThemeMode.PAPER_DAY..ThemeMode.PAPER_NORD) {
            item { SectionLabel(R.string.mobile_accent) }
            item { FlowRow(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(16.dp)) {
                ThemeAccent.entries.forEach { choice ->
                    Column(horizontalAlignment = Alignment.CenterHorizontally, modifier = Modifier.clickable { accent.setAccent(choice) }.padding(4.dp)) {
                        Box(Modifier.size(44.dp).background(Color(choice.lightColor), CircleShape), contentAlignment = Alignment.Center) {
                            if (accent.accent == choice) Icon(Icons.Outlined.Check, null, tint = Color.White)
                        }
                        Text(stringResource(choice.label), Modifier.padding(top = 8.dp), fontSize = 10.sp, maxLines = 1)
                    }
                }
            } }
        }
    }
}

private val interfaceLanguages = listOf("en" to "English", "ru" to "Русский", "de" to "Deutsch", "fr" to "Français", "es" to "Español", "zh-CN" to "中文")

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
                Box(Modifier.size(88.dp).background(MaterialTheme.colorScheme.primaryContainer, RoundedCornerShape(28.dp)), contentAlignment = Alignment.Center) {
                    Text("CT", style = MaterialTheme.typography.headlineLarge, fontWeight = FontWeight.Bold, color = MaterialTheme.colorScheme.onPrimaryContainer)
                }
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
