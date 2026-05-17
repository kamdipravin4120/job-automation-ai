package com.jobai.companion.core.db

import androidx.room.*
import kotlinx.coroutines.flow.Flow

@Dao
interface ApplicationDao {
    @Query("SELECT * FROM applications ORDER BY submittedAt DESC")
    fun observeAll(): Flow<List<ApplicationEntity>>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsertAll(apps: List<ApplicationEntity>)
}
