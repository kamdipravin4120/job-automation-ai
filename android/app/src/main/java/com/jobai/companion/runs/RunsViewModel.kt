package com.jobai.companion.runs

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.jobai.companion.core.model.Run
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.*
import kotlinx.coroutines.launch
import javax.inject.Inject

data class RunsUiState(
    val runs: List<Run> = emptyList(),
    val isRefreshing: Boolean = false,
    val triggerPending: Boolean = false,
)

@HiltViewModel
class RunsViewModel @Inject constructor(
    private val repo: RunsRepository,
) : ViewModel() {

    private val _isRefreshing = MutableStateFlow(false)
    private val _triggerPending = MutableStateFlow(false)

    val uiState: StateFlow<RunsUiState> = combine(
        repo.runsFlow, _isRefreshing, _triggerPending
    ) { runs, refreshing, trigger ->
        RunsUiState(runs = runs, isRefreshing = refreshing, triggerPending = trigger)
    }.stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), RunsUiState())

    init { refresh() }

    fun refresh() {
        viewModelScope.launch {
            _isRefreshing.value = true
            runCatching { repo.sync() }
            _isRefreshing.value = false
        }
    }

    fun triggerRun() {
        viewModelScope.launch {
            _triggerPending.value = true
            runCatching { repo.triggerRun() }
            _triggerPending.value = false
            refresh()
        }
    }
}
