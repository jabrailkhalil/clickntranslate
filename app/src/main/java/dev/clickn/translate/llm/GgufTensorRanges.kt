package dev.clickn.translate.llm

import android.os.Build
import androidx.annotation.Keep
import java.io.File

/** Checks a GGUF index during an explicit transfer without starting an inference engine. */
@Keep
internal object GgufTensorRanges {
    fun validate(file: File): String? {
        if (!LocalLlmDeviceCapability.supportsSdk(Build.VERSION.SDK_INT)) return null
        return try {
            System.loadLibrary("ai-chat")
            if (completeNative(file.absolutePath)) null else "incomplete or invalid GGUF tensor data"
        } catch (_: LinkageError) {
            "GGUF tensor validation unavailable"
        }
    }

    private external fun completeNative(path: String): Boolean
}
