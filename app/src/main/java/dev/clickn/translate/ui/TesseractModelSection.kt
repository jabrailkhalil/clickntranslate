package dev.clickn.translate.ui

import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import dev.clickn.translate.R
import dev.clickn.translate.ocr.TesseractModelFailure
import dev.clickn.translate.ocr.TesseractModelState

/** The existing OCR/model settings surface; no download runs merely by mounting this section. */
@Composable internal fun TesseractModelSection(state: TesseractModelState, onDownload: () -> Unit,
    onCancel: () -> Unit, onDelete: () -> Unit) {
    Column(Modifier.fillMaxWidth(), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Text(stringResource(R.string.settings_ocr_chip_tesseract_arabic), style = MaterialTheme.typography.titleSmall)
        Text(stringResource(R.string.settings_tesseract_language_scope), style = MaterialTheme.typography.bodySmall)
        Text(stringResource(if (state.ready) R.string.settings_tesseract_models_ready else R.string.settings_tesseract_models_missing),
            Modifier.testTag("tesseract-model-status"), style = MaterialTheme.typography.bodySmall)
        state.error?.takeUnless { it == TesseractModelFailure.MISSING }?.let { failure -> Text(stringResource(when (failure) {
            TesseractModelFailure.DOWNLOAD -> R.string.settings_tesseract_download_failed
            TesseractModelFailure.INVALID -> R.string.settings_tesseract_models_invalid
            TesseractModelFailure.MISSING -> R.string.settings_tesseract_models_missing
        }), color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall) }
        if (state.busy) {
            val progress = state.progress?.takeIf { it.isFinite() }?.coerceIn(0f, 1f)
            if (progress == null) LinearProgressIndicator(Modifier.fillMaxWidth())
            else LinearProgressIndicator(progress = { progress }, modifier = Modifier.fillMaxWidth())
            TextButton(onClick = onCancel, modifier = Modifier.testTag("tesseract-model-cancel")) {
                Text(stringResource(R.string.settings_tesseract_cancel))
            }
        } else Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            if (!state.ready || state.error != null) OutlinedButton(onClick = onDownload,
                modifier = Modifier.testTag("tesseract-model-download")) {
                Text(stringResource(if (state.error == null || state.error == TesseractModelFailure.MISSING)
                    R.string.settings_tesseract_download else R.string.settings_tesseract_retry))
            }
            if (state.ready) TextButton(onClick = onDelete, modifier = Modifier.testTag("tesseract-model-delete")) {
                Text(stringResource(R.string.settings_tesseract_delete))
            }
        }
    }
}
