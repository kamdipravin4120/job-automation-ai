package com.jobai.companion.settings

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.jobai.companion.core.api.JobAiService
import com.jobai.companion.core.api.SavedSearchDto
import com.jobai.companion.core.api.SearchPatchDto
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import javax.inject.Inject

data class SearchesUiState(
    val searches: List<SavedSearchDto> = emptyList(),
    val isLoading: Boolean = false,
    val triggeringId: String? = null,
    val error: String? = null,
)

@HiltViewModel
class SearchesViewModel @Inject constructor(
    private val api: JobAiService,
) : ViewModel() {

    private val _state = MutableStateFlow(SearchesUiState())
    val uiState: StateFlow<SearchesUiState> = _state.asStateFlow()

    init { load() }

    fun load() {
        viewModelScope.launch {
            _state.update { it.copy(isLoading = true, error = null) }
            runCatching { api.listSearches() }
                .onSuccess { list -> _state.update { it.copy(searches = list, isLoading = false) } }
                .onFailure { err -> _state.update { it.copy(isLoading = false, error = err.message) } }
        }
    }

    fun create(keywords: String, location: String) {
        viewModelScope.launch {
            runCatching {
                api.createSearch(SavedSearchDto(keywords = keywords, location = location))
            }.onSuccess { load() }
             .onFailure { err -> _state.update { it.copy(error = err.message) } }
        }
    }

    fun toggleEnabled(search: SavedSearchDto) {
        viewModelScope.launch {
            runCatching {
                api.updateSearch(search.id, SearchPatchDto(enabled = !search.enabled))
            }.onSuccess { updated ->
                _state.update { s ->
                    s.copy(searches = s.searches.map { if (it.id == updated.id) updated else it })
                }
            }.onFailure { err -> _state.update { it.copy(error = err.message) } }
        }
    }

    fun delete(id: String) {
        viewModelScope.launch {
            runCatching { api.deleteSearch(id) }
                .onSuccess { _state.update { s -> s.copy(searches = s.searches.filter { it.id != id }) } }
                .onFailure { err -> _state.update { it.copy(error = err.message) } }
        }
    }

    fun trigger(id: String) {
        viewModelScope.launch {
            _state.update { it.copy(triggeringId = id, error = null) }
            runCatching { api.triggerSearch(id) }
                .onSuccess { _state.update { it.copy(triggeringId = null) } }
                .onFailure { err -> _state.update { it.copy(triggeringId = null, error = err.message) } }
        }
    }
}
