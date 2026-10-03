package dev.clickn.translate.ui

import android.content.ComponentName
import android.content.Context
import android.content.pm.PackageManager
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.net.Uri
import androidx.compose.foundation.Image
import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import dev.clickn.translate.R
import java.io.File

internal object BrandIconPrefs {
    const val LOGO = "logo"
    private const val MAX_BYTES = 10 * 1024 * 1024
    val choices = listOf(LOGO, "ocean", "mint", "sunset")
    fun read(context: Context): String = context.getSharedPreferences("clickn_brand_icon", Context.MODE_PRIVATE)
        .getString("choice", LOGO)?.takeIf { it in choices } ?: LOGO
    fun migrate(context: Context) {
        val previous = context.getSharedPreferences("clickn_brand_icon", Context.MODE_PRIVATE).getString("choice", LOGO)
        val desired = read(context)
        val component = ComponentName(context.packageName, "dev.clickn.translate.${componentName(desired)}")
        if (previous !in choices || context.packageManager.getComponentEnabledSetting(component) != PackageManager.COMPONENT_ENABLED_STATE_ENABLED) {
            write(context, desired)
        }
    }
    fun componentName(choice: String): String = when (choice) {
        "ocean" -> "LauncherOcean"
        "mint" -> "LauncherMint"
        "sunset" -> "LauncherSunset"
        else -> "LauncherLogo"
    }
    fun write(context: Context, choice: String) {
        require(choice in choices)
        val active = componentName(choice)
        val components = choices.map(::componentName) + "LauncherMascot"
        // Enable the next entry first so launchers never lose every app entry.
        (listOf(active) + components.filterNot { it == active }).forEach { name ->
            context.packageManager.setComponentEnabledSetting(
                ComponentName(context.packageName, "dev.clickn.translate.$name"),
                if (name == active) PackageManager.COMPONENT_ENABLED_STATE_ENABLED else PackageManager.COMPONENT_ENABLED_STATE_DISABLED,
                PackageManager.DONT_KILL_APP,
            )
        }
        context.getSharedPreferences("clickn_brand_icon", Context.MODE_PRIVATE).edit().putString("choice", choice).apply()
    }
    private fun pictureFile(context: Context, floating: Boolean) =
        File(context.filesDir, if (floating) "clickn_floating_picture.png" else "clickn_custom_icon.png")
    fun bitmap(context: Context, floating: Boolean = false): Bitmap? =
        runCatching { BitmapFactory.decodeFile(pictureFile(context, floating).path) }.getOrNull()
    fun importPicture(context: Context, uri: Uri, floating: Boolean = false): Bitmap {
        require(uri.scheme == "content") { "Choose an image through the Android picker" }
        val bytes = context.contentResolver.openInputStream(uri)?.use { input ->
            val out = java.io.ByteArrayOutputStream()
            val buffer = ByteArray(8192)
            while (true) {
                val read = input.read(buffer)
                if (read < 0) break
                require(out.size() + read <= MAX_BYTES) { "Image too large" }
                out.write(buffer, 0, read)
            }
            out.toByteArray()
        } ?: throw IllegalArgumentException("Image unavailable")
        val bounds = BitmapFactory.Options().apply { inJustDecodeBounds = true }
        BitmapFactory.decodeByteArray(bytes, 0, bytes.size, bounds)
        require(bounds.outWidth > 0 && bounds.outHeight > 0) { "Invalid image" }
        var sample = 1
        while (maxOf(bounds.outWidth, bounds.outHeight) / sample > 1024) sample *= 2
        val decoded = BitmapFactory.decodeByteArray(bytes, 0, bytes.size, BitmapFactory.Options().apply { inSampleSize = sample })
            ?: throw IllegalArgumentException("Invalid image")
        val scale = minOf(1f, 512f / maxOf(decoded.width, decoded.height))
        val image = Bitmap.createScaledBitmap(decoded, maxOf(1, (decoded.width * scale).toInt()), maxOf(1, (decoded.height * scale).toInt()), true)
        if (image !== decoded) decoded.recycle()
        val atomic = android.util.AtomicFile(pictureFile(context, floating))
        val output = atomic.startWrite()
        try {
            check(image.compress(Bitmap.CompressFormat.PNG, 100, output))
            atomic.finishWrite(output)
        } catch (error: Throwable) { atomic.failWrite(output); throw error }
        return image
    }

}

internal fun brandLogoResource(choice: String): Int = when (choice) {
    "ocean" -> R.drawable.ic_clickn_ocean
    "mint" -> R.drawable.ic_clickn_mint
    "sunset" -> R.drawable.ic_clickn_sunset
    else -> R.drawable.ic_clickn_logo
}

@Composable
internal fun BrandLogo(modifier: Modifier = Modifier, choice: String = BrandIconPrefs.LOGO) {
    Image(painterResource(brandLogoResource(choice)), null, modifier, contentScale = ContentScale.Fit)
}

@Composable
internal fun BrandIconSheet(onChanged: () -> Unit) {
    val context = LocalContext.current
    var choice by remember { mutableStateOf(BrandIconPrefs.read(context)) }
    Column(Modifier.fillMaxWidth().padding(24.dp), verticalArrangement = Arrangement.spacedBy(16.dp)) {
        Text(stringResource(R.string.refine_icon), style = MaterialTheme.typography.headlineSmall)
        Text(stringResource(R.string.logo_choices_body), color = MaterialTheme.colorScheme.onSurfaceVariant)
        listOf(BrandIconPrefs.LOGO to R.string.logo_original, "ocean" to R.string.logo_ocean,
            "mint" to R.string.logo_mint, "sunset" to R.string.logo_sunset).chunked(2).forEach { options ->
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                options.forEach { (option, label) ->
                    Surface(onClick = { BrandIconPrefs.write(context, option); choice = option; onChanged() },
                        modifier = Modifier.weight(1f), shape = MaterialTheme.shapes.large,
                        border = androidx.compose.foundation.BorderStroke(if (choice == option) 2.dp else 1.dp,
                            if (choice == option) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.outlineVariant),
                        color = MaterialTheme.colorScheme.surfaceContainerLow) {
                        Column(Modifier.padding(16.dp), horizontalAlignment = Alignment.CenterHorizontally,
                            verticalArrangement = Arrangement.spacedBy(8.dp)) {
                            BrandLogo(Modifier.size(64.dp), option)
                            Text(stringResource(label))
                            RadioButton(choice == option, onClick = null)
                        }
                    }
                }
            }
        }
    }
}
