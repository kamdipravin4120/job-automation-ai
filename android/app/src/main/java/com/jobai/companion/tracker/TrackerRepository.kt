package com.jobai.companion.tracker

import com.jobai.companion.core.api.JobAiService
import com.jobai.companion.core.db.ApplicationDao
import com.jobai.companion.core.db.ApplicationEntity
import com.jobai.companion.core.model.Application
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map
import java.time.Instant
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class TrackerRepository @Inject constructor(
    private val applicationDao: ApplicationDao,
    private val api: JobAiService,
) {
    val applicationsFlow: Flow<List<Application>> = applicationDao.observeAll().map { entities ->
        entities.map {
            Application(
                id = it.id,
                jobId = it.jobId,
                jobTitle = it.jobTitle,
                company = it.company,
                channel = it.channel,
                currentStatus = it.currentStatus,
                submittedAt = Instant.ofEpochMilli(it.submittedAt),
                externalRef = it.externalRef,
            )
        }
    }

    suspend fun sync() {
        val now = System.currentTimeMillis()
        var page = 1
        do {
            val resp = api.listApplications(page = page, perPage = 100)
            applicationDao.upsertAll(resp.items.map { dto ->
                ApplicationEntity(
                    id = dto.id,
                    jobId = dto.jobId,
                    jobTitle = dto.jobId, // API doesn't return title — enrich in SP3
                    company = "",
                    channel = dto.channel,
                    currentStatus = dto.currentStatus,
                    submittedAt = Instant.parse(dto.submittedAt).toEpochMilli(),
                    externalRef = dto.externalRef,
                    syncedAt = now,
                )
            })
            page++
        } while (resp.hasNext)
    }
}
