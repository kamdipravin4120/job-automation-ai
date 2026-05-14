package com.jobai.companion.settings

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.*
import kotlinx.coroutines.launch
import javax.inject.Inject

data class SettingsUiState(
    val serverUrl: String = "",
    val deviceId: String = "",
    val gmailAuthorized: Boolean = false,
    val isUnpairing: Boolean = false,
    val isPollingGmail: Boolean = false,
    val gmailPollTimedOut: Boolean = false,
    val navigateToWelcome: Boolean = false,
)

@HiltViewModel
class SettingsViewModel @Inject constructor(
    private val repo: SettingsRepository,
    private val gmailPoller: GmailOAuthPoller,
) : ViewModel() {

    private val _state = MutableStateFlow(SettingsUiState())
    val uiState: StateFlow<SettingsUiState> = _state.asStateFlow()

    init {
        _state.update { it.copy(serverUrl = repo.serverUrl, deviceId = repo.deviceId) }
        viewModelScope.launch {
            val authorized = repo.gmailAuthorized()
            _state.update { it.copy(gmailAuthorized = authorized) }
        }
    }

    fun startGmailOAuthPoll() {
        viewModelScope.launch {
            _state.update { it.copy(isPollingGmail = true, gmailPollTimedOut = false) }
            when (gmailPoller.pollUntilAuthorized()) {
                is PollResult.Authorized -> _state.update { it.copy(gmailAuthorized = true, isPollingGmail = false) }
                is PollResult.TimedOut -> _state.update { it.copy(gmailPollTimedOut = true, isPollingGmail = false) }
            }
        }
    }

    fun unpair() {
        viewModelScope.launch {
            _state.update { it.copy(isUnpairing = true) }
            runCatching { repo.unpair() }
            _state.update { it.copy(isUnpairing = false, navigateToWelcome = true) }
        }
    }

    fun onNavigatedToWelcome() {
        _state.update { it.copy(navigateToWelcome = false) }
    }
}
