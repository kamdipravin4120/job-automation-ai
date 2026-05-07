package com.jobai.companion.core.api

import com.squareup.moshi.Json
import com.squareup.moshi.JsonClass
import retrofit2.http.*

// ─── Auth DTOs ───────────────────────────────────────────────
@JsonClass(generateAdapter = true)
data class ChallengeRequest(@Json(name = "bootstrap_secret") val bootstrapSecret: String)

@JsonClass(generateAdapter = true)
data class ChallengeResponse(val challenge: String)

@JsonClass(generateAdapter = true)
data class PairRequest(
    @Json(name = "bootstrap_secret") val bootstrapSecret: String,
    @Json(name = "public_key") val publicKey: String,
    val signature: String,
)

@JsonClass(generateAdapter = true)
data class PairResponse(
    @Json(name = "session_token") val sessionToken: String,
    @Json(name = "device_id") val deviceId: String,
)

// ─── Job DTOs ────────────────────────────────────────────────
@JsonClass(generateAdapter = true)
data class JobDto(
    val id: String,
    val title: String,
    val company: String,
    val location: String?,
    val url: String?,
    val status: String,
    @Json(name = "match_score") val matchScore: Float?,
    @Json(name = "scraped_at") val scrapedAt: String,
    val starred: Boolean = false,
    val dismissed: Boolean = false,
)

@JsonClass(generateAdapter = true)
data class PaginatedJobs(
    val items: List<JobDto>,
    val total: Int,
    val page: Int,
    @Json(name = "per_page") val perPage: Int,
    @Json(name = "has_next") val hasNext: Boolean,
)

// ─── Application DTOs ────────────────────────────────────────
@JsonClass(generateAdapter = true)
data class ApplicationDto(
    val id: String,
    @Json(name = "job_id") val jobId: String,
    val channel: String,
    @Json(name = "current_status") val currentStatus: String,
    @Json(name = "submitted_at") val submittedAt: String,
    @Json(name = "external_ref") val externalRef: String?,
)

@JsonClass(generateAdapter = true)
data class PaginatedApplications(
    val items: List<ApplicationDto>,
    val total: Int,
    val page: Int,
    @Json(name = "per_page") val perPage: Int,
    @Json(name = "has_next") val hasNext: Boolean,
)

// ─── Run DTOs ─────────────────────────────────────────────────
@JsonClass(generateAdapter = true)
data class RunDto(
    val id: String,
    val kind: String,
    val status: String,
    @Json(name = "started_at") val startedAt: String,
    @Json(name = "finished_at") val finishedAt: String?,
)

@JsonClass(generateAdapter = true)
data class TriggerRunResponse(val id: String, val status: String)

// ─── Service interface ────────────────────────────────────────
interface JobAiService {
    @POST("auth/challenge")
    suspend fun challenge(@Body body: ChallengeRequest): ChallengeResponse

    @POST("auth/pair")
    suspend fun pair(@Body body: PairRequest): PairResponse

    @GET("jobs")
    suspend fun listJobs(
        @Query("page") page: Int = 1,
        @Query("per_page") perPage: Int = 50,
    ): PaginatedJobs

    @POST("jobs/{id}/star")
    suspend fun starJob(@Path("id") id: String): JobDto

    @POST("jobs/{id}/dismiss")
    suspend fun dismissJob(@Path("id") id: String): JobDto

    @GET("applications")
    suspend fun listApplications(
        @Query("page") page: Int = 1,
        @Query("per_page") perPage: Int = 100,
    ): PaginatedApplications

    @GET("pipeline/runs")
    suspend fun listRuns(@Query("per_page") perPage: Int = 20): List<RunDto>

    @POST("pipeline/runs")
    suspend fun triggerRun(): TriggerRunResponse
}
