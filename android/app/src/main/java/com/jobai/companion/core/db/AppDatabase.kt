package com.jobai.companion.core.db

import androidx.room.*
import kotlinx.coroutines.flow.Flow

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

@Entity(tableName = "dlq_items")
data class DlqEntity(
    @PrimaryKey val id: String,
    val kind: String,
    val correlationId: String,
    val status: String,
    val errorCode: String?,
    val retryCount: Int,
    val startedAt: Long?,
    val finishedAt: Long?,
    val syncedAt: Long,
)

@Dao
interface DlqDao {
    @Query("SELECT * FROM dlq_items ORDER BY startedAt DESC")
    fun observeAll(): Flow<List<DlqEntity>>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsertAll(items: List<DlqEntity>)

    @Query("DELETE FROM dlq_items WHERE id = :id")
    suspend fun delete(id: String)
}

@Database(
    entities = [JobEntity::class, ApplicationEntity::class, RunEntity::class, DlqEntity::class],
    version = 2,
    exportSchema = false,
)
abstract class AppDatabase : RoomDatabase() {
    abstract fun jobDao(): JobDao
    abstract fun applicationDao(): ApplicationDao
    abstract fun runDao(): RunDao
    abstract fun dlqDao(): DlqDao
}
