package dev.clickn.translate.data

internal data class OverlayThemePalette(
    val background: Int, val foreground: Int, val muted: Int, val accent: Int,
)

/** Nearly opaque backgrounds keep built-in overlay text readable over other applications. */
internal fun builtInOverlayPalette(theme: OverlayTheme): OverlayThemePalette? = when (theme) {
    OverlayTheme.CLASSIC_DARK -> OverlayThemePalette(0xF2000000.toInt(), 0xFFFFFFFF.toInt(), 0xFFBEC9CF.toInt(), 0xFF90CAF9.toInt())
    OverlayTheme.AMBER_GOLD -> OverlayThemePalette(0xF8241608.toInt(), 0xFFFFD27F.toInt(), 0xFFCFAD79.toInt(), 0xFFE3B65B.toInt())
    OverlayTheme.PAPER_LIGHT -> OverlayThemePalette(0xFCF5EFE0.toInt(), 0xFF3E2A1F.toInt(), 0xFF614938.toInt(), 0xFF604426.toInt())
    OverlayTheme.FROST_GLASS -> OverlayThemePalette(0xF51E293B.toInt(), 0xFFE0F2FE.toInt(), 0xFFCBD5E1.toInt(), 0xFF93C5FD.toInt())
    OverlayTheme.CUSTOM -> null
}
