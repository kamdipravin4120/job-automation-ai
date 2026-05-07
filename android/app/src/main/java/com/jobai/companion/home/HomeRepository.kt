package com.jobai.companion.home

import com.jobai.companion.core.api.JobAiService
import com.jobai.companion.core.db.ApplicationDao
import com.jobai.companion.core.db.JobDao
import com.jobai.companion.core.db.JobEntity
import com.jobai.companion.core.db.RunDao
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map
import java.time.Instant
import javax.inject.Inject
import javax.inject.Singleton

data class DashboardState(
    val totalJobs: Int,
    val appliedCount: Int,
    val avgScore: Float,
    val lastRunTime: Instant?,
    val recentActivity: List<ActivityEvent>,
)

data class ActivityEvent(val label: String, val time: Instant)

@Singleton
class HomeRepository @Inject constructor(
    private val jobDao: JobDao,
    private val applicationDao: ApplicationDao,
    private val runDao: RunDao,
    private val api: JobAiService,
) {
    val dashboardFlow: Flow<DashboardState> = jobDao.observeAll().map { jobs ->
        DashboardState(
            totalJobs = jobs.size,
            appliedCount = 0,
            avgScore = jobs.mapNotNull { it.matchScore }.average().takeIf { !it.isNaN() }?.toFloat() ?: 0f,
            lastRunTime = null,
            recentActivity = emptyList(),
        )
    }

    suspend fun triggerScrape() = api.triggerRun()

    suspend fun sync() {
        val jobs = api.listJobs(perPage = 100)
        val now = System.currentTimeMillis()
        jobDao.upsertAll(jobs.items.map { dto ->
            JobEntity(
                id = dto.id,
                title = dto.title,
                company = dto.company,
                location = dto.location,
                url = dto.url,
                status = dto.status,
                matchScore = dto.matchScore,
                scrapedAt = Instant.parse(dto.scrapedAt).toEpochMilli(),
                starred = dto.starred,
                dismissed = dto.dismissed,
                syncedAt = now,
            )
        })
    }
}
