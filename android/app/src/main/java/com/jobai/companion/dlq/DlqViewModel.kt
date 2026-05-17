package com.jobai.companion.dlq

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.*
import kotlinx.coroutines.launch
import javax.inject.Inject

data class DlqUiState(
    val items: List<DlqItem> = emptyList(),
    val isRefreshing: Boolean = false,
)

@HiltViewModel
class DlqViewModel @Inject constructor(
    private val repo: DlqRepository,
) : ViewModel() {

    private val _isRefreshing = MutableStateFlow(false)

    val uiState: StateFlow<DlqUiState> = combine(repo.dlqFlow, _isRefreshing) { items, refreshing ->
        DlqUiState(items = items, isRefreshing = refreshing)
    }.stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), DlqUiState())

    init { refresh() }

    fun refresh() {
        viewModelScope.launch {
            _isRefreshing.value = true
            runCatching { repo.sync() }
            _isRefreshing.value = false
        }
    }

    fun retry(itemId: String) {
        viewModelScope.launch { runCatching { repo.retry(itemId) } }
    }

    fun dismiss(itemId: String) {
        viewModelScope.launch { runCatching { repo.dismiss(itemId) } }
    }
}
