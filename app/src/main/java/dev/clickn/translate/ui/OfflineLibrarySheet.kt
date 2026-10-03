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
import dev.clickn.translate.llm.LlmModelKind
import dev.clickn.translate.translate.MlKitLanguagePolicy
import java.util.Locale

@Composable
internal fun OfflineLibrarySheet(settings: Settings, viewModel: MobileViewModel, onAdvanced: (String) -> Unit) {
    val models by viewModel.modelState.collectAsState()
    val busy by viewModel.offlineBusy.collectAsState()
    val error by viewModel.offlineError.collectAsState()
    val initial = mobileMlKitPair(settings)
    var source by remember { mutableStateOf(initial.sourceLang) }
    var target by remember { mutableStateOf(initial.targetLang) }
    val pair = initial.copy(sourceLang = source, targetLang = target)
    val languages = remember { MlKitLanguagePolicy.supportedLanguageTags.sortedBy { Locale.forLanguageTag(it).displayLanguage } }
    val downloaded = models.downloadedLanguages + "en"
    LazyColumn(Modifier.fillMaxWidth(), contentPadding = PaddingValues(24.dp, 0.dp, 24.dp, 32.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        item { Text(stringResource(R.string.refine_offline), style = MaterialTheme.typography.headlineSmall) }
        item { Text(stringResource(R.string.refine_models_body), style = MaterialTheme.typography.bodyMedium) }
        item { Text(stringResource(R.string.refine_light_engine), style = MaterialTheme.typography.titleMedium) }
        item { Text("Google ML Kit", style = MaterialTheme.typography.titleSmall); Text(stringResource(R.string.refine_mlkit_size), style = MaterialTheme.typography.bodySmall) }
        item { LanguagePair(pair, {}, {}, {}) }
        item { Button(onClick = { viewModel.downloadOfflinePair(pair) }, enabled = !busy, modifier = Modifier.fillMaxWidth()) { Text(stringResource(R.string.refine_download_pair)) } }
        if (busy) item {
            Text(stringResource(R.string.refine_downloading)); LinearProgressIndicator(Modifier.fillMaxWidth())
            TextButton(onClick = viewModel::cancelOfflineDownload) { Text(stringResource(R.string.mobile_cancel)) }
        }
        if (error) item { Text(stringResource(R.string.refine_download_failed), color = MaterialTheme.colorScheme.error) }
        item { Text(stringResource(R.string.mobile_target), style = MaterialTheme.typography.titleSmall) }
        item { FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            languages.forEach { code ->
                val normalized = runCatching { MlKitLanguagePolicy.resolveTarget(code) }.getOrNull()
                if (normalized != source) SettingChoiceChip(target == code, { target = code }, label = { Text(Locale.forLanguageTag(code).getDisplayLanguage(Locale.getDefault())) })
            }
        } }
        item { Text(stringResource(R.string.refine_language_packs), style = MaterialTheme.typography.titleSmall) }
        items(languages.filter { runCatching { MlKitLanguagePolicy.resolveTarget(it) }.getOrNull() != target }, key = { it }) { code ->
            val canonical = runCatching { MlKitLanguagePolicy.resolveTarget(code) }.getOrDefault(code)
            ListItem(headlineContent = { Text(Locale.forLanguageTag(code).getDisplayLanguage(Locale.getDefault())) },
                supportingContent = { Text(stringResource(if (canonical in downloaded) R.string.refine_downloaded else R.string.refine_not_downloaded)) },
                leadingContent = { RadioButton(source == canonical, onClick = null) },
                trailingContent = { if (canonical in downloaded) Icon(Icons.Outlined.CheckCircle, null) },
                modifier = Modifier.clickable { source = canonical })
        }
        item { HorizontalDivider(); Text(stringResource(R.string.refine_large_engines), style = MaterialTheme.typography.titleMedium) }
        listOf(TranslatorEngine.LOCAL_HY_MT2 to LlmModelKind.HY_MT2_1_8B_Q4_K_M, TranslatorEngine.LOCAL_SAKURA to LlmModelKind.SAKURA_1_5B_Q4).forEach { (engine, kind) ->
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
        item { HorizontalDivider(); Text(stringResource(R.string.refine_offline_ocr), style = MaterialTheme.typography.titleMedium) }
        item { Text(stringResource(R.string.refine_offline_ocr_body)) }
        item { TextButton(onClick = { onAdvanced("ocr") }) { Text(stringResource(R.string.setup_ocr)) } }
    }
}
