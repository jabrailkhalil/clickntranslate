plugins {
    alias(libs.plugins.android.application)
}

android {
    namespace = "dev.clickn.qa.page"
    compileSdk = 35

    defaultConfig {
        applicationId = "dev.clickn.qa.page"
        minSdk = 29
        targetSdk = 35
        versionCode = 1
        versionName = "1.0"
    }
}
