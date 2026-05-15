package com.jobai.companion.tracker

import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.jobai.companion.core.api.BriefingItemDto
import com.jobai.companion.core.api.JobAiService
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import javax.inject.Inject

data class AppDetailUiState(
    val appId: String = "",
    val title: String = "",
    val currentStatus: String = "",
    val briefingItems: List<BriefingItemDto> = emptyList(),
    val isLoading: Boolean = true,
    val isGenerating: Boolean = false,
    val error: String? = null,
)

@HiltViewModel
class ApplicationDetailViewModel @Inject constructor(
    private val api: JobAiService,
    savedStateHandle: SavedStateHandle,
) : ViewModel() {

    private val appId: String = checkNotNull(savedStateHandle["appId"])

    private val _state = MutableStateFlow(
        AppDetailUiState(
            appId = appId,
            title = savedStateHandle["title"] ?: "",
            currentStatus = savedStateHandle["status"] ?: "",
        )
    )
    val uiState: StateFlow<AppDetailUiState> = _state.asStateFlow()

    init { load() }

    private fun load() {
        viewModelScope.launch {
            _state.update { it.copy(isLoading = true, error = null) }
            runCatching { api.getApplication(appId) }
                .onSuccess { dto ->
                    _state.update {
                        it.copy(
                            briefingItems = dto.briefingJson ?: emptyList(),
                            isLoading = false,
                        )
                    }
                }
                .onFailure { err ->
                    _state.update { it.copy(isLoading = false, error = err.message) }
                }
        }
    }

    fun generateBrief() {
        viewModelScope.launch {
            _state.update { it.copy(isGenerating = true, error = null) }
            runCatching { api.generateBrief(appId) }
                .onSuccess { dto ->
                    _state.update {
                        it.copy(
                            briefingItems = dto.briefingJson ?: emptyList(),
                            isGenerating = false,
                        )
                    }
                }
                .onFailure { err ->
                    _state.update { it.copy(isGenerating = false, error = err.message) }
                }
        }
    }
}
