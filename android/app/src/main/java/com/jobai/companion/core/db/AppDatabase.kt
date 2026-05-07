package com.jobai.companion.core.db

import androidx.room.Database
import androidx.room.Entity
import androidx.room.PrimaryKey
import androidx.room.RoomDatabase

@Entity(tableName = "jobs")
data class JobEntity(
    @PrimaryKey val id: String,
    val title: String,
    val company: String,
    val location: String?,
    val url: String?,
    val status: String,
    val matchScore: Float?,
    val scrapedAt: Long,
    val starred: Boolean,
    val dismissed: Boolean,
    val syncedAt: Long,
)

@Entity(tableName = "applications")
data class ApplicationEntity(
    @PrimaryKey val id: String,
    val jobId: String,
    val jobTitle: String,
    val company: String,
    val channel: String,
    val currentStatus: String,
    val submittedAt: Long,
    val externalRef: String?,
    val syncedAt: Long,
)

@Entity(tableName = "runs")
data class RunEntity(
    @PrimaryKey val id: String,
    val kind: String,
    val status: String,
    val startedAt: Long,
    val finishedAt: Long?,
    val jobsFound: Int,
    val syncedAt: Long,
)

@Database(
    entities = [JobEntity::class, ApplicationEntity::class, RunEntity::class],
    version = 1,
    exportSchema = false,
)
abstract class AppDatabase : RoomDatabase() {
    abstract fun jobDao(): JobDao
    abstract fun applicationDao(): ApplicationDao
    abstract fun runDao(): RunDao
}
