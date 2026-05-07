package com.jobai.companion.runs

import com.jobai.companion.core.api.JobAiService
import com.jobai.companion.core.db.RunDao
import com.jobai.companion.core.db.RunEntity
import com.jobai.companion.core.model.Run
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map
import java.time.Instant
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class RunsRepository @Inject constructor(
    private val runDao: RunDao,
    private val api: JobAiService,
) {
    val runsFlow: Flow<List<Run>> = runDao.observeRecent().map { entities ->
        entities.map {
            Run(
                id = it.id,
                kind = it.kind,
                status = it.status,
                startedAt = Instant.ofEpochMilli(it.startedAt),
                finishedAt = it.finishedAt?.let(Instant::ofEpochMilli),
                jobsFound = it.jobsFound,
            )
        }
    }

    suspend fun sync() {
        val now = System.currentTimeMillis()
        val runs = api.listRuns(perPage = 20)
        runDao.upsertAll(runs.map { dto ->
            RunEntity(
                id = dto.id,
                kind = dto.kind,
                status = dto.status,
                startedAt = Instant.parse(dto.startedAt).toEpochMilli(),
                finishedAt = dto.finishedAt?.let { Instant.parse(it).toEpochMilli() },
                jobsFound = 0, // not exposed in RunOut yet — SP3 to enrich
                syncedAt = now,
            )
        })
    }

    suspend fun triggerRun() = api.triggerRun()
}
