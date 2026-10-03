buildscript {
    repositories { google(); mavenCentral() }
    dependencies {
        if (project.hasProperty("uiSnapshots")) {
            classpath("app.cash.paparazzi:paparazzi-gradle-plugin:1.3.5")
        }
    }
}

plugins {
    alias(libs.plugins.android.application) apply false
    alias(libs.plugins.android.library) apply false
    alias(libs.plugins.kotlin.android) apply false
    alias(libs.plugins.kotlin.compose) apply false
    alias(libs.plugins.kotlin.serialization) apply false
    alias(libs.plugins.hilt) apply false
    alias(libs.plugins.ksp) apply false
}
