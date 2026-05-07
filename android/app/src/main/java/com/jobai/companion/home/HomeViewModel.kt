package com.jobai.companion.home

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.*
import kotlinx.coroutines.launch
import javax.inject.Inject

data class HomeUiState(
    val dashboard: DashboardState? = null,
    val isRefreshing: Boolean = false,
    val isOffline: Boolean = false,
    val lastSyncLabel: String = "",
)

@HiltViewModel
class HomeViewModel @Inject constructor(
    private val repo: HomeRepository,
) : ViewModel() {

    private val _isRefreshing = MutableStateFlow(false)

    val uiState: StateFlow<HomeUiState> = repo.dashboardFlow
        .combine(_isRefreshing) { dashboard, refreshing ->
            HomeUiState(dashboard = dashboard, isRefreshing = refreshing)
        }
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), HomeUiState())

    init { refresh() }

    fun refresh() {
        viewModelScope.launch {
            _isRefreshing.value = true
            runCatching { repo.sync() }
            _isRefreshing.value = false
        }
    }

    fun triggerScrape() {
        viewModelScope.launch { runCatching { repo.triggerScrape() } }
    }
}
