package com.jobai.companion.tracker

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.jobai.companion.core.model.Application
import com.jobai.companion.core.ui.components.StatusBadge
import com.jobai.companion.core.ui.theme.*
import java.time.ZoneId
import java.time.format.DateTimeFormatter

private val dateFormatter = DateTimeFormatter.ofPattern("MMM d").withZone(ZoneId.systemDefault())

@Composable
fun TrackerScreen(vm: TrackerViewModel = hiltViewModel()) {
    val state by vm.uiState.collectAsStateWithLifecycle()

    Column(Modifier.fillMaxSize().background(Background)) {
        Text(
            "Applications",
            style = AppTypography.headlineMedium,
            color = TextPrimary,
            modifier = Modifier.padding(16.dp),
        )

        TabRow(
            selectedTabIndex = state.activeTab.ordinal,
            containerColor = Surface,
            contentColor = Primary,
        ) {
            TrackerTab.values().forEach { tab ->
                Tab(
                    selected = state.activeTab == tab,
                    onClick = { vm.selectTab(tab) },
                    text = { Text(tab.name, style = AppTypography.labelMedium) },
                )
            }
        }

        if (state.isRefreshing) LinearProgressIndicator(Modifier.fillMaxWidth(), color = Primary)

        LazyColumn(
            contentPadding = PaddingValues(16.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            items(state.applications, key = { it.id }) { app ->
                ApplicationCard(app)
            }
        }
    }
}

@Composable
private fun ApplicationCard(app: Application) {
    Card(
        Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(12.dp),
        colors = CardDefaults.cardColors(containerColor = Surface),
        elevation = CardDefaults.cardElevation(defaultElevation = 1.dp),
    ) {
        Row(Modifier.padding(12.dp)) {
            Column(Modifier.weight(1f)) {
                Text(app.jobTitle.ifBlank { "Job ${app.jobId.take(8)}" }, style = AppTypography.titleMedium, color = TextPrimary)
                Text(app.company.ifBlank { app.channel }, style = AppTypography.bodyMedium, color = TextMuted)
                Spacer(Modifier.height(4.dp))
                StatusBadge(app.currentStatus)
            }
            Text(
                dateFormatter.format(app.submittedAt),
                style = AppTypography.labelSmall,
                color = TextDisabled,
            )
        }
    }
}
