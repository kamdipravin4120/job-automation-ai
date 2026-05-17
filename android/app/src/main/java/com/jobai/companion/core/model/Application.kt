package com.jobai.companion.core.model

import java.time.Instant

data class RecruiterInfo(
    val name: String?,
    val email: String?,
    val company: String?,
)

data class Application(
    val id: String,
    val jobId: String,
    val jobTitle: String,
    val company: String,
    val channel: String,
    val currentStatus: String,
    val submittedAt: Instant,
    val externalRef: String?,
    val recruiter: RecruiterInfo? = null,
    val emailStatus: String? = null,
    val lastContactAt: Instant? = null,
)
