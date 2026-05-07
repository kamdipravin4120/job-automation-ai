package com.jobai.companion.tracker

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.jobai.companion.core.model.Application
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.*
import kotlinx.coroutines.launch
import javax.inject.Inject

enum class TrackerTab { Applied, Screens, Interview, Closed }

data class TrackerUiState(
    val applications: List<Application> = emptyList(),
    val activeTab: TrackerTab = TrackerTab.Applied,
    val isRefreshing: Boolean = false,
)

@HiltViewModel
class TrackerViewModel @Inject constructor(
    private val repo: TrackerRepository,
) : ViewModel() {

    private val _tab = MutableStateFlow(TrackerTab.Applied)
    private val _isRefreshing = MutableStateFlow(false)

    val uiState: StateFlow<TrackerUiState> = combine(
        repo.applicationsFlow, _tab, _isRefreshing
    ) { apps, tab, refreshing ->
        val filtered = apps.filter { app ->
            when (tab) {
                TrackerTab.Applied -> app.currentStatus == "applied"
                TrackerTab.Screens -> app.currentStatus == "screening"
                TrackerTab.Interview -> app.currentStatus == "interview"
                TrackerTab.Closed -> app.currentStatus in listOf("rejected", "offer", "withdrawn")
            }
        }
        TrackerUiState(applications = filtered, activeTab = tab, isRefreshing = refreshing)
    }.stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), TrackerUiState())

    init { refresh() }

    fun selectTab(tab: TrackerTab) { _tab.value = tab }

    fun refresh() {
        viewModelScope.launch {
            _isRefreshing.value = true
            runCatching { repo.sync() }
            _isRefreshing.value = false
        }
    }
}
