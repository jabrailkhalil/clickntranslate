package dev.clickn.translate.ui

import android.os.Build
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.CheckCircle
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import dev.clickn.translate.R
import dev.clickn.translate.data.Settings
import dev.clickn.translate.data.TranslatorEngine
import dev.clickn.translate.data.chineseToolsRelevant
import androidx.compose.ui.platform.LocalContext
import androidx.compose.runtime.saveable.rememberSaveable
import dev.clickn.translate.llm.LlmModelKind
import dev.clickn.translate.translate.MlKitLanguagePolicy
import java.util.Locale

@Composable
internal fun OfflineLibrarySheet(settings: Settings, viewModel: MobileViewModel, onAdvanced: (String) -> Unit) {
    val models by viewModel.modelState.collectAsState()
    val locale = LocalContext.current.resources.configuration.locales[0]
    var showSpecialized by rememberSaveable { mutableStateOf(false) }
    var languagePicker by rememberSaveable { mutableStateOf("") }
    val busy by viewModel.offlineBusy.collectAsState()
    val error by viewModel.offlineError.collectAsState()
    val initial = mobileMlKitPair(settings)
    var source by remember { mutableStateOf(initial.sourceLang) }
    var target by remember { mutableStateOf(initial.targetLang) }
    val pair = initial.copy(sourceLang = source, targetLang = target)
    val languages = remember(locale) { MlKitLanguagePolicy.supportedLanguageTags.map { MlKitLanguagePolicy.resolveTarget(it) }.distinct().sortedBy { Locale.forLanguageTag(it).getDisplayLanguage(locale) } }
    val downloaded = models.downloadedLanguages + "en"
    LazyColumn(Modifier.fillMaxWidth(), contentPadding = PaddingValues(24.dp, 0.dp, 24.dp, 32.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        item { Text(stringResource(R.string.refine_offline), style = MaterialTheme.typography.headlineSmall) }
        item { Text(stringResource(R.string.refine_models_body), style = MaterialTheme.typography.bodyMedium) }
        item { Text(stringResource(R.string.refine_light_engine), style = MaterialTheme.typography.titleMedium) }
        item { Text("Google ML Kit", style = MaterialTheme.typography.titleSmall); Text(stringResource(R.string.refine_mlkit_size), style = MaterialTheme.typography.bodySmall) }
        item { LanguagePair(pair, { languagePicker = "source" }, { languagePicker = "target" }, {
            val oldSource = source; source = target; target = oldSource
        }) }
        item { Button(onClick = { viewModel.downloadOfflinePair(pair) }, enabled = !busy, modifier = Modifier.fillMaxWidth()) { Text(stringResource(R.string.refine_download_pair)) } }
        if (busy) item {
            Text(stringResource(R.string.refine_downloading)); LinearProgressIndicator(Modifier.fillMaxWidth())
            TextButton(onClick = viewModel::cancelOfflineDownload) { Text(stringResource(R.string.mobile_cancel)) }
        }
        if (error) item { Text(stringResource(R.string.refine_download_failed), color = MaterialTheme.colorScheme.error) }
        item { Text(stringResource(R.string.refine_language_packs), style = MaterialTheme.typography.titleSmall) }
        items(languages.filter { runCatching { MlKitLanguagePolicy.resolveTarget(it) }.getOrNull() != target }, key = { it }) { code ->
            val canonical = runCatching { MlKitLanguagePolicy.resolveTarget(code) }.getOrDefault(code)
            ListItem(headlineContent = { Text(Locale.forLanguageTag(code).getDisplayLanguage(locale)) },
                supportingContent = { Text(stringResource(if (canonical in downloaded) R.string.refine_downloaded else R.string.refine_not_downloaded)) },
                leadingContent = { RadioButton(source == canonical, onClick = null) },
                trailingContent = { if (canonical in downloaded) Icon(Icons.Outlined.CheckCircle, null) },
                modifier = Modifier.clickable { source = canonical })
        }
        item { HorizontalDivider(); Text(stringResource(R.string.refine_large_engines), style = MaterialTheme.typography.titleMedium) }
        val largeEngines = listOf(TranslatorEngine.LOCAL_HY_MT2 to LlmModelKind.HY_MT2_1_8B_Q4_K_M,
            TranslatorEngine.LOCAL_SAKURA to LlmModelKind.SAKURA_1_5B_Q4)
        largeEngines.filter { (engine, _) -> engine != TranslatorEngine.LOCAL_SAKURA ||
            showSpecialized || chineseToolsRelevant(settings.targetLang, locale) ||
            settings.translatorEngine == TranslatorEngine.LOCAL_SAKURA }.forEach { (engine, kind) ->
            item {
                Text(kind.displayName, style = MaterialTheme.typography.titleSmall)
                Text(stringResource(if (engine == TranslatorEngine.LOCAL_HY_MT2) R.string.refine_hymt_size else R.string.refine_sakura_size))
                if (Build.VERSION.SDK_INT < 33) Text(stringResource(R.string.refine_android13))
                OutlinedButton(onClick = {
                    viewModel.update { if (engine == TranslatorEngine.LOCAL_SAKURA) it.copy(translatorEngine = engine, sourceLang = "ja", targetLang = "zh-CN") else it.copy(translatorEngine = engine) }
                    onAdvanced("translate")
                }, enabled = Build.VERSION.SDK_INT >= 33) { Text(stringResource(R.string.mobile_manage_models)) }
            }
        }
        if (!showSpecialized && !chineseToolsRelevant(settings.targetLang, locale) && settings.translatorEngine != TranslatorEngine.LOCAL_SAKURA) item {
            TextButton(onClick = { showSpecialized = true }) { Text(stringResource(R.string.polish_specialized_models)) }
        }
        item { HorizontalDivider(); Text(stringResource(R.string.refine_offline_ocr), style = MaterialTheme.typography.titleMedium) }
        item { Text(stringResource(R.string.refine_offline_ocr_body)) }
        item { TextButton(onClick = { onAdvanced("ocr") }) { Text(stringResource(R.string.setup_ocr)) } }
    }
    if (languagePicker.isNotEmpty()) ModalBottomSheet(onDismissRequest = { languagePicker = "" }) {
        val isSource = languagePicker == "source"
        val selected = if (isSource) source else target
        LanguageSheet(isSource, if (selected == "zh") "zh-CN" else selected, allowAuto = false,
            allowedCodes = MlKitLanguagePolicy.supportedLanguageTags) { code ->
            val canonical = MlKitLanguagePolicy.resolveTarget(code)
            if (isSource) {
                if (canonical == target) target = source
                source = canonical
            } else {
                if (canonical == source) source = target
                target = canonical
            }
            languagePicker = ""
        }
    }
}
