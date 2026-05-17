package com.jobai.companion.jobs

import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.jobai.companion.core.api.JobAiService
import com.jobai.companion.firebase.FcmEventBus
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.filter
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import javax.inject.Inject

data class JobDetailUiState(
    val jobId: String = "",
    val title: String = "",
    val company: String = "",
    val coverLetter: String? = null,
    val resumeText: String? = null,
    val isLoading: Boolean = true,
    val isGenerating: Boolean = false,
    val error: String? = null,
)

@HiltViewModel
class JobDetailViewModel @Inject constructor(
    private val api: JobAiService,
    savedStateHandle: SavedStateHandle,
) : ViewModel() {

    private val jobId: String = checkNotNull(savedStateHandle["jobId"])

    private val _state = MutableStateFlow(
        JobDetailUiState(
            jobId = jobId,
            title = savedStateHandle["title"] ?: "",
            company = savedStateHandle["company"] ?: "",
        )
    )
    val uiState: StateFlow<JobDetailUiState> = _state.asStateFlow()

    init {
        loadArtifacts()
        viewModelScope.launch {
            FcmEventBus.events
                .filter { it.kind == "tailor" && it.jobId == jobId }
                .collect { loadArtifacts() }
        }
    }

    fun loadArtifacts() {
        viewModelScope.launch {
            _state.update { it.copy(isLoading = true, error = null) }
            runCatching { api.getArtifacts(jobId) }
                .onSuccess { dto ->
                    _state.update {
                        it.copy(
                            coverLetter = dto.coverLetter,
                            resumeText = dto.resumeText,
                            isLoading = false,
                            isGenerating = false,
                        )
                    }
                }
                .onFailure { err ->
                    _state.update { it.copy(isLoading = false, error = err.message) }
                }
        }
    }

    fun triggerGeneration() {
        viewModelScope.launch {
            _state.update { it.copy(isGenerating = true, error = null) }
            runCatching { api.triggerTailor(jobId) }
                .onFailure { err ->
                    _state.update { it.copy(isGenerating = false, error = err.message) }
                }
            // FcmEventBus.events collector above calls loadArtifacts() when tailor completes
        }
    }
}
