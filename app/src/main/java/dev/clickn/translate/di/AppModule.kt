// Modified for Click'n'Translate on October 3, 2026.
package dev.clickn.translate.di

import android.content.Context
import androidx.room.Room
import dev.clickn.translate.BuildConfig
import dev.clickn.translate.data.AndroidKeystoreSettingsSecretCipher
import dev.clickn.translate.data.SettingsSecretCipher
import dev.clickn.translate.glossary.TranslationGlossaryDao
import dev.clickn.translate.glossary.TranslationGlossaryDatabase
import dev.clickn.translate.gallery.GalleryTranslationDao
import dev.clickn.translate.gallery.GalleryTranslationDatabase
import dev.clickn.translate.ocr.OcrEngine
import dev.clickn.translate.ocr.RoutingOcrEngine
import dev.clickn.translate.network.NetworkPerformanceEventListener
import dev.clickn.translate.network.DebugHttpWireLoggingInterceptor
import dev.clickn.translate.util.RuntimePerformanceDiagnostics
import dev.clickn.translate.translate.RoutingTranslator
import dev.clickn.translate.translate.TranslationCache
import dev.clickn.translate.translate.TranslationMemoryDao
import dev.clickn.translate.translate.TranslationMemoryDatabase
import dev.clickn.translate.translate.Translator
import dev.clickn.translate.translate.GoogleMlKitTranslationClientFactory
import dev.clickn.translate.translate.GoogleMlKitDownloadedLanguageProvider
import dev.clickn.translate.translate.MlKitDownloadedLanguageProvider
import dev.clickn.translate.translate.MlKitLanguageModelDeleter
import dev.clickn.translate.translate.MlKitTranslationClientFactory
import dev.clickn.translate.tts.RoutingTtsEngine
import dev.clickn.translate.tts.TtsEngine
import dagger.Binds
import dagger.Module
import dagger.Provides
import dagger.hilt.InstallIn
import dagger.hilt.components.SingletonComponent
import dagger.hilt.android.qualifiers.ApplicationContext
import javax.inject.Singleton
import kotlinx.serialization.json.Json
import okhttp3.OkHttpClient
import java.util.concurrent.TimeUnit

@Module
@InstallIn(SingletonComponent::class)
object AppModule {

    @Provides
    @Singleton
    fun provideJson(): Json = Json {
        ignoreUnknownKeys = true
        encodeDefaults = true
        explicitNulls = false
        // 当 JSON 字段是 null 但 data class 字段是非 null 类型时，回退到字段默认值而不抛错。
        // 防御外部 API（如 deeplx 返回 alternatives:null）的"宽松"响应破坏解析。
        coerceInputValues = true
    }

    @Provides
    @Singleton
    fun provideOkHttp(
        privateCleartextInterceptor: PrivateCleartextInterceptor,
        performanceDiagnostics: RuntimePerformanceDiagnostics,
    ): OkHttpClient = OkHttpClient.Builder()
        .connectTimeout(15, TimeUnit.SECONDS)
        .readTimeout(60, TimeUnit.SECONDS)
        .writeTimeout(60, TimeUnit.SECONDS)
        .eventListenerFactory(
            NetworkPerformanceEventListener.Factory(performanceDiagnostics)
        )
        // 明文 HTTP 仅允许私有/回环地址 + 用户显式白名单 host。详见拦截器注释。
        .addInterceptor(privateCleartextInterceptor)
        .apply {
            if (BuildConfig.DEBUG) {
                // Complete request/response logs for Debug builds only. The interceptor preserves
                // streaming delivery and redacts credentials before writing to Logcat.
                addInterceptor(DebugHttpWireLoggingInterceptor())
            }
        }
        .build()

    @Provides
    @Singleton
    fun provideTranslationCache(): TranslationCache = TranslationCache(capacity = 256)

    @Provides
    @Singleton
    fun provideTranslationGlossaryDatabase(
        @ApplicationContext context: Context,
    ): TranslationGlossaryDatabase = Room.databaseBuilder(
        context,
        TranslationGlossaryDatabase::class.java,
        "translation-glossary.db",
    ).build()

    @Provides
    fun provideTranslationGlossaryDao(
        database: TranslationGlossaryDatabase,
    ): TranslationGlossaryDao = database.glossaryDao()

    @Provides
    @Singleton
    fun provideTranslationMemoryDatabase(
        @ApplicationContext context: Context,
    ): TranslationMemoryDatabase = Room.databaseBuilder(
        context,
        TranslationMemoryDatabase::class.java,
        "translation-memory.db",
    ).build()

    @Provides
    fun provideTranslationMemoryDao(
        database: TranslationMemoryDatabase,
    ): TranslationMemoryDao = database.translationMemoryDao()

    @Provides
    @Singleton
    fun provideGalleryTranslationDatabase(
        @ApplicationContext context: Context,
    ): GalleryTranslationDatabase = Room.databaseBuilder(
        context,
        GalleryTranslationDatabase::class.java,
        "gallery-translation.db",
    ).build()

    @Provides
    fun provideGalleryTranslationDao(
        database: GalleryTranslationDatabase,
    ): GalleryTranslationDao = database.galleryTranslationDao()
}

@Module
@InstallIn(SingletonComponent::class)
abstract class EngineBindings {

    @Binds
    @Singleton
    abstract fun bindOcrEngine(impl: RoutingOcrEngine): OcrEngine

    @Binds
    @Singleton
    abstract fun bindTranslator(impl: RoutingTranslator): Translator

    @Binds
    abstract fun bindMlKitTranslationClientFactory(
        impl: GoogleMlKitTranslationClientFactory
    ): MlKitTranslationClientFactory

    @Binds
    abstract fun bindMlKitDownloadedLanguageProvider(
        impl: GoogleMlKitDownloadedLanguageProvider
    ): MlKitDownloadedLanguageProvider

    @Binds
    abstract fun bindMlKitLanguageModelDeleter(
        impl: GoogleMlKitDownloadedLanguageProvider
    ): MlKitLanguageModelDeleter

    @Binds
    @Singleton
    abstract fun bindTtsEngine(impl: RoutingTtsEngine): TtsEngine

    @Binds
    @Singleton
    abstract fun bindSettingsSecretCipher(
        impl: AndroidKeystoreSettingsSecretCipher
    ): SettingsSecretCipher
}
