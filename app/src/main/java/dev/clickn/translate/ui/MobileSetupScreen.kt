package dev.clickn.translate.ui

import android.content.Context
import android.content.Intent
import android.widget.Toast
import androidx.activity.compose.BackHandler
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
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import dev.clickn.translate.R
import dev.clickn.translate.capture.CaptureStartMode
import dev.clickn.translate.capture.CaptureStartPreference
import dev.clickn.translate.data.Settings
import dev.clickn.translate.data.TranslatorEngine

internal fun openSetupAndroidSettings(context: Context, primary: Intent, fallback: Intent? = null) {
    val opened = runCatching { context.startActivity(primary); true }.getOrDefault(false)
    if (!opened && (fallback == null || runCatching { context.startActivity(fallback); true }.getOrDefault(false).not())) {
        Toast.makeText(context, R.string.setup_settings_unavailable, Toast.LENGTH_LONG).show()
    }
}

@Composable
fun MobileSetupScreen(onFinished: () -> Unit, onAdvanced: (String) -> Unit, viewModel: MobileViewModel = hiltViewModel()) {
    val settings by viewModel.settings.collectAsState()
    var step by rememberSaveable { mutableIntStateOf(0) }
    var sheet by rememberSaveable { mutableStateOf("") }
    val finish = {
        if (CaptureStartPreference.mode.value == null) CaptureStartPreference.select(CaptureStartMode.SYSTEM)
        onFinished()
    }
    Scaffold(
        topBar = { TopAppBar(title = { Text(stringResource(R.string.setup_title)) }, navigationIcon = {
            if (step > 0) IconButton(onClick = { step-- }) {
                Icon(Icons.AutoMirrored.Outlined.ArrowBack, stringResource(R.string.setup_previous))
            }
        }) },
        bottomBar = {
            Surface {
                Column(Modifier.fillMaxWidth().navigationBarsPadding().padding(20.dp)) {
                    Button(onClick = { if (step == 0) step++ else finish() },
                        enabled = step == 0 || setupLanguagePairReady(settings),
                        modifier = Modifier.fillMaxWidth().heightIn(min = 56.dp)) {
                        Text(stringResource(if (step == 0) R.string.setup_next else R.string.setup_finish))
                    }
                }
            }
        },
    ) { padding ->
        Box(Modifier.fillMaxSize().padding(padding), contentAlignment = Alignment.TopCenter) {
            LazyColumn(Modifier.widthIn(max = 640.dp).fillMaxWidth().testTag("setup-options"),
                contentPadding = PaddingValues(20.dp), verticalArrangement = Arrangement.spacedBy(16.dp)) {
                item {
                    Text(stringResource(R.string.setup_step, step + 1, 2), color = MaterialTheme.colorScheme.primary)
                    Text(stringResource(if (step == 0) R.string.polish_choose_theme else R.string.setup_translation),
                        Modifier.padding(top = 12.dp), style = MaterialTheme.typography.headlineMedium)
                    Text(stringResource(if (step == 0) R.string.setup_simple_appearance else R.string.setup_simple_languages),
                        Modifier.padding(top = 8.dp), color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
                if (step == 0) {
                    item { BrandLogo(Modifier.size(56.dp)) }
                    themeChoices.chunked(2).forEach { choices -> item { ThemeChoiceRow(choices) } }
                    item { SetupButton(R.string.mobile_interface_language, Icons.Outlined.Language) { sheet = "interface" } }
                } else {
                    settings?.let { current ->
                        item { LanguagePair(current, { sheet = "source" }, { sheet = "target" }, {
                            if (current.sourceLang != "auto") viewModel.update { it.copy(sourceLang = current.targetLang, targetLang = current.sourceLang) }
                        }) }
                        if (!setupLanguagePairReady(current)) item {
                            Text(stringResource(R.string.mobile_explicit_source), color = MaterialTheme.colorScheme.error)
                        }
                    }
                    item {
                        Surface(shape = MaterialTheme.shapes.large, color = MaterialTheme.colorScheme.surfaceContainerLow) {
                            Column(Modifier.padding(20.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                                Text(stringResource(R.string.setup_simple_usage_title), style = MaterialTheme.typography.titleMedium)
                                Text(stringResource(R.string.setup_simple_usage_body), color = MaterialTheme.colorScheme.onSurfaceVariant)
                            }
                        }
                    }
                }
            }
        }
    }
    if (sheet.isNotEmpty()) ModalBottomSheet(onDismissRequest = { sheet = "" }) {
        when (sheet) {
            "interface" -> InterfaceLanguageSheet { sheet = "" }
            "source", "target" -> {
                val source = sheet == "source"
                val current = settings ?: Settings()
                LanguageSheet(source, if (source) current.sourceLang else current.targetLang,
                    allowAuto = current.translatorEngine !in setOf(TranslatorEngine.MYMEMORY, TranslatorEngine.GOOGLE_ML_KIT),
                    allowedCodes = if (current.translatorEngine == TranslatorEngine.GOOGLE_ML_KIT) dev.clickn.translate.translate.MlKitLanguagePolicy.supportedLanguageTags else null) { code ->
                    viewModel.update { mobileLanguagePair(it, source, code) }; sheet = ""
                }
            }
        }
    }
    BackHandler(step > 0 && sheet.isEmpty()) { step-- }
}

internal fun setupLanguagePairReady(settings: Settings?): Boolean = settings != null &&
    settings.targetLang.isNotBlank() && settings.targetLang != "auto" &&
    (settings.translatorEngine !in setOf(TranslatorEngine.MYMEMORY, TranslatorEngine.GOOGLE_ML_KIT) ||
        settings.sourceLang.isNotBlank() && settings.sourceLang != "auto")

@Composable
private fun SetupButton(label: Int, icon: androidx.compose.ui.graphics.vector.ImageVector, onClick: () -> Unit) {
    OutlinedButton(onClick, Modifier.fillMaxWidth().heightIn(min = 56.dp)) {
        Icon(icon, null); Spacer(Modifier.width(12.dp)); Text(stringResource(label))
    }
}
