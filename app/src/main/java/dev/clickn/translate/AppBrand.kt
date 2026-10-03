// Modified for Click'n'Translate on October 3, 2026.
package dev.clickn.translate

/** Product identity shared by Android entry points, sharing, and release checks. */
object AppBrand {
    const val DISPLAY_NAME = "Click'n'Translate"
    const val WEBSITE_URL = "https://clickn.dev"
    const val SOURCE_CODE_URL = "https://github.com/jabrailkhalil/clickntranslate/tree/android"
    const val COMMUNITY_URL = "https://t.me/jabrail_digital"

    val mobileReleaseApiUrl: String get() = BuildConfig.MOBILE_RELEASE_API_URL
    val updatesEnabled: Boolean get() = mobileReleaseApiUrl.isNotBlank()
}
