package com.jobai.companion.core.model

import java.time.Instant

data class Job(
    val id: String,
    val title: String,
    val company: String,
    val location: String?,
    val url: String?,
    val status: String,
    val matchScore: Float?,
    val scrapedAt: Instant,
    val starred: Boolean,
    val dismissed: Boolean,
)
