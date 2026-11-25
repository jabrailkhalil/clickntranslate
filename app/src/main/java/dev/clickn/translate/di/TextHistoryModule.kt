package dev.clickn.translate.di

import android.content.Context
import androidx.room.Room
import dagger.Module
import dagger.Provides
import dagger.hilt.InstallIn
import dagger.hilt.android.qualifiers.ApplicationContext
import dagger.hilt.components.SingletonComponent
import dev.clickn.translate.history.SharedPreferencesTextHistorySource
import dev.clickn.translate.history.TextHistoryDatabase
import dev.clickn.translate.history.TextHistoryRepository
import javax.inject.Singleton

@Module
@InstallIn(SingletonComponent::class)
object TextHistoryModule {
    @Provides
    @Singleton
    fun database(@ApplicationContext context: Context): TextHistoryDatabase =
        Room.databaseBuilder(context, TextHistoryDatabase::class.java, "text-history.db").build()

    @Provides
    @Singleton
    fun repository(database: TextHistoryDatabase, @ApplicationContext context: Context): TextHistoryRepository =
        TextHistoryRepository(database, SharedPreferencesTextHistorySource(context))
}
