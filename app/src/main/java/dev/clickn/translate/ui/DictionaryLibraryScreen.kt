// Modified for Click'n'Translate on October 3, 2026.
package dev.clickn.translate.ui

import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.DeleteOutline
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.RadioButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import dev.clickn.translate.R
import dev.clickn.translate.data.DictionaryLookupMode
import dev.clickn.translate.dictionary.DictionaryPackFailureKind
import dev.clickn.translate.dictionary.DictionaryPackId
import dev.clickn.translate.dictionary.DictionaryPackInstallResult
import dev.clickn.translate.dictionary.DictionaryPackStatus
import dev.clickn.translate.dictionary.supportsOnlineDictionaryLookup
import kotlinx.coroutines.Job
import kotlinx.coroutines.launch

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun DictionaryLibraryScreen(
    onBack: () -> Unit,
    viewModel: DictionaryLibraryViewModel = hiltViewModel(),
) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val snackbar = remember { SnackbarHostState() }
    val settings by viewModel.settings.collectAsState()
    val statuses by viewModel.packStatuses.collectAsState()
    val visibleStatuses = remember(statuses) { visibleDictionaryPackStatuses(statuses) }
    var pendingImportName by rememberSaveable { mutableStateOf<String?>(null) }
    var importJob by remember { mutableStateOf<Job?>(null) }
    var importing by remember { mutableStateOf(false) }
    val importLauncher = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri ->
        val id = DictionaryPackId.entries.firstOrNull { it.name == pendingImportName }
        pendingImportName = null
        if (uri != null && id != null) {
            importing = true
            importJob = scope.launch {
                val result = try {
                    viewModel.importPack(uri, id)
                } finally {
                    importing = false
                    importJob = null
                    viewModel.refresh()
                }
                when (result) {
                    is DictionaryPackInstallResult.Success -> snackbar.showSnackbar(
                        context.getString(R.string.dictionary_pack_imported)
                    )
                    is DictionaryPackInstallResult.Failure -> snackbar.showSnackbar(
                        context.getString(dictionaryPackFailureMessageResource(result.kind))
                    )
                }
            }
        }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(stringResource(R.string.dictionary_library_title)) },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = null)
                    }
                },
                actions = {
                    if (importing) {
                        TextButton(onClick = { importJob?.cancel() }) {
                            Text(stringResource(android.R.string.cancel))
                        }
                    }
                },
            )
        },
        snackbarHost = { SnackbarHost(snackbar) },
    ) { padding ->
        LazyColumn(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding),
            contentPadding = PaddingValues(horizontal = 16.dp, vertical = 12.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            item {
                DictionaryModeGroup(
                    mode = settings.dictionaryLookupMode,
                    tapLookupEnabled = settings.dictionaryTapLookupEnabled,
                    onlineAvailable = supportsOnlineDictionaryLookup(settings.translatorEngine),
                    onTapLookupEnabledChange = viewModel::setTapLookupEnabled,
                    onSelect = { mode ->
                        scope.launch {
                            if (!viewModel.selectMode(mode)) {
                                snackbar.showSnackbar(
                                    context.getString(R.string.dictionary_online_unavailable)
                                )
                            }
                        }
                    },
                )
            }
            if (importing) {
                item {
                    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                        LinearProgressIndicator(modifier = Modifier.fillMaxWidth())
                    }
                }
            }
            item {
                DictionaryPackGroup(
                    statuses = visibleStatuses,
                    enabled = !importing,
                    onImport = { status ->
                        pendingImportName = status.spec.id.name
                        importLauncher.launch(
                            // Providers disagree on MIME types for .bin/.db; validate the actual SQLite format.
                            arrayOf("*/*")
                        )
                    },
                    onDelete = { status ->
                        scope.launch {
                            val deleted = viewModel.deletePack(status.spec.id)
                            snackbar.showSnackbar(
                                context.getString(
                                    if (deleted) R.string.dictionary_pack_deleted
                                    else R.string.dictionary_pack_delete_failed
                                )
                            )
                        }
                    },
                )
            }
        }
    }
}

@Composable
private fun DictionaryModeGroup(
    mode: DictionaryLookupMode,
    tapLookupEnabled: Boolean,
    onlineAvailable: Boolean,
    onTapLookupEnabledChange: (Boolean) -> Unit,
    onSelect: (DictionaryLookupMode) -> Unit,
) {
    DictionarySectionCard(title = stringResource(R.string.dictionary_lookup_source)) {
        Column {
            SwitchRow(
                label = stringResource(R.string.dictionary_tap_lookup_enabled),
                checked = tapLookupEnabled,
                helpText = stringResource(R.string.dictionary_tap_lookup_enabled_summary),
                onChange = onTapLookupEnabledChange,
            )
            HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
            DictionaryLookupMode.entries.forEachIndexed { index, option ->
                DictionaryModeRow(
                    option = option,
                    selected = mode == option,
                    onlineAvailable = onlineAvailable,
                    onClick = { onSelect(option) },
                )
                if (index != DictionaryLookupMode.entries.lastIndex) {
                    HorizontalDivider(
                        modifier = Modifier.padding(start = 44.dp),
                        color = MaterialTheme.colorScheme.outlineVariant,
                    )
                }
            }
        }
    }
}

@Composable
private fun DictionaryModeRow(
    option: DictionaryLookupMode,
    selected: Boolean,
    onlineAvailable: Boolean,
    onClick: () -> Unit,
) {
    val isOffline = option == DictionaryLookupMode.OFFLINE
    val supportingText = when {
        isOffline -> R.string.dictionary_mode_offline_summary
        onlineAvailable -> R.string.dictionary_mode_online_summary
        else -> R.string.dictionary_online_unavailable
    }
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .clickable(onClick = onClick)
            .padding(vertical = 8.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        RadioButton(selected = selected, onClick = null)
        Column(
            modifier = Modifier
                .weight(1f)
                .padding(horizontal = 8.dp),
            verticalArrangement = Arrangement.spacedBy(2.dp),
        ) {
            Text(
                text = stringResource(
                    if (isOffline) R.string.dictionary_mode_offline
                    else R.string.dictionary_mode_online
                ),
                style = MaterialTheme.typography.bodyLarge,
                fontWeight = FontWeight.Medium,
            )
            Text(
                text = stringResource(supportingText),
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                maxLines = 2,
                overflow = TextOverflow.Ellipsis,
            )
        }
    }
}

/** Hide unfinished language entries only in the library UI; installed packs remain intact. */
internal fun visibleDictionaryPackStatuses(statuses: List<DictionaryPackStatus>): List<DictionaryPackStatus> =
    statuses.filter { it.spec.id == DictionaryPackId.ECDICT }

@Composable
private fun DictionaryPackGroup(
    statuses: List<DictionaryPackStatus>,
    enabled: Boolean,
    onImport: (DictionaryPackStatus) -> Unit,
    onDelete: (DictionaryPackStatus) -> Unit,
) {
    DictionarySectionCard(title = stringResource(R.string.dictionary_offline_packs)) {
        Column {
            if (statuses.isEmpty()) {
                Text(
                    text = stringResource(R.string.dictionary_pack_checking),
                    modifier = Modifier.padding(vertical = 8.dp),
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            } else {
                statuses.forEachIndexed { index, status ->
                    DictionaryPackRow(
                        status = status,
                        enabled = enabled,
                        onImport = { onImport(status) },
                        onDelete = { onDelete(status) },
                    )
                    if (index != statuses.lastIndex) {
                        HorizontalDivider(
                            modifier = Modifier.padding(start = 52.dp),
                            color = MaterialTheme.colorScheme.outlineVariant,
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun DictionaryPackRow(
    status: DictionaryPackStatus,
    enabled: Boolean,
    onImport: () -> Unit,
    onDelete: () -> Unit,
) {
    val statusText = when {
        status.invalidReason != null || status.invalidKind != null -> stringResource(
            dictionaryPackFailureMessageResource(status.invalidKind ?: DictionaryPackFailureKind.UNKNOWN)
        )
        status.installed -> stringResource(R.string.dictionary_pack_installed)
        else -> stringResource(R.string.dictionary_pack_not_installed)
    }.orEmpty()
    val badge = when (status.spec.id) {
        DictionaryPackId.ECDICT -> "EN"
        DictionaryPackId.JMDICT -> "日"
        DictionaryPackId.KOREAN_BASIC -> "한"
    }

    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 8.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Surface(
            modifier = Modifier.size(40.dp),
            shape = CircleShape,
            color = MaterialTheme.colorScheme.secondaryContainer,
            contentColor = MaterialTheme.colorScheme.onSecondaryContainer,
        ) {
            Box(contentAlignment = Alignment.Center) {
                Text(
                    text = badge,
                    style = MaterialTheme.typography.labelLarge,
                    fontWeight = FontWeight.SemiBold,
                )
            }
        }
        Column(
            modifier = Modifier
                .weight(1f)
                .padding(start = 12.dp, end = 4.dp),
            verticalArrangement = Arrangement.spacedBy(2.dp),
        ) {
            Text(
                text = status.spec.displayName,
                style = MaterialTheme.typography.bodyLarge,
                fontWeight = FontWeight.Medium,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
            Text(
                text = statusText,
                style = MaterialTheme.typography.bodySmall,
                color = when {
                    status.invalidReason != null || status.invalidKind != null -> MaterialTheme.colorScheme.error
                    status.installed -> MaterialTheme.colorScheme.primary
                    else -> MaterialTheme.colorScheme.onSurfaceVariant
                },
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
        }
        if (status.installed || status.invalidReason != null || status.invalidKind != null) {
            IconButton(onClick = onDelete, enabled = enabled) {
                Icon(
                    imageVector = Icons.Default.DeleteOutline,
                    contentDescription = stringResource(R.string.dictionary_pack_delete),
                    tint = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
        TextButton(onClick = onImport, enabled = enabled) {
            Text(
                text = stringResource(
                    if (status.installed) R.string.dictionary_pack_action_replace
                    else R.string.dictionary_pack_action_import
                ),
                maxLines = 1,
            )
        }
    }
}

@Composable
private fun DictionarySectionCard(
    title: String,
    content: @Composable () -> Unit,
) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surface,
            contentColor = MaterialTheme.colorScheme.onSurface,
        ),
        elevation = CardDefaults.cardElevation(defaultElevation = 0.dp),
        border = BorderStroke(1.dp, MaterialTheme.colorScheme.outlineVariant),
    ) {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            Text(
                text = title,
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.SemiBold,
                color = MaterialTheme.colorScheme.onSurface,
            )
            content()
        }
    }
}
