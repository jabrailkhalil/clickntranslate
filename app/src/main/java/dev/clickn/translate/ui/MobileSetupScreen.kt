package dev.clickn.translate.ui

import android.content.Context
import android.content.Intent
import android.widget.Toast
import androidx.activity.compose.BackHandler
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyListState
import androidx.compose.foundation.selection.selectableGroup
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.outlined.ArrowBack
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import dev.clickn.translate.BuildConfig
import dev.clickn.translate.R
import dev.clickn.translate.data.Settings
import dev.clickn.translate.data.AppLocalePrefs
import dev.clickn.translate.data.CompanionPrefs
import dev.clickn.translate.data.TranslatorEngine
import dev.clickn.translate.data.defaultTranslationTarget
import java.util.Locale
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

internal object MobileSetupSteps {
    const val LANGUAGE = 0
    const val THEME = 1
    const val HERO = 2
    const val LANGUAGES = 3
    const val COUNT = 4
}

internal fun openSetupAndroidSettings(context: Context, primary: Intent, fallback: Intent? = null) {
    val opened = runCatching { context.startActivity(primary); true }.getOrDefault(false)
    if (!opened && (fallback == null || runCatching { context.startActivity(fallback); true }.getOrDefault(false).not())) {
        Toast.makeText(context, R.string.setup_settings_unavailable, Toast.LENGTH_LONG).show()
    }
}

@Composable
fun MobileSetupScreen(onFinished: () -> Unit, onAdvanced: (String) -> Unit, firstRun: Boolean = false,
    viewModel: MobileViewModel = hiltViewModel(), openedFromHelp: Boolean = false) {
    val showingHelp = openedFromHelp && !firstRun
    val settings by viewModel.settings.collectAsState()
    val captureModeInitialized by viewModel.captureModeInitialized.collectAsState()
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    var finishing by remember { mutableStateOf(false) }
    var appLanguage by remember { mutableStateOf(AppLocalePrefs.read(context)) }
    var step by rememberSaveable { mutableIntStateOf(MobileSetupSteps.LANGUAGE) }
    val optionsState = rememberSaveable(step, saver = LazyListState.Saver) { LazyListState() }
    val companionChoice by rememberCompanionChoice(context)
    var companionPicture by remember { mutableStateOf<android.graphics.Bitmap?>(null) }
    LaunchedEffect(context, step) {
        if (step == MobileSetupSteps.HERO) {
            companionPicture = withContext(Dispatchers.IO) { BrandIconPrefs.bitmap(context, floating = true) }
        }
    }
    var sheet by rememberSaveable { mutableStateOf("") }
    var pairEdited by rememberSaveable { mutableStateOf(false) }
    var automaticTarget by rememberSaveable { mutableStateOf(
        defaultTranslationTarget(android.content.res.Resources.getSystem().configuration.locales[0])) }
    val finish: () -> Unit = {
        if (!finishing) {
            finishing = true
            scope.launch {
                try {
                    viewModel.ensureCaptureModeInitialized()
                    onFinished()
                } finally { finishing = false }
            }
        }
    }
    Scaffold(
        topBar = { TopAppBar(title = {
            Text(stringResource(if (showingHelp) R.string.mobile_help else R.string.setup_title))
        }, navigationIcon = {
            if (step > MobileSetupSteps.LANGUAGE) IconButton(onClick = { step-- }) {
                Icon(Icons.AutoMirrored.Outlined.ArrowBack, stringResource(R.string.setup_previous))
            }
        }) },
        bottomBar = {
            Surface {
                Column(Modifier.fillMaxWidth().navigationBarsPadding().padding(20.dp)) {
                    Button(onClick = {
                        if (step == MobileSetupSteps.HERO) CompanionPrefs.confirmSelection(context)
                        if (step < MobileSetupSteps.LANGUAGES) step++ else finish()
                    }, enabled = !finishing && (step != MobileSetupSteps.LANGUAGES ||
                        setupLanguagePairReady(settings) && captureModeInitialized),
                        modifier = Modifier.fillMaxWidth().heightIn(min = 56.dp).testTag("setup-next")) {
                        Text(stringResource(if (step < MobileSetupSteps.LANGUAGES) R.string.setup_next else R.string.setup_finish))
                    }
                    if (showingHelp) {
                        Text(stringResource(R.string.settings_about_version_format, BuildConfig.VERSION_NAME),
                            modifier = Modifier.align(Alignment.CenterHorizontally).padding(top = 8.dp),
                            style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                }
            }
        },
    ) { padding ->
        Box(Modifier.fillMaxSize().padding(padding), contentAlignment = Alignment.TopCenter) {
            LazyColumn(Modifier.widthIn(max = 640.dp).fillMaxWidth().testTag("setup-options").selectableGroup(),
                state = optionsState,
                contentPadding = PaddingValues(20.dp), verticalArrangement = Arrangement.spacedBy(16.dp)) {
                item {
                    Text(stringResource(R.string.setup_step, step + 1, MobileSetupSteps.COUNT), color = MaterialTheme.colorScheme.primary)
                    Text(stringResource(when (step) {
                        MobileSetupSteps.LANGUAGE -> R.string.mobile_interface_language
                        MobileSetupSteps.THEME -> R.string.polish_choose_theme
                        MobileSetupSteps.HERO -> R.string.setup_hero_title
                        else -> R.string.setup_translation
                    }),
                        Modifier.padding(top = 12.dp), style = MaterialTheme.typography.headlineMedium)
                    Text(stringResource(when (step) {
                        MobileSetupSteps.LANGUAGE -> R.string.setup_choose_language_body
                        MobileSetupSteps.THEME -> R.string.setup_simple_appearance
                        MobileSetupSteps.HERO -> R.string.setup_hero_body
                        else -> R.string.setup_simple_languages
                    }),
                        Modifier.padding(top = 8.dp), color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
                if (step == MobileSetupSteps.LANGUAGE) {
                    item { SetupLanguageChoices(appLanguage) { tag ->
                        appLanguage = tag
                        AppLocalePrefs.write(context, tag)
                        val locale = if (tag.isBlank()) android.content.res.Resources.getSystem().configuration.locales[0]
                            else Locale.forLanguageTag(tag)
                        val previousTarget = automaticTarget
                        automaticTarget = defaultTranslationTarget(locale)
                        viewModel.update { setupInterfaceLanguageSettings(it, locale, firstRun, pairEdited, previousTarget) }
                    } }
                } else if (step == MobileSetupSteps.THEME) {
                    item { BrandLogo(Modifier.size(56.dp)) }
                    themeChoices.chunked(2).forEach { choices -> item { ThemeChoiceRow(choices) } }
                } else if (step == MobileSetupSteps.HERO) {
                    companionChoices(companionChoice, companionPicture) { CompanionPrefs.write(context, it) }
                } else {
                    settings?.let { current ->
                        item { LanguagePair(current, { sheet = "source" }, { sheet = "target" }, {
                            if (current.sourceLang != "auto") {
                                pairEdited = true
                                viewModel.selectTranslation { it.copy(sourceLang = current.targetLang, targetLang = current.sourceLang) }
                            }
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
            "source", "target" -> {
                val source = sheet == "source"
                val current = settings ?: Settings()
                LanguageSheet(source, if (source) current.sourceLang else current.targetLang,
                    allowAuto = current.translatorEngine !in setOf(TranslatorEngine.MYMEMORY, TranslatorEngine.GOOGLE_ML_KIT),
                    mlKitOnly = current.translatorEngine == TranslatorEngine.GOOGLE_ML_KIT) { code ->
                    pairEdited = true
                    viewModel.selectTranslation { mobileLanguagePair(it, source, code) }
                    sheet = ""
                }
            }
        }
    }
    BackHandler(step > MobileSetupSteps.LANGUAGE && sheet.isEmpty()) { step-- }
}

/** A new installation translates into the chosen interface language until the pair is edited. */
internal fun setupInterfaceLanguageSettings(current: Settings, locale: Locale,
    firstRun: Boolean, pairEdited: Boolean, previousAutomaticTarget: String): Settings =
    if (firstRun && !pairEdited && current.sourceLang == "auto" && current.targetLang == previousAutomaticTarget)
        current.copy(targetLang = defaultTranslationTarget(locale))
    else current

internal fun setupLanguagePairReady(settings: Settings?): Boolean = settings != null &&
    settings.targetLang.isNotBlank() && settings.targetLang != "auto" &&
    (settings.translatorEngine !in setOf(TranslatorEngine.MYMEMORY, TranslatorEngine.GOOGLE_ML_KIT) ||
        settings.sourceLang.isNotBlank() && settings.sourceLang != "auto")
