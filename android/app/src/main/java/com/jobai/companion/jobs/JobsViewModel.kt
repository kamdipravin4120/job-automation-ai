package com.jobai.companion.jobs

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.jobai.companion.core.model.Job
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.*
import kotlinx.coroutines.launch
import javax.inject.Inject

data class JobsUiState(
    val jobs: List<Job> = emptyList(),
    val query: String = "",
    val isRefreshing: Boolean = false,
)

@HiltViewModel
class JobsViewModel @Inject constructor(
    private val repo: JobsRepository,
) : ViewModel() {

    private val _query = MutableStateFlow("")
    private val _isRefreshing = MutableStateFlow(false)

    val uiState: StateFlow<JobsUiState> = combine(
        repo.jobsFlow, _query, _isRefreshing
    ) { jobs, query, refreshing ->
        val filtered = if (query.isBlank()) jobs
        else jobs.filter {
            it.title.contains(query, ignoreCase = true) ||
            it.company.contains(query, ignoreCase = true)
        }
        JobsUiState(jobs = filtered, query = query, isRefreshing = refreshing)
    }.stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), JobsUiState())

    init { refresh() }

    fun onQueryChange(q: String) { _query.value = q }

    fun refresh() {
        viewModelScope.launch {
            _isRefreshing.value = true
            runCatching { repo.sync() }
            _isRefreshing.value = false
        }
    }

    fun star(jobId: String) { viewModelScope.launch { repo.star(jobId) } }
    fun dismiss(jobId: String) { viewModelScope.launch { repo.dismiss(jobId) } }
}
