// Modified for Click'n'Translate on October 3, 2026.
package dev.clickn.translate.overlay

import dev.clickn.translate.data.TranslationBlockInteractionMode

internal data class TranslationBlockInteractionPlan(
    val enableNativeTextSelection: Boolean,
    val enableSelectedTextSpeech: Boolean,
    val openCopyPanelOnBlockTap: Boolean,
    val windowFocusable: Boolean,
    val useDecorViewActionModeHost: Boolean,
)

internal fun translationBlockInteractionPlan(
    mode: TranslationBlockInteractionMode,
): TranslationBlockInteractionPlan = when (mode) {
    TranslationBlockInteractionMode.COPY_BUTTON -> TranslationBlockInteractionPlan(
        enableNativeTextSelection = true,
        enableSelectedTextSpeech = true,
        openCopyPanelOnBlockTap = false,
        windowFocusable = true,
        useDecorViewActionModeHost = true,
    )

    TranslationBlockInteractionMode.OPEN_COPY_PANEL -> TranslationBlockInteractionPlan(
        enableNativeTextSelection = false,
        enableSelectedTextSpeech = false,
        openCopyPanelOnBlockTap = true,
        windowFocusable = false,
        useDecorViewActionModeHost = false,
    )
}

internal fun isTranslationBlockTextActionable(text: String?): Boolean =
    !text.isNullOrBlank() && text != "..." && text != "…"

internal fun canSelectFloatingWindowText(locked: Boolean, text: String?): Boolean =
    !locked && isTranslationBlockTextActionable(text)

internal fun floatingWindowNeedsKeyFocus(
    locked: Boolean,
    selectionActive: Boolean,
): Boolean = !locked && selectionActive
