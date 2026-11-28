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
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import dev.clickn.translate.R
import dev.clickn.translate.data.Settings
import dev.clickn.translate.data.TranslatorEngine
import dev.clickn.translate.data.chineseToolsRelevant
import dev.clickn.translate.data.languageDisplayName
import dev.clickn.translate.download.ModelDownloadType
import dev.clickn.translate.download.ModelDownloadWorkPolicy
import dev.clickn.translate.download.ModelDownloadWorker
import androidx.work.WorkInfo
import androidx.compose.ui.platform.LocalContext
import androidx.compose.runtime.saveable.rememberSaveable
import dev.clickn.translate.llm.LlmModelKind
import dev.clickn.translate.translate.MlKitLanguagePolicy
import java.util.Locale
import kotlinx.coroutines.launch

@Composable
internal fun OfflineLibrarySheet(settings: Settings, viewModel: MobileViewModel, onAdvanced: (String) -> Unit) {
    val models by viewModel.modelState.collectAsState()
    val locale = LocalContext.current.resources.configuration.locales[0]
    val scope = rememberCoroutineScope()
    var openingLocalModel by remember { mutableStateOf(false) }
    var showSpecialized by rememberSaveable { mutableStateOf(false) }
    var languagePicker by rememberSaveable { mutableStateOf("") }
    val busy by viewModel.offlineBusy.collectAsState()
    val error by viewModel.offlineError.collectAsState()
    val tesseract by viewModel.tesseractModelState.collectAsState()
    val workSnapshot by viewModel.modelDownloadWorkInfos.collectAsState(initial = null)
    val queued = workSnapshot.orEmpty()
    val pairWork = remember(queued) {
        queued.filterNot { it.state.isFinished }.mapNotNull { work ->
            val pairs = ModelDownloadWorkPolicy.specsFromTags(work.tags)
                .filter { it.type == ModelDownloadType.ML_KIT_TRANSLATION }.map { it.mlKitLanguages() }
            if (pairs.isEmpty()) null else work to pairs
        }
    }
    val tesseractSpec = dev.clickn.translate.download.ModelDownloadSpec.tesseractArabic()
    val tesseractWork = queued.filter { !it.state.isFinished &&
        dev.clickn.translate.download.ModelDownloadWorkPolicy.specTag(tesseractSpec) in it.tags }
    val arabicSpec = dev.clickn.translate.download.ModelDownloadSpec.paddle(dev.clickn.translate.data.PaddleModelVersion.V5_ARABIC)
    val arabicWork = queued.filter { !it.state.isFinished &&
        dev.clickn.translate.download.ModelDownloadWorkPolicy.specTag(arabicSpec) in it.tags }
    val arabicFailure = queued.any { it.state == androidx.work.WorkInfo.State.FAILED &&
        dev.clickn.translate.download.ModelDownloadWorkPolicy.specTag(arabicSpec) in it.tags }
    val initial = mobileMlKitPair(settings)
    var source by rememberSaveable { mutableStateOf(initial.sourceLang) }
    var target by rememberSaveable { mutableStateOf(initial.targetLang) }
    val pair = initial.copy(sourceLang = source, targetLang = target)
    val languages = remember(locale) { MlKitLanguagePolicy.supportedLanguageTags.map { MlKitLanguagePolicy.resolveTarget(it) }.distinct().sortedBy { Locale.forLanguageTag(it).getDisplayLanguage(locale) } }
    val downloaded = models.downloadedLanguages + "en"
    val pairInstalled = MlKitLanguagePolicy.requiredDownloadLanguages(source, target).all { it in downloaded }
    val installedLanguages = languages.filter { it in downloaded }
    LazyColumn(Modifier.fillMaxWidth().testTag("offline-library"), contentPadding = PaddingValues(24.dp, 0.dp, 24.dp, 32.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        item { Text(stringResource(R.string.refine_offline), style = MaterialTheme.typography.headlineSmall) }
        item { Text(stringResource(R.string.refine_models_body), style = MaterialTheme.typography.bodyMedium) }
        item { Text(stringResource(R.string.refine_light_engine), style = MaterialTheme.typography.titleMedium) }
        item { Text("Google ML Kit", style = MaterialTheme.typography.titleSmall); Text(stringResource(R.string.refine_mlkit_size), style = MaterialTheme.typography.bodySmall) }
        item { LanguagePair(pair, { languagePicker = "source" }, { languagePicker = "target" }, {
            val oldSource = source; source = target; target = oldSource
        }) }
        item { Button(onClick = { viewModel.downloadOfflinePair(pair) }, enabled = workSnapshot != null && !busy && pairWork.isEmpty(),
            modifier = Modifier.fillMaxWidth().testTag("offline-pair-apply")) {
            Text(stringResource(if (pairInstalled) R.string.offline_use_installed_pair else R.string.refine_download_pair))
        } }
        if (busy && pairWork.isEmpty()) item {
            Text(stringResource(R.string.model_download_waiting)); LinearProgressIndicator(Modifier.fillMaxWidth())
            TextButton(onClick = viewModel::cancelOfflineDownload) { Text(stringResource(R.string.mobile_cancel)) }
        }
        items(pairWork, key = { "translation:${it.first.id}" }) { (work, languages) ->
            val pairs = languages.joinToString { (from, to) ->
                "${languageDisplayName(from, locale)} → ${languageDisplayName(to, locale)}"
            }
            val status = work.progress.getString(ModelDownloadWorker.KEY_STATUS).orEmpty().ifBlank {
                stringResource(if (work.state == WorkInfo.State.RUNNING) R.string.refine_downloading else R.string.gallery_status_queued)
            }
            Box(Modifier.testTag("translation-download-${work.id}")) {
                ModelDownloadProgressCard(
                    requestKey = work.id.toString(), status = "$pairs\n$status",
                    downloaded = work.progress.getLong(ModelDownloadWorker.KEY_DOWNLOADED, 0),
                    total = work.progress.getLong(ModelDownloadWorker.KEY_TOTAL, -1),
                    active = work.state == WorkInfo.State.RUNNING && work.progress.getBoolean(ModelDownloadWorker.KEY_ACTIVE, true),
                    onCancel = { viewModel.cancelOfflineDownload(work) },
                )
            }
        }
        if (error && !busy && pairWork.isEmpty()) item { Text(stringResource(R.string.refine_download_failed), color = MaterialTheme.colorScheme.error) }
        item { HorizontalDivider(); Text(stringResource(R.string.refine_offline_ocr), style = MaterialTheme.typography.titleMedium) }
        item { Text(stringResource(R.string.refine_offline_ocr_body)) }
        item { Text(stringResource(R.string.mobile_arabic_ocr), style = MaterialTheme.typography.titleMedium) }
        item { Text(stringResource(R.string.mobile_arabic_ocr_body)) }
        item {
            if (arabicWork.isNotEmpty()) {
                LinearProgressIndicator(Modifier.fillMaxWidth())
                Text(stringResource(R.string.refine_downloading))
                TextButton(onClick = viewModel::cancelArabicOcrDownload) { Text(stringResource(R.string.mobile_cancel)) }
            } else {
                if (models.arabicOcrReady) Text(stringResource(R.string.refine_downloaded))
                if (arabicFailure && !models.arabicOcrReady) Text(stringResource(R.string.refine_download_failed), color = MaterialTheme.colorScheme.error)
                Button(onClick = viewModel::enableArabicOcr, modifier = Modifier.fillMaxWidth()) {
                    Text(stringResource(if (models.arabicOcrReady) R.string.mobile_arabic_ocr_use else R.string.mobile_arabic_ocr_download))
                }
            }
        }
        arabicWork.forEach { work -> item(key = "arabic-paddle:${work.id}") {
            Text(work.progress.getString(dev.clickn.translate.download.ModelDownloadWorker.KEY_STATUS).orEmpty(), style = MaterialTheme.typography.bodySmall)
        } }
        item { TesseractModelSection(tesseract.copy(busy = tesseract.busy || tesseractWork.isNotEmpty()),
            onDownload = { viewModel.downloadTesseractModels() }, onCancel = viewModel::cancelTesseractModels,
            onDelete = { viewModel.deleteTesseractModels() }) }
        tesseractWork.forEach { work -> item(key = "tesseract:${work.id}") {
            Text(work.progress.getString(dev.clickn.translate.download.ModelDownloadWorker.KEY_STATUS).orEmpty(),
                style = MaterialTheme.typography.bodySmall)
        } }
        item { TextButton(onClick = { onAdvanced("ocr") }) { Text(stringResource(R.string.setup_ocr)) } }
        item { HorizontalDivider(); Text(stringResource(R.string.offline_installed_translation_languages, installedLanguages.size), style = MaterialTheme.typography.titleSmall) }
        item { Text(stringResource(R.string.offline_installed_translation_help), style = MaterialTheme.typography.bodySmall) }
        items(installedLanguages, key = { it }) { code ->
            ListItem(headlineContent = { Text(Locale.forLanguageTag(code).getDisplayLanguage(locale)) },
                supportingContent = { Text(stringResource(if (code == "en") R.string.offline_builtin_english else R.string.refine_downloaded)) },
                leadingContent = { RadioButton(source == code, onClick = null) },
                trailingContent = { Icon(Icons.Outlined.CheckCircle, null) },
                modifier = Modifier.clickable {
                    if (code == target) target = source
                    source = code
                })
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
                    openingLocalModel = true
                    scope.launch {
                        try {
                            // Advanced settings reads once on entry; commit the selected engine first.
                            viewModel.selectTranslation {
                                if (engine == TranslatorEngine.LOCAL_SAKURA) {
                                    it.copy(translatorEngine = engine, sourceLang = "ja", targetLang = "zh-CN")
                                } else it.copy(translatorEngine = engine)
                            }.join()
                            onAdvanced("translate")
                        } finally { openingLocalModel = false }
                    }
                }, enabled = Build.VERSION.SDK_INT >= 33 && !openingLocalModel) { Text(stringResource(R.string.mobile_manage_models)) }
            }
        }
        if (!showSpecialized && !chineseToolsRelevant(settings.targetLang, locale) && settings.translatorEngine != TranslatorEngine.LOCAL_SAKURA) item {
            TextButton(onClick = { showSpecialized = true }) { Text(stringResource(R.string.polish_specialized_models)) }
        }
    }
    if (languagePicker.isNotEmpty()) ModalBottomSheet(onDismissRequest = { languagePicker = "" }) {
        val isSource = languagePicker == "source"
        val selected = if (isSource) source else target
        LanguageSheet(isSource, selected, allowAuto = false, mlKitOnly = true) { code ->
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
