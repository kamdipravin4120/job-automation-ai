package com.jobai.companion.runs

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
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.jobai.companion.core.model.Run
import com.jobai.companion.core.ui.components.StatusBadge
import com.jobai.companion.core.ui.theme.*
import java.time.ZoneId
import java.time.format.DateTimeFormatter

private val runDateFmt = DateTimeFormatter.ofPattern("MMM d, HH:mm").withZone(ZoneId.systemDefault())

@Composable
fun RunsScreen(
    onOpenDlq: () -> Unit,
    vm: RunsViewModel = hiltViewModel(),
) {
    val state by vm.uiState.collectAsStateWithLifecycle()

    Box(Modifier.fillMaxSize().background(Background)) {
        Column(Modifier.fillMaxSize()) {
            Text(
                "Pipeline Runs",
                style = AppTypography.headlineMedium,
                color = TextPrimary,
                modifier = Modifier.padding(16.dp),
            )
            if (state.isRefreshing) LinearProgressIndicator(Modifier.fillMaxWidth(), color = Primary)
            LazyColumn(
                contentPadding = PaddingValues(horizontal = 16.dp, vertical = 8.dp),
                verticalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                items(state.runs, key = { it.id }) { run ->
                    RunRow(
                        run = run,
                        isExpanded = state.selectedRunId == run.id,
                        errorCode = if (state.selectedRunId == run.id) state.selectedDetail?.errorCode else null,
                        onTap = { vm.toggleDetail(run.id) },
                    )
                }
            }
        }

        Column(
            Modifier.align(Alignment.BottomEnd).padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
            horizontalAlignment = Alignment.End,
        ) {
            SmallFloatingActionButton(
                onClick = onOpenDlq,
                containerColor = ScoreLow,
            ) { Text("!", color = Color.White, style = AppTypography.titleMedium) }
            FloatingActionButton(
                onClick = { vm.triggerRun() },
                containerColor = Primary,
            ) {
                Text(if (state.triggerPending) "…" else "▶", color = Color.White)
            }
        }
    }
}

@Composable
private fun RunRow(run: Run, isExpanded: Boolean, errorCode: String?, onTap: () -> Unit) {
    Card(
        Modifier.fillMaxWidth().clickable(onClick = onTap),
        shape = RoundedCornerShape(12.dp),
        colors = CardDefaults.cardColors(containerColor = Surface),
        elevation = CardDefaults.cardElevation(defaultElevation = 1.dp),
    ) {
        Column(Modifier.padding(12.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Column(Modifier.weight(1f)) {
                    Text(run.kind.replaceFirstChar { it.uppercase() }, style = AppTypography.titleMedium, color = TextPrimary)
                    Text(runDateFmt.format(run.startedAt), style = AppTypography.bodyMedium, color = TextMuted)
                }
                if (run.jobsFound > 0) {
                    Surface(
                        shape = RoundedCornerShape(6.dp),
                        color = PrimarySurface,
                        modifier = Modifier.padding(end = 8.dp),
                    ) {
                        Text(
                            "${run.jobsFound} jobs",
                            style = AppTypography.labelSmall,
                            color = Primary,
                            modifier = Modifier.padding(horizontal = 6.dp, vertical = 2.dp),
                        )
                    }
                }
                StatusBadge(run.status)
            }
            if (isExpanded) {
                Spacer(Modifier.height(8.dp))
                HorizontalDivider(color = Border)
                Spacer(Modifier.height(8.dp))
                if (errorCode != null) {
                    Text("Error: $errorCode", style = AppTypography.bodySmall, color = ScoreLow)
                } else {
                    Text("No error details", style = AppTypography.bodySmall, color = TextDisabled)
                }
            }
        }
    }
}
