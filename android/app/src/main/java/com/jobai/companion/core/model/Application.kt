package com.jobai.companion.core.model

import java.time.Instant

data class Application(
    val id: String,
    val jobId: String,
    val jobTitle: String,
    val company: String,
    val channel: String,
    val currentStatus: String,
    val submittedAt: Instant,
    val externalRef: String?,
)
