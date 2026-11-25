package dev.clickn.translate.ui

import android.content.Context
import android.graphics.Bitmap
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyListScope
import androidx.compose.foundation.selection.selectable
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.RadioButton
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.State
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.unit.dp
import dev.clickn.translate.R
import dev.clickn.translate.data.AppCompanion
import dev.clickn.translate.data.CompanionPrefs

internal fun companionChoiceOptions(selected: String, hasCustomPicture: Boolean): List<Pair<String, Int>> =
    AppCompanion.entries.map { it.id to it.label } +
        listOf(CompanionPrefs.ACTION to R.string.polish_action_icon, CompanionPrefs.LOGO to R.string.refine_brand_logo) +
        if (hasCustomPicture || selected == CompanionPrefs.CUSTOM)
            listOf(CompanionPrefs.CUSTOM to R.string.polish_custom_picture) else emptyList()

/** The same lazy, full-width picture/name selection is used by setup and appearance settings. */
internal fun LazyListScope.companionChoices(selected: String, picture: Bitmap?, onSelected: (String) -> Unit) {
    companionChoiceOptions(selected, picture != null).forEach { (id, label) ->
        item(key = "companion-$id") {
            val chosen = selected == id
            Surface(
                shape = MaterialTheme.shapes.large,
                color = if (chosen) MaterialTheme.colorScheme.secondaryContainer else MaterialTheme.colorScheme.surface,
                border = BorderStroke(if (chosen) 2.dp else 1.dp,
                    if (chosen) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.outlineVariant),
            ) {
                BoxWithConstraints(Modifier.fillMaxWidth()) {
                    val stacked = maxWidth < 360.dp || LocalDensity.current.fontScale >= 1.5f
                    val choiceModifier = Modifier.fillMaxWidth().heightIn(min = 88.dp).testTag("companion-$id")
                        .selectable(chosen, role = Role.RadioButton, onClick = { onSelected(id) })
                        .padding(12.dp)
                    if (stacked) {
                        Column(choiceModifier, verticalArrangement = Arrangement.spacedBy(8.dp)) {
                            Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically,
                                horizontalArrangement = Arrangement.SpaceBetween) {
                                FloatingPicture(id, picture, Modifier.size(56.dp))
                                RadioButton(chosen, onClick = null)
                            }
                            CompanionChoiceLabel(id, label, picture == null, Modifier.fillMaxWidth())
                        }
                    } else {
                        Row(choiceModifier, verticalAlignment = Alignment.CenterVertically,
                            horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                            FloatingPicture(id, picture, Modifier.size(56.dp))
                            CompanionChoiceLabel(id, label, picture == null, Modifier.weight(1f))
                            RadioButton(chosen, onClick = null)
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun CompanionChoiceLabel(id: String, label: Int, missingPicture: Boolean, modifier: Modifier) {
    Column(modifier, verticalArrangement = Arrangement.spacedBy(4.dp)) {
        Text(stringResource(label), Modifier.fillMaxWidth().testTag("companion-name-$id"),
            style = MaterialTheme.typography.bodyLarge)
        if (id == CompanionPrefs.CUSTOM && missingPicture) {
            Text(stringResource(R.string.setup_hero_custom_unavailable), Modifier.fillMaxWidth(),
                style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }
}

@Composable
internal fun rememberCompanionChoice(context: Context = LocalContext.current): State<String> {
    val choice = remember(context) { mutableStateOf(CompanionPrefs.read(context)) }
    DisposableEffect(context) {
        val stop = CompanionPrefs.observe(context) { choice.value = CompanionPrefs.read(context) }
        choice.value = CompanionPrefs.read(context)
        onDispose(stop)
    }
    return choice
}
