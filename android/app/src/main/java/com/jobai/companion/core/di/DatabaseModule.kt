package com.jobai.companion.core.di

import android.content.Context
import androidx.room.Room
import androidx.room.migration.Migration
import androidx.sqlite.db.SupportSQLiteDatabase
import com.jobai.companion.core.db.AppDatabase
import com.jobai.companion.core.db.ApplicationDao
import com.jobai.companion.core.db.DlqDao
import com.jobai.companion.core.db.JobDao
import com.jobai.companion.core.db.MIGRATION_2_3
import com.jobai.companion.core.db.RunDao
import dagger.Module
import dagger.Provides
import dagger.hilt.InstallIn
import dagger.hilt.android.qualifiers.ApplicationContext
import dagger.hilt.components.SingletonComponent
import javax.inject.Singleton

private val migration_1_2 = object : Migration(1, 2) {
    override fun migrate(db: SupportSQLiteDatabase) {
        db.execSQL("""
            CREATE TABLE IF NOT EXISTS dlq_items (
                id TEXT NOT NULL PRIMARY KEY,
                kind TEXT NOT NULL,
                correlationId TEXT NOT NULL,
                status TEXT NOT NULL,
                errorCode TEXT,
                retryCount INTEGER NOT NULL,
                startedAt INTEGER,
                finishedAt INTEGER,
                syncedAt INTEGER NOT NULL
            )
        """.trimIndent())
    }
}

@Module
@InstallIn(SingletonComponent::class)
object DatabaseModule {

    @Provides @Singleton
    fun provideDatabase(@ApplicationContext ctx: Context): AppDatabase =
        Room.databaseBuilder(ctx, AppDatabase::class.java, "jobai.db")
            .addMigrations(migration_1_2, MIGRATION_2_3)
            .build()

    @Provides fun provideJobDao(db: AppDatabase): JobDao = db.jobDao()
    @Provides fun provideApplicationDao(db: AppDatabase): ApplicationDao = db.applicationDao()
    @Provides fun provideRunDao(db: AppDatabase): RunDao = db.runDao()
    @Provides fun provideDlqDao(db: AppDatabase): DlqDao = db.dlqDao()
}
