package dev.clickn.translate.ui

import android.graphics.Bitmap
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.Image
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.selection.selectable
import androidx.compose.foundation.selection.selectableGroup
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.TouchApp
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.Dp
import dev.clickn.translate.R
import dev.clickn.translate.data.*
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import kotlin.math.roundToInt

@Composable
internal fun FloatingAppearanceSheet(settings: Settings, onUpdate: ((Settings) -> Settings) -> Unit,
    onAdvanced: () -> Unit) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    var choice by remember { mutableStateOf(CompanionPrefs.read(context)) }
    var picture by remember { mutableStateOf<Bitmap?>(null) }
    var size by remember(settings.floatingButtonSizeDp) { mutableFloatStateOf(settings.floatingButtonSizeDp.toFloat().coerceIn(32f, 96f)) }
    var opacity by remember(settings.floatingButtonAlpha) { mutableFloatStateOf(normalizedFloatingButtonAlpha(settings.floatingButtonAlpha)) }
    var busy by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf(false) }
    LaunchedEffect(Unit) { picture = withContext(Dispatchers.IO) { BrandIconPrefs.bitmap(context, floating = true) } }
    val picker = rememberLauncherForActivityResult(ActivityResultContracts.GetContent()) { uri ->
        if (uri != null) scope.launch {
            busy = true; error = false
            try {
                picture = withContext(Dispatchers.IO) { BrandIconPrefs.importPicture(context, uri, floating = true) }
                CompanionPrefs.write(context, CompanionPrefs.CUSTOM)
                choice = CompanionPrefs.CUSTOM
            } catch (cancelled: kotlinx.coroutines.CancellationException) { throw cancelled }
            catch (_: Exception) { error = true }
            finally { busy = false }
        }
    }
    androidx.compose.foundation.lazy.LazyColumn(
        Modifier.fillMaxWidth().testTag("floating-appearance"),
        contentPadding = PaddingValues(24.dp, 0.dp, 24.dp, 32.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp),
    ) {
        item {
            Text(stringResource(R.string.refine_floating), style = MaterialTheme.typography.headlineSmall)
            Text(stringResource(R.string.polish_floating_body), Modifier.padding(top = 8.dp),
                color = MaterialTheme.colorScheme.onSurfaceVariant, style = MaterialTheme.typography.bodyMedium)
        }
        item {
            Surface(shape = MaterialTheme.shapes.large, color = MaterialTheme.colorScheme.surfaceContainerHigh) {
                Box(Modifier.fillMaxWidth().height(120.dp), contentAlignment = Alignment.Center) {
                    FloatingPicture(choice, picture, Modifier.size(size.dp).alpha(opacity), actionPadding = (size * .18f).dp)
                }
            }
        }
        val options = listOf(CompanionPrefs.ACTION to R.string.polish_action_icon, CompanionPrefs.LOGO to R.string.refine_brand_logo) +
            AppCompanion.entries.map { it.id to it.label } +
            if (picture != null) listOf(CompanionPrefs.CUSTOM to R.string.polish_custom_picture) else emptyList()
        options.chunked(3).forEach { row ->
            item {
                Row(Modifier.fillMaxWidth().height(IntrinsicSize.Min).selectableGroup(), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                    row.forEach { (id, label) ->
                        Surface(
                            modifier = Modifier.weight(1f).fillMaxHeight().testTag("companion-$id")
                                .selectable(choice == id, role = Role.RadioButton, onClick = {
                                    CompanionPrefs.write(context, id); choice = id
                                }),
                            shape = MaterialTheme.shapes.medium,
                            border = BorderStroke(if (choice == id) 2.dp else 1.dp,
                                if (choice == id) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.outlineVariant),
                        ) {
                            Column(Modifier.padding(10.dp), horizontalAlignment = Alignment.CenterHorizontally) {
                                FloatingPicture(id, picture, Modifier.size(56.dp))
                                Text(stringResource(label), Modifier.padding(top = 8.dp), style = MaterialTheme.typography.labelLarge)
                            }
                        }
                    }
                    if (row.size == 1) Spacer(Modifier.weight(1f))
                }
            }
        }
        item {
            OutlinedButton(onClick = { picker.launch("image/*") }, enabled = !busy, modifier = Modifier.fillMaxWidth()) {
                Text(stringResource(R.string.refine_choose_image))
            }
            if (busy) LinearProgressIndicator(Modifier.fillMaxWidth())
            if (error) Text(stringResource(R.string.refine_icon_error), color = MaterialTheme.colorScheme.error)
        }
        item {
            Text(stringResource(R.string.settings_floating_size_format, size.roundToInt()))
            Slider(value = size, onValueChange = { size = it },
                onValueChangeFinished = { val value = size.roundToInt(); onUpdate { it.copy(floatingButtonSizeDp = value) } },
                valueRange = 32f..96f, steps = 15)
            Text(stringResource(R.string.settings_alpha_label_format, (opacity * 100).roundToInt()))
            Slider(value = opacity, onValueChange = { opacity = it },
                onValueChangeFinished = { val value = opacity; onUpdate { it.copy(floatingButtonAlpha = value) } },
                valueRange = .1f..1f)
        }
        item {
            var keepVisible by remember { mutableStateOf(CompanionPrefs.keepVisible(context)) }
            SwitchRow(stringResource(R.string.floating_keep_visible), keepVisible,
                helpText = stringResource(R.string.floating_keep_visible_body)) {
                keepVisible = it; CompanionPrefs.setKeepVisible(context, it)
            }
        }
        item { OutlinedButton(onClick = onAdvanced, modifier = Modifier.fillMaxWidth()) {
            Text(stringResource(R.string.polish_button_actions))
        } }
    }
}

@Composable
internal fun FloatingPicture(choice: String, bitmap: Bitmap?, modifier: Modifier = Modifier, actionPadding: Dp = 12.dp) {
    val companion = AppCompanion.entries.firstOrNull { it.id == choice }
    when {
        choice == CompanionPrefs.CUSTOM && bitmap != null -> Image(bitmap.asImageBitmap(), null, modifier, contentScale = ContentScale.Fit)
        choice == CompanionPrefs.LOGO -> BrandLogo(modifier)
        companion != null -> Image(painterResource(companion.image), null, modifier, contentScale = ContentScale.Fit)
        else -> Icon(Icons.Outlined.TouchApp, null, modifier.padding(actionPadding), tint = MaterialTheme.colorScheme.primary)
    }
}
