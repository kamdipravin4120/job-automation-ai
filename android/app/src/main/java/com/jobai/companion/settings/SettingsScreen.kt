package com.jobai.companion.settings

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalUriHandler
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.jobai.companion.core.api.SavedSearchDto
import com.jobai.companion.core.ui.theme.*

@Composable
fun SettingsScreen(
    onUnpaired: () -> Unit,
    vm: SettingsViewModel = hiltViewModel(),
    searchesVm: SearchesViewModel = hiltViewModel(),
) {
    val state by vm.uiState.collectAsStateWithLifecycle()
    val searchesState by searchesVm.uiState.collectAsStateWithLifecycle()
    val uriHandler = LocalUriHandler.current
    var showUnpairDialog by remember { mutableStateOf(false) }
    var showAddSearchDialog by remember { mutableStateOf(false) }

    LaunchedEffect(state.navigateToWelcome) {
        if (state.navigateToWelcome) {
            vm.onNavigatedToWelcome()
            onUnpaired()
        }
    }

    Column(
        Modifier
            .fillMaxSize()
            .background(Background)
            .verticalScroll(rememberScrollState())
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp),
    ) {
        Text("Settings", style = AppTypography.headlineMedium, color = TextPrimary)

        SectionCard(title = "Device") {
            LabelValue("Server", state.serverUrl)
            LabelValue("Device ID", state.deviceId.take(16), monospace = true)
        }

        SectionCard(title = "Gmail") {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(
                    if (state.gmailAuthorized) "Connected" else "Not connected",
                    style = AppTypography.bodyMedium,
                    color = if (state.gmailAuthorized) ScoreHigh else TextMuted,
                    modifier = Modifier.weight(1f),
                )
                if (!state.gmailAuthorized) {
                    Button(
                        onClick = {
                            uriHandler.openUri("https://accounts.google.com/o/oauth2/device/code")
                            vm.startGmailOAuthPoll()
                        },
                        enabled = !state.isPollingGmail,
                        colors = ButtonDefaults.buttonColors(containerColor = Primary),
                        shape = RoundedCornerShape(8.dp),
                    ) { Text(if (state.isPollingGmail) "Waiting…" else "Connect", color = Color.White) }
                }
            }
            if (state.gmailPollTimedOut) {
                Text("OAuth timed out — try again", style = AppTypography.labelSmall, color = ScoreLow)
            }
        }

        SearchesSection(
            state = searchesState,
            onToggle = { searchesVm.toggleEnabled(it) },
            onDelete = { searchesVm.delete(it) },
            onTrigger = { searchesVm.trigger(it) },
            onAdd = { showAddSearchDialog = true },
        )

        Button(
            onClick = { showUnpairDialog = true },
            modifier = Modifier
                .fillMaxWidth()
                .height(48.dp),
            shape = RoundedCornerShape(12.dp),
            colors = ButtonDefaults.buttonColors(containerColor = ScoreLow),
            enabled = !state.isUnpairing,
        ) {
            Text(if (state.isUnpairing) "Unpairing…" else "Unpair Device", color = Color.White)
        }
    }

    if (showUnpairDialog) {
        AlertDialog(
            onDismissRequest = { showUnpairDialog = false },
            title = { Text("Unpair device?") },
            text = { Text("This clears your session and keys. You will need to scan a QR code to reconnect.") },
            confirmButton = {
                TextButton(onClick = { showUnpairDialog = false; vm.unpair() }) {
                    Text("Unpair", color = ScoreLow)
                }
            },
            dismissButton = {
                TextButton(onClick = { showUnpairDialog = false }) { Text("Cancel") }
            },
        )
    }

    if (showAddSearchDialog) {
        AddSearchDialog(
            onDismiss = { showAddSearchDialog = false },
            onAdd = { keywords, location ->
                searchesVm.create(keywords, location)
                showAddSearchDialog = false
            },
        )
    }
}

@Composable
private fun SectionCard(title: String, content: @Composable ColumnScope.() -> Unit) {
    Card(
        Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(12.dp),
        colors = CardDefaults.cardColors(containerColor = Surface),
        elevation = CardDefaults.cardElevation(defaultElevation = 1.dp),
    ) {
        Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text(title, style = AppTypography.labelMedium, color = TextMuted)
            content()
        }
    }
}

@Composable
private fun LabelValue(label: String, value: String, monospace: Boolean = false) {
    Row {
        Text("$label: ", style = AppTypography.bodyMedium, color = TextMuted)
        Text(
            value,
            style = if (monospace) AppTypography.bodyMedium.copy(fontFamily = FiraCodeFamily)
                    else AppTypography.bodyMedium,
            color = TextPrimary,
        )
    }
}

@Composable
private fun SearchesSection(
    state: SearchesUiState,
    onToggle: (SavedSearchDto) -> Unit,
    onDelete: (String) -> Unit,
    onTrigger: (String) -> Unit,
    onAdd: () -> Unit,
) {
    Card(
        Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(12.dp),
        colors = CardDefaults.cardColors(containerColor = Surface),
        elevation = CardDefaults.cardElevation(defaultElevation = 1.dp),
    ) {
        Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text("Job Searches", style = AppTypography.labelMedium, color = TextMuted, modifier = Modifier.weight(1f))
                IconButton(onClick = onAdd) {
                    Icon(Icons.Default.Add, contentDescription = "Add search", tint = Primary)
                }
            }
            if (state.isLoading) {
                LinearProgressIndicator(Modifier.fillMaxWidth(), color = Primary)
            }
            state.error?.let {
                Text(it, style = AppTypography.labelSmall, color = ScoreLow)
            }
            if (state.searches.isEmpty() && !state.isLoading) {
                Text("No saved searches yet.", style = AppTypography.bodyMedium, color = TextMuted)
            }
            state.searches.forEach { search ->
                SearchRow(
                    search = search,
                    isTriggering = state.triggeringId == search.id,
                    onToggle = { onToggle(search) },
                    onDelete = { onDelete(search.id) },
                    onTrigger = { onTrigger(search.id) },
                )
            }
        }
    }
}

@Composable
private fun SearchRow(
    search: SavedSearchDto,
    isTriggering: Boolean,
    onToggle: () -> Unit,
    onDelete: () -> Unit,
    onTrigger: () -> Unit,
) {
    Row(
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(4.dp),
    ) {
        Column(Modifier.weight(1f)) {
            Text(search.keywords, style = AppTypography.bodyMedium, color = TextPrimary)
            Text(search.location, style = AppTypography.bodySmall, color = TextMuted)
        }
        Switch(
            checked = search.enabled,
            onCheckedChange = { onToggle() },
            colors = SwitchDefaults.colors(checkedThumbColor = Primary, checkedTrackColor = Primary.copy(alpha = 0.5f)),
        )
        IconButton(onClick = onTrigger, enabled = !isTriggering) {
            if (isTriggering) {
                CircularProgressIndicator(Modifier.size(20.dp), color = Primary, strokeWidth = 2.dp)
            } else {
                Icon(Icons.Default.PlayArrow, contentDescription = "Run now", tint = Primary)
            }
        }
        IconButton(onClick = onDelete) {
            Icon(Icons.Default.Delete, contentDescription = "Delete", tint = ScoreLow)
        }
    }
}

@Composable
private fun AddSearchDialog(onDismiss: () -> Unit, onAdd: (String, String) -> Unit) {
    var keywords by remember { mutableStateOf("") }
    var location by remember { mutableStateOf("") }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Add Job Search") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedTextField(
                    value = keywords,
                    onValueChange = { keywords = it },
                    label = { Text("Keywords") },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth(),
                )
                OutlinedTextField(
                    value = location,
                    onValueChange = { location = it },
                    label = { Text("Location") },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth(),
                )
            }
        },
        confirmButton = {
            TextButton(
                onClick = { if (keywords.isNotBlank() && location.isNotBlank()) onAdd(keywords.trim(), location.trim()) },
            ) { Text("Add", color = Primary) }
        },
        dismissButton = {
            TextButton(onClick = onDismiss) { Text("Cancel") }
        },
    )
}
