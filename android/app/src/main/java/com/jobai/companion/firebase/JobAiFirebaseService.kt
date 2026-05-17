package com.jobai.companion.firebase

import android.app.NotificationChannel
import android.app.NotificationManager
import android.content.Context
import androidx.core.app.NotificationCompat
import com.google.firebase.messaging.FirebaseMessagingService
import com.google.firebase.messaging.RemoteMessage
import com.jobai.companion.core.api.FcmRegisterRequest
import com.jobai.companion.core.api.JobAiService
import com.jobai.companion.core.auth.SessionStore
import dagger.hilt.android.AndroidEntryPoint
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.launch
import javax.inject.Inject

private const val CHANNEL_ID = "jobai_pipeline"
private const val CHANNEL_NAME = "Pipeline Events"

@AndroidEntryPoint
class JobAiFirebaseService : FirebaseMessagingService() {

    @Inject lateinit var api: JobAiService
    @Inject lateinit var sessionStore: SessionStore
    @Inject @ApplicationScope lateinit var scope: CoroutineScope

    override fun onNewToken(token: String) {
        val deviceId = sessionStore.deviceId ?: return
        scope.launch {
            runCatching { api.registerFcmToken(FcmRegisterRequest(token = token, deviceId = deviceId)) }
        }
    }

    override fun onMessageReceived(message: RemoteMessage) {
        val kind = message.data["kind"]
        val jobId = message.data["job_id"]
        if (kind != null) {
            FcmEventBus.emit(FcmEvent(kind = kind, jobId = jobId))
        }
        val title = message.notification?.title ?: message.data["title"] ?: "JobAI"
        val body = message.notification?.body ?: message.data["body"] ?: ""
        showNotification(title, body)
    }

    private fun showNotification(title: String, body: String) {
        val manager = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        val channel = NotificationChannel(CHANNEL_ID, CHANNEL_NAME, NotificationManager.IMPORTANCE_DEFAULT)
        manager.createNotificationChannel(channel)
        val notification = NotificationCompat.Builder(this, CHANNEL_ID)
            .setSmallIcon(android.R.drawable.ic_dialog_info)
            .setContentTitle(title)
            .setContentText(body)
            .setAutoCancel(true)
            .build()
        manager.notify(System.currentTimeMillis().toInt(), notification)
    }
}
