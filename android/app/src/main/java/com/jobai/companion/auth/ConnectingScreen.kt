package com.jobai.companion.auth

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import com.jobai.companion.core.ui.theme.*

private val steps = listOf(
    "Bootstrap secret verified",
    "Ed25519 keypair generated",
    "Pairing with server",
    "Session token stored",
)

@Composable
fun ConnectingScreen(activeStep: Int, error: String?) {
    Box(
        Modifier.fillMaxSize().background(PairingBg),
        contentAlignment = Alignment.Center,
    ) {
        Column(
            Modifier.fillMaxWidth().padding(horizontal = 32.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            if (error == null) {
                CircularProgressIndicator(color = PairingAccent, modifier = Modifier.size(56.dp))
            }
            Spacer(Modifier.height(24.dp))
            Text(
                if (error != null) "Pairing failed" else "Connecting…",
                style = AppTypography.headlineMedium,
                color = if (error != null) Color(0xFFEF4444) else Color.White,
            )
            if (error != null) {
                Spacer(Modifier.height(8.dp))
                Text(error, style = AppTypography.bodyMedium, color = Color.White.copy(0.6f))
            }
            Spacer(Modifier.height(32.dp))
            steps.forEachIndexed { i, label ->
                Row(
                    Modifier.fillMaxWidth().padding(vertical = 6.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    val dotColor = when {
                        error != null && i == activeStep -> Color(0xFFEF4444)
                        i < activeStep -> PairingSuccess
                        i == activeStep -> PairingAccent
                        else -> Color.White.copy(0.2f)
                    }
                    Box(Modifier.size(16.dp).background(dotColor, CircleShape))
                    Spacer(Modifier.width(12.dp))
                    Text(
                        label,
                        style = AppTypography.bodyMedium,
                        color = if (i <= activeStep) Color.White else Color.White.copy(0.4f),
                    )
                }
            }
        }
    }
}
