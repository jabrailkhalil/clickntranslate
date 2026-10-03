package dev.clickn.translate.ui

import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.content.pm.ShortcutInfo
import android.content.pm.ShortcutManager
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.Canvas
import android.graphics.drawable.Icon as AndroidIcon
import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.Image
import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import dev.clickn.translate.R
import java.io.File
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

internal object BrandIconPrefs {
    const val LOGO = "logo"
    const val MASCOT = "mascot"
    const val CUSTOM = "custom"
    private const val MAX_BYTES = 10 * 1024 * 1024
    fun read(context: Context): String = context.getSharedPreferences("clickn_brand_icon", Context.MODE_PRIVATE)
        .getString("choice", LOGO)?.takeIf { it in setOf(LOGO, MASCOT, CUSTOM) } ?: LOGO
    fun write(context: Context, choice: String) {
        require(choice in setOf(LOGO, MASCOT, CUSTOM))
        val active = if (choice == MASCOT) "LauncherMascot" else "LauncherLogo"
        val inactive = if (choice == MASCOT) "LauncherLogo" else "LauncherMascot"
        fun component(name: String) = ComponentName(context.packageName, "dev.clickn.translate.$name")
        context.packageManager.setComponentEnabledSetting(component(active), PackageManager.COMPONENT_ENABLED_STATE_ENABLED, PackageManager.DONT_KILL_APP)
        context.packageManager.setComponentEnabledSetting(component(inactive), PackageManager.COMPONENT_ENABLED_STATE_DISABLED, PackageManager.DONT_KILL_APP)
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
    fun pinShortcut(context: Context, bitmap: Bitmap): Boolean {
        val manager = context.getSystemService(ShortcutManager::class.java) ?: return false
        if (!manager.isRequestPinShortcutSupported) return false
        val square = Bitmap.createBitmap(512, 512, Bitmap.Config.ARGB_8888)
        val canvas = Canvas(square)
        val scale = minOf(512f / bitmap.width, 512f / bitmap.height)
        val width = bitmap.width * scale; val height = bitmap.height * scale
        canvas.drawBitmap(bitmap, null, android.graphics.RectF((512 - width) / 2, (512 - height) / 2, (512 + width) / 2, (512 + height) / 2), android.graphics.Paint(android.graphics.Paint.ANTI_ALIAS_FLAG))
        val info = ShortcutInfo.Builder(context, "clickn-custom-icon")
            .setShortLabel(context.getString(R.string.app_name))
            .setIcon(AndroidIcon.createWithAdaptiveBitmap(square))
            .setIntent(Intent(context, MainActivity::class.java).setAction(Intent.ACTION_MAIN))
            .build()
        return manager.requestPinShortcut(info, null)
    }
}

@Composable
internal fun BrandLogo(modifier: Modifier = Modifier, choice: String = BrandIconPrefs.LOGO, bitmap: Bitmap? = null) {
    when {
        choice == BrandIconPrefs.CUSTOM && bitmap != null -> Image(bitmap.asImageBitmap(), null, modifier, contentScale = ContentScale.Fit)
        choice == BrandIconPrefs.MASCOT -> Image(painterResource(R.drawable.companion_doc), null, modifier, contentScale = ContentScale.Fit)
        else -> Icon(painterResource(R.drawable.ic_clickn_logo), null, modifier, tint = Color.Unspecified)
    }
}

@Composable
internal fun BrandIconSheet(onChanged: () -> Unit) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    var choice by remember { mutableStateOf(BrandIconPrefs.read(context)) }
    var picture by remember { mutableStateOf<Bitmap?>(null) }
    var busy by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf(false) }
    LaunchedEffect(choice) { picture = withContext(Dispatchers.IO) { BrandIconPrefs.bitmap(context) } }
    val picker = rememberLauncherForActivityResult(ActivityResultContracts.GetContent()) { uri ->
        if (uri != null) scope.launch {
            busy = true; error = false
            try {
                picture = withContext(Dispatchers.IO) { BrandIconPrefs.importPicture(context, uri) }
                BrandIconPrefs.write(context, BrandIconPrefs.CUSTOM)
                choice = BrandIconPrefs.CUSTOM; onChanged()
            } catch (cancelled: kotlinx.coroutines.CancellationException) { throw cancelled }
            catch (_: Exception) { error = true }
            finally { busy = false }
        }
    }
    Column(Modifier.fillMaxWidth().padding(24.dp), verticalArrangement = Arrangement.spacedBy(16.dp)) {
        Text(stringResource(R.string.refine_icon), style = MaterialTheme.typography.headlineSmall)
        listOf(BrandIconPrefs.LOGO to R.string.refine_brand_logo, BrandIconPrefs.MASCOT to R.string.refine_brand_mascot).forEach { (option, label) ->
            Surface(onClick = { BrandIconPrefs.write(context, option); choice = option; onChanged() }, shape = MaterialTheme.shapes.medium, color = MaterialTheme.colorScheme.surfaceContainerLow) {
                Row(Modifier.fillMaxWidth().padding(20.dp), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(16.dp)) {
                    BrandLogo(Modifier.size(56.dp), option)
                    Text(stringResource(label), Modifier.weight(1f))
                    RadioButton(choice == option, onClick = null)
                }
            }
        }
        Text(stringResource(R.string.refine_custom_icon_body), style = MaterialTheme.typography.bodyMedium)
        OutlinedButton(onClick = { picker.launch("image/*") }, enabled = !busy, modifier = Modifier.fillMaxWidth()) { Text(stringResource(R.string.refine_choose_image)) }
        if (busy) LinearProgressIndicator(Modifier.fillMaxWidth())
        picture?.let { image ->
            BrandLogo(Modifier.size(96.dp).align(Alignment.CenterHorizontally), BrandIconPrefs.CUSTOM, image)
            Button(onClick = { error = !BrandIconPrefs.pinShortcut(context, image) }, modifier = Modifier.fillMaxWidth()) { Text(stringResource(R.string.refine_add_shortcut)) }
        }
        if (error) Text(stringResource(R.string.refine_icon_error), color = MaterialTheme.colorScheme.error)
    }
}
