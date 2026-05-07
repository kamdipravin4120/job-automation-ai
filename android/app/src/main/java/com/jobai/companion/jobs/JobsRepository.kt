package com.jobai.companion.jobs

import com.jobai.companion.core.api.JobAiService
import com.jobai.companion.core.db.JobDao
import com.jobai.companion.core.db.JobEntity
import com.jobai.companion.core.model.Job
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map
import java.time.Instant
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class JobsRepository @Inject constructor(
    private val jobDao: JobDao,
    private val api: JobAiService,
) {
    val jobsFlow: Flow<List<Job>> = jobDao.observeAll().map { entities ->
        entities.map { it.toDomain() }
    }

    suspend fun sync() {
        val now = System.currentTimeMillis()
        var page = 1
        do {
            val resp = api.listJobs(page = page, perPage = 50)
            jobDao.upsertAll(resp.items.map { dto ->
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
            page++
        } while (resp.hasNext)
    }

    suspend fun star(jobId: String) {
        val current = jobDao.findById(jobId) ?: return
        jobDao.updateStarred(jobId, !current.starred)
        runCatching { api.starJob(jobId) }
    }

    suspend fun dismiss(jobId: String) {
        jobDao.markDismissed(jobId)
        runCatching { api.dismissJob(jobId) }
    }
}

fun JobEntity.toDomain() = Job(
    id = id,
    title = title,
    company = company,
    location = location,
    url = url,
    status = status,
    matchScore = matchScore,
    scrapedAt = Instant.ofEpochMilli(scrapedAt),
    starred = starred,
    dismissed = dismissed,
)
