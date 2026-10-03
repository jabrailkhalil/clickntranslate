package dev.clickn.translate.ui

import android.Manifest
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.provider.Settings as AndroidSettings
import android.widget.Toast
import androidx.activity.compose.BackHandler
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.outlined.ArrowBack
import androidx.compose.material.icons.outlined.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.lifecycle.compose.LocalLifecycleOwner
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import dev.clickn.translate.R
import dev.clickn.translate.capture.CaptureStartMode
import dev.clickn.translate.capture.CaptureStartPreference
import dev.clickn.translate.data.Settings
import dev.clickn.translate.data.TranslatorEngine
import dev.clickn.translate.trigger.AccessibilityServiceStatus
import dev.clickn.translate.trigger.ClickTranslateAccessibilityService

internal fun openSetupAndroidSettings(context: Context, primary: Intent, fallback: Intent? = null) {
    val opened = runCatching { context.startActivity(primary); true }.getOrDefault(false)
    if (!opened && (fallback == null || runCatching { context.startActivity(fallback); true }.getOrDefault(false).not())) {
        Toast.makeText(context, R.string.setup_settings_unavailable, Toast.LENGTH_LONG).show()
    }
}

@Composable
fun MobileSetupScreen(onFinished: () -> Unit, onAdvanced: (String) -> Unit, viewModel: MobileViewModel = hiltViewModel()) {
    val context = LocalContext.current
    val settings by viewModel.settings.collectAsState()
    var step by rememberSaveable { mutableIntStateOf(0) }
    var sheet by rememberSaveable { mutableStateOf("") }
    var selectedProvider by remember { mutableStateOf<TranslatorEngine?>(null) }
    var overlay by remember { mutableStateOf(AndroidSettings.canDrawOverlays(context)) }
    var notifications by remember { mutableStateOf(hasSetupNotificationPermission(context)) }
    var accessibility by remember { mutableStateOf(AccessibilityServiceStatus.isEnabled(context)) }
    val lifecycle = LocalLifecycleOwner.current.lifecycle
    DisposableEffect(lifecycle) {
        val observer = LifecycleEventObserver { _, event ->
            if (event == Lifecycle.Event.ON_RESUME) {
                overlay = AndroidSettings.canDrawOverlays(context)
                notifications = hasSetupNotificationPermission(context)
                accessibility = AccessibilityServiceStatus.isEnabled(context)
            }
        }
        lifecycle.addObserver(observer)
        onDispose { lifecycle.removeObserver(observer) }
    }
    var notificationRequested by rememberSaveable { mutableStateOf(false) }
    val notificationRequest = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { notifications = it }
    val stepTitles = listOf(R.string.setup_title, R.string.setup_translation, R.string.setup_overlay,
        R.string.setup_capture, R.string.setup_recognition, R.string.setup_background, R.string.setup_ready)
    val stepBodies = listOf(R.string.setup_intro, R.string.setup_translation_body, R.string.setup_overlay_body,
        R.string.setup_capture_body, R.string.setup_recognition_body, R.string.setup_background_body, R.string.setup_ready_body)
    Scaffold(
        topBar = { TopAppBar(title = { Text(stringResource(R.string.setup_title)) }, navigationIcon = {
            if (step > 0) IconButton(onClick = { step-- }) { Icon(Icons.AutoMirrored.Outlined.ArrowBack, stringResource(R.string.setup_previous)) }
        }) },
        bottomBar = {
            Surface {
                Column(Modifier.fillMaxWidth().navigationBarsPadding().padding(24.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                    Button(onClick = {
                        if (step == 3 && CaptureStartPreference.mode.value == null) CaptureStartPreference.select(CaptureStartMode.SYSTEM)
                        if (step < stepTitles.lastIndex) step++ else onFinished()
                    }, enabled = setupCanContinue(step, overlay) && (step != 1 || setupLanguagePairReady(settings)), modifier = Modifier.fillMaxWidth().heightIn(min = 56.dp)) {
                        Text(stringResource(if (step == stepTitles.lastIndex) R.string.setup_finish else R.string.setup_next))
                    }
                    if (step == 2 && !overlay) TextButton(onClick = onFinished, modifier = Modifier.fillMaxWidth()) {
                        Text(stringResource(R.string.setup_text_only))
                    }
                }
            }
        },
    ) { padding ->
        Box(Modifier.fillMaxSize().padding(padding), contentAlignment = Alignment.TopCenter) {
            LazyColumn(Modifier.widthIn(max = 640.dp).fillMaxWidth().testTag("setup-options"), contentPadding = PaddingValues(24.dp), verticalArrangement = Arrangement.spacedBy(20.dp)) {
                item {
                    Text(stringResource(R.string.setup_step, step + 1, stepTitles.size), color = MaterialTheme.colorScheme.primary, style = MaterialTheme.typography.labelLarge)
                    LinearProgressIndicator(progress = { (step + 1f) / stepTitles.size }, modifier = Modifier.fillMaxWidth().padding(top = 12.dp))
                    Text(stringResource(stepTitles[step]), Modifier.padding(top = 24.dp), style = MaterialTheme.typography.headlineLarge, fontWeight = FontWeight.Bold)
                    Text(stringResource(stepBodies[step]), Modifier.padding(top = 16.dp), style = MaterialTheme.typography.bodyLarge, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
                when (step) {
                    0 -> {
                        item { BrandLogo(Modifier.size(64.dp)) }
                        item { Button(onClick = onFinished, modifier = Modifier.fillMaxWidth().heightIn(min = 56.dp)) { Text(stringResource(R.string.refine_quick_setup)) } }
                        item { SetupButton(R.string.mobile_interface_language, Icons.Outlined.Language) { sheet = "interface" } }
                        item { SetupButton(R.string.mobile_appearance, Icons.Outlined.Palette) { sheet = "appearance" } }
                    }
                    1 -> settings?.let { current ->
                        item { LanguagePair(current, { sheet = "source" }, { sheet = "target" }, {
                            if (current.sourceLang != "auto") viewModel.update { it.copy(sourceLang = current.targetLang, targetLang = current.sourceLang) }
                        }) }
                        item { ServiceRow(current) { sheet = "services" } }
                        if (!setupLanguagePairReady(current)) item {
                            Text(stringResource(R.string.mobile_explicit_source), color = MaterialTheme.colorScheme.error)
                        }
                    }
                    2 -> {
                        item { PermissionCard(R.string.setup_overlay, R.string.setup_overlay_body, overlay) { openOverlayPermissionSettings(context) } }
                        if (Build.VERSION.SDK_INT >= 33) item {
                            PermissionCard(R.string.setup_notifications, R.string.setup_notifications_body, notifications) {
                                if (!notifications && !notificationRequested) {
                                    notificationRequested = true
                                    notificationRequest.launch(Manifest.permission.POST_NOTIFICATIONS)
                                } else openSetupAndroidSettings(context, Intent(AndroidSettings.ACTION_APP_NOTIFICATION_SETTINGS)
                                    .putExtra(AndroidSettings.EXTRA_APP_PACKAGE, context.packageName))
                            }
                        }
                    }
                    3 -> if (Build.VERSION.SDK_INT >= 30) {
                      item {
                        PermissionCard(R.string.setup_accessibility, R.string.setup_accessibility_body, accessibility) {
                            openSetupAndroidSettings(context,
                                Intent("android.settings.ACCESSIBILITY_DETAILS_SETTINGS")
                                    .putExtra("android.intent.extra.COMPONENT_NAME",
                                        ComponentName(context, ClickTranslateAccessibilityService::class.java)),
                                Intent(AndroidSettings.ACTION_ACCESSIBILITY_SETTINGS))
                        }
                      }
                      if (Build.VERSION.SDK_INT >= 33 && !accessibility) item {
                        SetupButton(R.string.setup_restricted_settings, Icons.Outlined.Info) {
                            openSetupAndroidSettings(context, Intent(AndroidSettings.ACTION_APPLICATION_DETAILS_SETTINGS,
                                Uri.parse("package:${context.packageName}")))
                        }
                      }
                    }
                    4 -> {
                        item { SetupButton(R.string.setup_ocr, Icons.Outlined.DocumentScanner) { onAdvanced("ocr") } }
                        item { SetupButton(R.string.setup_models, Icons.Outlined.Translate) { onAdvanced("translate") } }
                    }
                    5 -> {
                        item { SetupButton(R.string.setup_battery, Icons.Outlined.BatterySaver) {
                            openSetupAndroidSettings(context, Intent(AndroidSettings.ACTION_APPLICATION_DETAILS_SETTINGS,
                                Uri.parse("package:${context.packageName}")), Intent(AndroidSettings.ACTION_IGNORE_BATTERY_OPTIMIZATION_SETTINGS))
                        } }
                        item { SetupButton(R.string.setup_shortcuts, Icons.Outlined.TouchApp) { onAdvanced("floating") } }
                    }
                }
            }
        }
    }
    if (sheet.isNotEmpty()) ModalBottomSheet(onDismissRequest = { sheet = "" }) {
        when (sheet) {
            "interface" -> InterfaceLanguageSheet { sheet = "" }
            "appearance" -> AppearanceSheet()
            "source", "target" -> {
                val source = sheet == "source"
                val current = settings ?: Settings()
                LanguageSheet(source, if (source) current.sourceLang else current.targetLang,
                    allowAuto = current.translatorEngine !in setOf(TranslatorEngine.MYMEMORY, TranslatorEngine.GOOGLE_ML_KIT),
                    allowedCodes = if (current.translatorEngine == TranslatorEngine.GOOGLE_ML_KIT) dev.clickn.translate.translate.MlKitLanguagePolicy.supportedLanguageTags else null) { code ->
                    viewModel.update { mobileLanguagePair(it, source, code) }; sheet = ""
                }
            }
            "services" -> ServicesSheet(settings?.translatorEngine ?: TranslatorEngine.GOOGLE) {
                selectedProvider = it; sheet = ""; viewModel.clearConnection()
            }
        }
    }
    selectedProvider?.let { engine ->
        ProviderSheet(settings ?: Settings(), engine, viewModel,
            onDismiss = { selectedProvider = null; viewModel.clearConnection() },
            onAdvanced = { selectedProvider = null; viewModel.clearConnection(); onAdvanced("translate") })
    }
    BackHandler(step > 0 && sheet.isEmpty() && selectedProvider == null) { step-- }
}

internal fun setupCanContinue(step: Int, overlayGranted: Boolean): Boolean = step != 2 || overlayGranted

internal fun setupLanguagePairReady(settings: Settings?): Boolean = settings != null &&
    settings.targetLang.isNotBlank() && settings.targetLang != "auto" &&
    (settings.translatorEngine !in setOf(TranslatorEngine.MYMEMORY, TranslatorEngine.GOOGLE_ML_KIT) ||
        settings.sourceLang.isNotBlank() && settings.sourceLang != "auto")

private fun hasSetupNotificationPermission(context: Context): Boolean = Build.VERSION.SDK_INT < 33 ||
    ContextCompat.checkSelfPermission(context, Manifest.permission.POST_NOTIFICATIONS) == PackageManager.PERMISSION_GRANTED

@Composable
private fun SetupButton(label: Int, icon: androidx.compose.ui.graphics.vector.ImageVector, onClick: () -> Unit) {
    OutlinedButton(onClick, Modifier.fillMaxWidth().heightIn(min = 56.dp)) {
        Icon(icon, null); Spacer(Modifier.width(12.dp)); Text(stringResource(label))
    }
}

@Composable
private fun PermissionCard(title: Int, body: Int, granted: Boolean, onOpen: () -> Unit) {
    Surface(shape = MaterialTheme.shapes.medium, color = MaterialTheme.colorScheme.surfaceContainerLow) {
        Column(Modifier.fillMaxWidth().padding(24.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Icon(if (granted) Icons.Outlined.CheckCircle else Icons.Outlined.SettingsSuggest, null, tint = MaterialTheme.colorScheme.primary)
                Text(stringResource(if (granted) R.string.setup_enabled else R.string.setup_pending), Modifier.padding(start = 10.dp), style = MaterialTheme.typography.labelLarge)
            }
            Text(stringResource(title), fontWeight = FontWeight.Bold)
            Text(stringResource(body), style = MaterialTheme.typography.bodyMedium)
            TextButton(onClick = onOpen, modifier = Modifier.align(Alignment.End)) { Text(stringResource(R.string.setup_open)) }
        }
    }
}
