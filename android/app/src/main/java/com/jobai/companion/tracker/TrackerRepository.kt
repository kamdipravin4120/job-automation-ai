package com.jobai.companion.tracker

import com.jobai.companion.core.api.JobAiService
import com.jobai.companion.core.db.ApplicationDao
import com.jobai.companion.core.db.ApplicationEntity
import com.jobai.companion.core.model.Application
import com.jobai.companion.core.model.RecruiterInfo
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
        entities.map { it.toDomain() }
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
                    jobTitle = dto.jobTitle.ifBlank { dto.jobId },
                    company = dto.jobCompany,
                    channel = dto.channel,
                    currentStatus = dto.currentStatus,
                    submittedAt = Instant.parse(dto.submittedAt).toEpochMilli(),
                    externalRef = dto.externalRef,
                    syncedAt = now,
                    recruiterName = dto.recruiter?.name,
                    recruiterEmail = dto.recruiter?.email,
                    recruiterCompany = dto.recruiter?.company,
                    emailStatus = dto.emailStatus,
                    lastContactAt = dto.lastContactAt?.let { runCatching { Instant.parse(it).toEpochMilli() }.getOrNull() },
                )
            })
            page++
        } while (resp.hasNext)
    }

    suspend fun fetchFollowUps(): List<Application> =
        api.listFollowUps().map { dto ->
            Application(
                id = dto.id,
                jobId = dto.jobId,
                jobTitle = dto.jobTitle.ifBlank { dto.jobId },
                company = dto.jobCompany,
                channel = dto.channel,
                currentStatus = dto.currentStatus,
                submittedAt = Instant.parse(dto.submittedAt),
                externalRef = dto.externalRef,
                recruiter = dto.recruiter?.let { RecruiterInfo(it.name, it.email, it.company) },
                emailStatus = dto.emailStatus,
                lastContactAt = dto.lastContactAt?.let { runCatching { Instant.parse(it) }.getOrNull() },
            )
        }
}

private fun ApplicationEntity.toDomain() = Application(
    id = id,
    jobId = jobId,
    jobTitle = jobTitle,
    company = company,
    channel = channel,
    currentStatus = currentStatus,
    submittedAt = Instant.ofEpochMilli(submittedAt),
    externalRef = externalRef,
    recruiter = if (recruiterName != null || recruiterEmail != null || recruiterCompany != null)
        RecruiterInfo(recruiterName, recruiterEmail, recruiterCompany) else null,
    emailStatus = emailStatus,
    lastContactAt = lastContactAt?.let { Instant.ofEpochMilli(it) },
)
