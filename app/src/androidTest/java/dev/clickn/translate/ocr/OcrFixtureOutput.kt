package dev.clickn.translate.ocr

import android.content.Context
import androidx.test.platform.app.InstrumentationRegistry
import java.io.File

/** Secondary users can export their own synthetic results over USB from the app's private directory. */
internal fun Context.ocrFixtureOutput(name: String): File {
    val privateOutput = InstrumentationRegistry.getArguments().getString("privateEvidence") == "true"
    val directory = if (privateOutput) File(filesDir, "qa-ocr/$name") else requireNotNull(getExternalFilesDir(name))
    check(directory.isDirectory || directory.mkdirs()) { "Could not create OCR fixture directory" }
    return directory
}
