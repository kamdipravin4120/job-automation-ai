package com.jobai.companion.jobs

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.jobai.companion.core.model.Job
import com.jobai.companion.core.ui.components.JobCard
import com.jobai.companion.core.ui.theme.*

@Composable
fun JobsScreen(
    onJobClick: (Job) -> Unit = {},
    vm: JobsViewModel = hiltViewModel(),
) {
    val state by vm.uiState.collectAsStateWithLifecycle()

    Column(Modifier.fillMaxSize().background(Background)) {
        OutlinedTextField(
            value = state.query,
            onValueChange = { vm.onQueryChange(it) },
            modifier = Modifier.fillMaxWidth().padding(16.dp),
            placeholder = { Text("Search jobs…", color = TextDisabled) },
            shape = RoundedCornerShape(12.dp),
            singleLine = true,
        )

        if (state.isRefreshing) LinearProgressIndicator(Modifier.fillMaxWidth(), color = Primary)

        if (state.jobs.isEmpty() && !state.isRefreshing) {
            Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                Column(horizontalAlignment = Alignment.CenterHorizontally) {
                    Text("No jobs yet", style = AppTypography.titleMedium, color = TextMuted)
                    Spacer(Modifier.height(8.dp))
                    Text("Trigger a scrape from Dashboard", style = AppTypography.bodyMedium, color = TextDisabled)
                }
            }
        } else {
            LazyColumn(
                contentPadding = PaddingValues(horizontal = 16.dp, vertical = 8.dp),
                verticalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                items(state.jobs, key = { it.id }) { job ->
                    Box(Modifier.clickable { onJobClick(job) }) {
                        JobCard(
                            job = job,
                            onStar = { vm.star(job.id) },
                            onDismiss = { vm.dismiss(job.id) },
                        )
                    }
                }
            }
        }
    }
}
