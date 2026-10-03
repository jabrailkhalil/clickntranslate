// Modified for Click'n'Translate on October 3, 2026.
package dev.clickn.translate.translate

/** Apps whose editors cannot currently be read and replaced safely through Accessibility. */
object InputTranslationAppPolicy {
    private val blockedPackages = setOf(
        "com.tencent.mm",
    )

    fun isBlocked(packageName: String?): Boolean =
        packageName != null && packageName in blockedPackages
}
