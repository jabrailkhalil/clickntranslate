package dev.clickn.translate.ui

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import dev.clickn.translate.R

@Composable
internal fun GlossaryModesPane(terms: Boolean, memory: Boolean, preservation: Boolean,
    termCount: Int, memoryCount: Int, preservationCount: Int,
    onTermsEnabled: (Boolean) -> Unit, onMemoryEnabled: (Boolean) -> Unit,
    onPreservationEnabled: (Boolean) -> Unit,
    onTerms: () -> Unit, onMemory: () -> Unit, onPreservation: () -> Unit,
) {
    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Text(stringResource(R.string.library_modes_intro), style = MaterialTheme.typography.bodyLarge,
            color = MaterialTheme.colorScheme.onSurfaceVariant)
        GlossaryModeCard(R.string.translation_library_terms_tab, R.string.library_terms_body, terms,
            onTermsEnabled, onTerms, termCount)
        GlossaryModeCard(R.string.translation_library_memory_tab, R.string.library_memory_body, memory,
            onMemoryEnabled, onMemory, memoryCount)
        GlossaryModeCard(R.string.source_preservation_tab, R.string.library_preservation_body, preservation,
            onPreservationEnabled, onPreservation, preservationCount)
    }
}

@Composable
internal fun GlossaryModeCard(title: Int, body: Int, enabled: Boolean, onEnabled: (Boolean) -> Unit,
    onOpen: (() -> Unit)?, count: Int = 0,
) {
    Surface(shape = MaterialTheme.shapes.large, color = MaterialTheme.colorScheme.surfaceContainerLow) {
        Column(Modifier.fillMaxWidth().padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            SwitchRow(stringResource(title), enabled, onChange = onEnabled)
            Text(stringResource(body), color = MaterialTheme.colorScheme.onSurfaceVariant,
                style = MaterialTheme.typography.bodyMedium)
            if (onOpen != null) TextButton(onClick = onOpen) {
                Text(stringResource(R.string.library_manage_count, count))
            }
        }
    }
}
