package com.jobai.companion.core.auth

import android.content.Context
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey
import dagger.hilt.android.qualifiers.ApplicationContext
import javax.inject.Inject
import javax.inject.Singleton

private const val PREFS_FILE = "jobai_session"
private const val KEY_SESSION_TOKEN = "session_token"
private const val KEY_DEVICE_ID = "device_id"
private const val KEY_SERVER_URL = "server_url"

@Singleton
class SessionStore @Inject constructor(
    @ApplicationContext private val context: Context,
) {
    private val prefs by lazy {
        val masterKey = MasterKey.Builder(context)
            .setKeyScheme(MasterKey.KeyScheme.AES256_GCM)
            .build()
        EncryptedSharedPreferences.create(
            context,
            PREFS_FILE,
            masterKey,
            EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
            EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM,
        )
    }

    var sessionToken: String?
        get() = prefs.getString(KEY_SESSION_TOKEN, null)
        set(v) = prefs.edit().putStringOrRemove(KEY_SESSION_TOKEN, v).apply()

    var deviceId: String?
        get() = prefs.getString(KEY_DEVICE_ID, null)
        set(v) = prefs.edit().putStringOrRemove(KEY_DEVICE_ID, v).apply()

    var serverUrl: String?
        get() = prefs.getString(KEY_SERVER_URL, null)
        set(v) = prefs.edit().putStringOrRemove(KEY_SERVER_URL, v).apply()

    val isPaired: Boolean get() = sessionToken != null

    fun clear() {
        prefs.edit().clear().apply()
    }

    private fun android.content.SharedPreferences.Editor.putStringOrRemove(
        key: String, value: String?
    ) = if (value != null) putString(key, value) else remove(key)
}
