package com.jobai.companion.core.model

import java.time.Instant

data class Run(
    val id: String,
    val kind: String,
    val status: String,
    val startedAt: Instant,
    val finishedAt: Instant?,
    val jobsFound: Int,
)
