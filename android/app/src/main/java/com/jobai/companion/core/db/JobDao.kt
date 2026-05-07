package com.jobai.companion.core.db

import androidx.room.*
import kotlinx.coroutines.flow.Flow

@Dao
interface JobDao {
    @Query("SELECT * FROM jobs WHERE dismissed = 0 ORDER BY scrapedAt DESC")
    fun observeAll(): Flow<List<JobEntity>>

    @Query("SELECT * FROM jobs WHERE id = :id")
    suspend fun findById(id: String): JobEntity?

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsertAll(jobs: List<JobEntity>)

    @Query("UPDATE jobs SET starred = :starred WHERE id = :id")
    suspend fun updateStarred(id: String, starred: Boolean)

    @Query("UPDATE jobs SET dismissed = 1 WHERE id = :id")
    suspend fun markDismissed(id: String)
}
