package com.jobai.companion.auth

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import com.jobai.companion.core.ui.theme.*

@Composable
fun WelcomeScreen(onStartPairing: () -> Unit) {
    Box(
        Modifier
            .fillMaxSize()
            .background(PairingBg),
        contentAlignment = Alignment.Center,
    ) {
        Column(
            Modifier
                .fillMaxWidth()
                .padding(horizontal = 32.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            Box(
                Modifier
                    .size(80.dp)
                    .clip(RoundedCornerShape(22.dp))
                    .background(Brush.linearGradient(listOf(Primary, Color(0xFF3B82F6)))),
                contentAlignment = Alignment.Center,
            ) {
                Text("AI", style = AppTypography.headlineMedium, color = Color.White)
            }
            Spacer(Modifier.height(24.dp))
            Text(
                "JobAI Companion",
                style = AppTypography.headlineLarge,
                color = Color.White,
                textAlign = TextAlign.Center,
            )
            Spacer(Modifier.height(8.dp))
            Text(
                "Connect to your VPS pipeline and manage your job search from anywhere.",
                style = AppTypography.bodyMedium,
                color = Color.White.copy(alpha = 0.6f),
                textAlign = TextAlign.Center,
            )
            Spacer(Modifier.height(40.dp))
            Button(
                onClick = onStartPairing,
                modifier = Modifier.fillMaxWidth().height(52.dp),
                shape = RoundedCornerShape(14.dp),
                colors = ButtonDefaults.buttonColors(containerColor = PairingAccent),
            ) {
                Text("Pair with Server", style = AppTypography.titleMedium, color = Color.White)
            }
            Spacer(Modifier.height(16.dp))
            Text(
                "Secured by Android Keystore · Ed25519 · TLS",
                style = AppTypography.labelSmall,
                color = Color.White.copy(alpha = 0.35f),
                textAlign = TextAlign.Center,
            )
        }
    }
}
