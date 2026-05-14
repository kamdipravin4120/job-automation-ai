package com.jobai.companion.settings

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalUriHandler
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.jobai.companion.core.ui.theme.*

@Composable
fun SettingsScreen(
    onUnpaired: () -> Unit,
    vm: SettingsViewModel = hiltViewModel(),
) {
    val state by vm.uiState.collectAsStateWithLifecycle()
    val uriHandler = LocalUriHandler.current
    var showUnpairDialog by remember { mutableStateOf(false) }

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

        Spacer(Modifier.weight(1f))

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
