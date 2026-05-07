package com.jobai.companion.core.db

import androidx.room.*
import kotlinx.coroutines.flow.Flow

@Dao
interface RunDao {
    @Query("SELECT * FROM runs ORDER BY startedAt DESC LIMIT 50")
    fun observeRecent(): Flow<List<RunEntity>>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsertAll(runs: List<RunEntity>)
}
