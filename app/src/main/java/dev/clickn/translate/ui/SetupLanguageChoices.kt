package dev.clickn.translate.ui

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.selection.selectable
import androidx.compose.foundation.selection.selectableGroup
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.unit.dp
import dev.clickn.translate.R

@Composable
internal fun SetupLanguageChoices(selectedTag: String, onSelected: (String) -> Unit) {
    val choices = listOf("" to stringResource(R.string.mobile_follow_system)) + interfaceLanguages
    Column(Modifier.fillMaxWidth().selectableGroup(), verticalArrangement = Arrangement.spacedBy(4.dp)) {
        choices.forEach { (tag, label) ->
            val tagId = tag.ifBlank { "system" }
            val selected = selectedTag == tag
            Surface(shape = MaterialTheme.shapes.medium,
                color = if (selected) MaterialTheme.colorScheme.secondaryContainer else MaterialTheme.colorScheme.surface) {
                Row(
                    Modifier.fillMaxWidth().heightIn(min = 48.dp)
                        .testTag("setup-language-$tagId")
                        .selectable(selected = selected, role = Role.RadioButton, onClick = { onSelected(tag) })
                        .padding(horizontal = 12.dp, vertical = 4.dp),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(12.dp),
                ) {
                    RadioButton(selected = selected, onClick = null)
                    Text(label, style = MaterialTheme.typography.bodyLarge)
                }
            }
        }
    }
}
