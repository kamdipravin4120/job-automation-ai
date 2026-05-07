package com.jobai.companion.home

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.jobai.companion.core.ui.components.OfflineBanner
import com.jobai.companion.core.ui.theme.*

@Composable
fun HomeScreen(vm: HomeViewModel = hiltViewModel()) {
    val state by vm.uiState.collectAsStateWithLifecycle()

    Column(Modifier.fillMaxSize().background(Background)) {
        OfflineBanner(visible = state.isOffline, lastSyncLabel = state.lastSyncLabel)

        Column(
            Modifier
                .fillMaxSize()
                .verticalScroll(rememberScrollState())
                .padding(16.dp)
        ) {
            Text("Dashboard", style = AppTypography.headlineMedium, color = TextPrimary)
            Spacer(Modifier.height(16.dp))

            val dashboard = state.dashboard
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                KpiChip("Total Jobs", dashboard?.totalJobs?.toString() ?: "—", Modifier.weight(1f))
                KpiChip("Applied", dashboard?.appliedCount?.toString() ?: "—", Modifier.weight(1f))
                KpiChip(
                    "Match Avg",
                    dashboard?.avgScore?.let { "%.0f%%".format(it) } ?: "—",
                    Modifier.weight(1f)
                )
            }

            Spacer(Modifier.height(16.dp))

            Button(
                onClick = { vm.triggerScrape() },
                modifier = Modifier.fillMaxWidth().height(48.dp),
                shape = RoundedCornerShape(12.dp),
                colors = ButtonDefaults.buttonColors(containerColor = Primary),
            ) {
                Text("Trigger Scrape", style = AppTypography.titleMedium, color = Color.White)
            }

            if (state.isRefreshing) {
                Spacer(Modifier.height(16.dp))
                LinearProgressIndicator(Modifier.fillMaxWidth(), color = Primary)
            }
        }
    }
}

@Composable
private fun KpiChip(label: String, value: String, modifier: Modifier = Modifier) {
    Card(
        modifier = modifier,
        shape = RoundedCornerShape(12.dp),
        colors = CardDefaults.cardColors(containerColor = Surface),
        elevation = CardDefaults.cardElevation(defaultElevation = 1.dp),
    ) {
        Column(Modifier.padding(12.dp), horizontalAlignment = Alignment.CenterHorizontally) {
            Text(value, style = AppTypography.titleLarge, color = Primary)
            Text(label, style = AppTypography.labelSmall, color = TextMuted)
        }
    }
}
