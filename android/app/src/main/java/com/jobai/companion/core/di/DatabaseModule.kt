package com.jobai.companion.core.di

import android.content.Context
import androidx.room.Room
import com.jobai.companion.core.db.AppDatabase
import com.jobai.companion.core.db.ApplicationDao
import com.jobai.companion.core.db.JobDao
import com.jobai.companion.core.db.RunDao
import dagger.Module
import dagger.Provides
import dagger.hilt.InstallIn
import dagger.hilt.android.qualifiers.ApplicationContext
import dagger.hilt.components.SingletonComponent
import javax.inject.Singleton

@Module
@InstallIn(SingletonComponent::class)
object DatabaseModule {

    @Provides @Singleton
    fun provideDatabase(@ApplicationContext ctx: Context): AppDatabase =
        Room.databaseBuilder(ctx, AppDatabase::class.java, "jobai.db").build()

    @Provides fun provideJobDao(db: AppDatabase): JobDao = db.jobDao()
    @Provides fun provideApplicationDao(db: AppDatabase): ApplicationDao = db.applicationDao()
    @Provides fun provideRunDao(db: AppDatabase): RunDao = db.runDao()
}
