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
    @Json(name = "jobs_found") val jobsFound: Int = 0,
    @Json(name = "error_code") val errorCode: String? = null,
)

@JsonClass(generateAdapter = true)
data class PaginatedRuns(
    val items: List<RunDto>,
    val total: Int,
    val page: Int,
    @Json(name = "per_page") val perPage: Int,
    @Json(name = "has_next") val hasNext: Boolean,
)

@JsonClass(generateAdapter = true)
data class TriggerRunResponse(val id: String, val status: String)

// ─── DLQ DTOs ────────────────────────────────────────────────
@JsonClass(generateAdapter = true)
data class DlqDto(
    val id: String,
    val kind: String,
    @Json(name = "correlation_id") val correlationId: String,
    val status: String,
    @Json(name = "error_code") val errorCode: String?,
    @Json(name = "retry_count") val retryCount: Int,
    @Json(name = "started_at") val startedAt: String?,
    @Json(name = "finished_at") val finishedAt: String?,
)

@JsonClass(generateAdapter = true)
data class PaginatedDlq(
    val items: List<DlqDto>,
    val total: Int,
    val page: Int,
    @Json(name = "per_page") val perPage: Int,
    @Json(name = "has_next") val hasNext: Boolean,
)

@JsonClass(generateAdapter = true)
data class GmailStatusDto(val authorized: Boolean)

@JsonClass(generateAdapter = true)
data class FcmRegisterRequest(
    val token: String,
    @Json(name = "device_id") val deviceId: String,
)

@JsonClass(generateAdapter = true)
data class FcmRegisterOut(val registered: Boolean)

@JsonClass(generateAdapter = true)
data class DlqActionOut(val queued: Boolean? = null, val dismissed: Boolean? = null)

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
    suspend fun listRuns(
        @Query("page") page: Int = 1,
        @Query("per_page") perPage: Int = 20,
    ): PaginatedRuns

    @GET("pipeline/runs/{id}")
    suspend fun getRunDetail(@Path("id") id: String): RunDto

    @POST("pipeline/runs")
    suspend fun triggerRun(): TriggerRunResponse

    @GET("dlq")
    suspend fun listDlq(
        @Query("page") page: Int = 1,
        @Query("per_page") perPage: Int = 50,
    ): PaginatedDlq

    @POST("dlq/{id}/retry")
    suspend fun retryDlqItem(@Path("id") id: String): DlqActionOut

    @POST("dlq/{id}/dismiss")
    suspend fun dismissDlqItem(@Path("id") id: String): DlqActionOut

    @GET("gmail/status")
    suspend fun gmailStatus(): GmailStatusDto

    @POST("notifications/fcm/register")
    suspend fun registerFcmToken(@Body body: FcmRegisterRequest): FcmRegisterOut

    @DELETE("devices/{deviceId}")
    suspend fun deleteDevice(@Path("deviceId") deviceId: String)
}
