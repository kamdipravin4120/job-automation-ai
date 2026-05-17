package com.jobai.companion.auth

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

sealed class PairingState {
    object Idle : PairingState()
    object Scanning : PairingState()
    data class Connecting(val step: Int) : PairingState()
    data class Paired(val deviceId: String) : PairingState()
    data class Failed(val error: String) : PairingState()
}

data class QrPayload(val url: String, val bootstrapSecret: String)

@HiltViewModel
class PairingViewModel @Inject constructor(
    private val authRepository: AuthRepository,
) : ViewModel() {

    private val _state = MutableStateFlow<PairingState>(PairingState.Idle)
    val state: StateFlow<PairingState> = _state

    fun startScan() { _state.value = PairingState.Scanning }

    fun onQrScanned(raw: String) {
        val payload = parseQrPayload(raw) ?: run {
            _state.value = PairingState.Failed("Invalid QR code")
            return
        }
        viewModelScope.launch {
            _state.value = PairingState.Connecting(step = 0)
            kotlinx.coroutines.delay(300)
            _state.value = PairingState.Connecting(step = 1)
            kotlinx.coroutines.delay(400)
            _state.value = PairingState.Connecting(step = 2)
            when (val result = authRepository.pair(payload.bootstrapSecret, payload.url)) {
                is PairResult.Success -> {
                    _state.value = PairingState.Connecting(step = 3)
                    kotlinx.coroutines.delay(300)
                    _state.value = PairingState.Paired(result.deviceId)
                }
                is PairResult.Error -> _state.value = PairingState.Failed(result.message)
            }
        }
    }

    fun retryFromIdle() { _state.value = PairingState.Idle }

    private fun parseQrPayload(raw: String): QrPayload? = runCatching {
        val url = Regex(""""url"\s*:\s*"([^"]+)"""").find(raw)?.groupValues?.get(1) ?: return null
        val secret = Regex(""""bootstrap_secret"\s*:\s*"([^"]+)"""").find(raw)?.groupValues?.get(1) ?: return null
        QrPayload(url, secret)
    }.getOrNull()
}
