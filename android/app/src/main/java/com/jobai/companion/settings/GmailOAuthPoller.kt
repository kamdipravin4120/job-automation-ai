package com.jobai.companion.settings

import com.jobai.companion.core.api.JobAiService
import kotlinx.coroutines.delay
import javax.inject.Inject

sealed class PollResult {
    object Authorized : PollResult()
    object TimedOut : PollResult()
}

class GmailOAuthPoller @Inject constructor(private val api: JobAiService) {
    suspend fun pollUntilAuthorized(
        timeoutMs: Long = 300_000L,
        intervalMs: Long = 3_000L,
    ): PollResult {
        val deadline = System.currentTimeMillis() + timeoutMs
        while (System.currentTimeMillis() < deadline) {
            val status = runCatching { api.gmailStatus() }.getOrNull()
            if (status?.authorized == true) return PollResult.Authorized
            delay(intervalMs)
        }
        return PollResult.TimedOut
    }
}
