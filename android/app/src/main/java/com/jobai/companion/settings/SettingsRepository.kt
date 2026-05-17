package com.jobai.companion.settings

import com.jobai.companion.auth.AuthRepository
import com.jobai.companion.core.api.JobAiService
import com.jobai.companion.core.auth.SessionStore
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class SettingsRepository @Inject constructor(
    private val api: JobAiService,
    private val sessionStore: SessionStore,
    private val authRepository: AuthRepository,
) {
    val serverUrl: String get() = sessionStore.serverUrl ?: "—"
    val deviceId: String get() = sessionStore.deviceId ?: "—"

    suspend fun gmailAuthorized(): Boolean =
        runCatching { api.gmailStatus().authorized }.getOrDefault(false)

    suspend fun unpair() {
        val deviceId = sessionStore.deviceId
        if (deviceId != null) runCatching { api.deleteDevice(deviceId) }
        authRepository.unpair()
    }
}
