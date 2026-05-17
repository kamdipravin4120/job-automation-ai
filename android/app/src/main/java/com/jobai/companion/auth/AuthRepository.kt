package com.jobai.companion.auth

import com.google.firebase.messaging.FirebaseMessaging
import com.jobai.companion.core.api.ChallengeRequest
import com.jobai.companion.core.api.FcmRegisterRequest
import com.jobai.companion.core.api.JobAiService
import com.jobai.companion.core.api.PairRequest
import com.jobai.companion.core.auth.KeystoreHelper
import com.jobai.companion.core.auth.SessionStore
import kotlinx.coroutines.tasks.await
import javax.inject.Inject
import javax.inject.Singleton

sealed class PairResult {
    data class Success(val deviceId: String) : PairResult()
    data class Error(val message: String) : PairResult()
}

@Singleton
class AuthRepository @Inject constructor(
    private val api: JobAiService,
    private val keystoreHelper: KeystoreHelper,
    private val sessionStore: SessionStore,
) {
    suspend fun pair(bootstrapSecret: String, serverUrl: String): PairResult = runCatching {
        val challengeResp = api.challenge(ChallengeRequest(bootstrapSecret))
        val challengeHex = challengeResp.challenge

        val publicKeyHexDer = keystoreHelper.publicKeyHexDer
        val signatureHex = keystoreHelper.signHex(challengeHex)

        val pairResp = api.pair(PairRequest(bootstrapSecret, publicKeyHexDer, signatureHex))

        sessionStore.sessionToken = pairResp.sessionToken
        sessionStore.deviceId = pairResp.deviceId
        sessionStore.serverUrl = serverUrl

        runCatching {
            val fcmToken = FirebaseMessaging.getInstance().token.await()
            api.registerFcmToken(FcmRegisterRequest(token = fcmToken, deviceId = pairResp.deviceId))
        }

        PairResult.Success(pairResp.deviceId)
    }.getOrElse { e ->
        PairResult.Error(e.message ?: "Pairing failed")
    }

    fun unpair() {
        sessionStore.clear()
        keystoreHelper.clearKeyPair()
    }

    val isPaired: Boolean get() = sessionStore.isPaired
}
