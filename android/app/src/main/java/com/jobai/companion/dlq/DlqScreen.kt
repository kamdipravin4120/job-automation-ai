package com.jobai.companion.dlq

import androidx.compose.foundation.background
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
import com.jobai.companion.core.ui.theme.*
import java.time.ZoneId
import java.time.format.DateTimeFormatter

private val dlqDateFmt = DateTimeFormatter.ofPattern("MMM d, HH:mm").withZone(ZoneId.systemDefault())

@Composable
fun DlqScreen(onBack: () -> Unit, vm: DlqViewModel = hiltViewModel()) {
    val state by vm.uiState.collectAsStateWithLifecycle()

    Column(Modifier.fillMaxSize().background(Background)) {
        Row(
            Modifier.fillMaxWidth().padding(16.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            TextButton(onClick = onBack) { Text("← Back", color = Primary) }
            Spacer(Modifier.width(8.dp))
            Text("Failed Runs", style = AppTypography.headlineMedium, color = TextPrimary)
        }

        if (state.isRefreshing) LinearProgressIndicator(Modifier.fillMaxWidth(), color = Primary)

        if (state.items.isEmpty() && !state.isRefreshing) {
            Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                Text("No failed runs", style = AppTypography.titleMedium, color = TextMuted)
            }
        } else {
            LazyColumn(
                contentPadding = PaddingValues(16.dp),
                verticalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                items(state.items, key = { it.id }) { item ->
                    DlqCard(item, onRetry = { vm.retry(item.id) }, onDismiss = { vm.dismiss(item.id) })
                }
            }
        }
    }
}

@Composable
private fun DlqCard(item: DlqItem, onRetry: () -> Unit, onDismiss: () -> Unit) {
    Card(
        Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(12.dp),
        colors = CardDefaults.cardColors(containerColor = Surface),
        elevation = CardDefaults.cardElevation(defaultElevation = 1.dp),
    ) {
        Column(Modifier.padding(12.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Column(Modifier.weight(1f)) {
                    Text(item.kind.replaceFirstChar { it.uppercase() }, style = AppTypography.titleMedium, color = TextPrimary)
                    item.errorCode?.let {
                        Text(it, style = AppTypography.bodySmall, color = ScoreLow)
                    }
                    item.startedAt?.let {
                        Text(dlqDateFmt.format(it), style = AppTypography.labelSmall, color = TextDisabled)
                    }
                }
                Text("× ${item.retryCount}", style = AppTypography.labelSmall, color = TextMuted)
            }
            Spacer(Modifier.height(8.dp))
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedButton(
                    onClick = onRetry,
                    modifier = Modifier.weight(1f),
                    shape = RoundedCornerShape(8.dp),
                ) { Text("Retry", color = Primary) }
                OutlinedButton(
                    onClick = onDismiss,
                    modifier = Modifier.weight(1f),
                    shape = RoundedCornerShape(8.dp),
                ) { Text("Dismiss", color = TextMuted) }
            }
        }
    }
}
