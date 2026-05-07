package com.jobai.companion.auth

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import com.jobai.companion.core.ui.theme.*

@Composable
fun PairedScreen(deviceId: String, onEnterDashboard: () -> Unit) {
    Box(
        Modifier.fillMaxSize().background(PairingBg),
        contentAlignment = Alignment.Center,
    ) {
        Column(
            Modifier.fillMaxWidth().padding(32.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            Box(
                Modifier.size(80.dp).background(PairingSuccess.copy(alpha = 0.15f), CircleShape),
                contentAlignment = Alignment.Center,
            ) {
                Text("✓", style = AppTypography.headlineLarge, color = PairingSuccess)
            }
            Spacer(Modifier.height(24.dp))
            Text("You're in", style = AppTypography.headlineLarge, color = Color.White, textAlign = TextAlign.Center)
            Spacer(Modifier.height(8.dp))
            Text("Device registered", style = AppTypography.bodyMedium, color = Color.White.copy(0.6f))
            Spacer(Modifier.height(8.dp))
            Text(
                deviceId.take(16),
                style = AppTypography.bodyMedium.copy(fontFamily = FiraCodeFamily),
                color = PairingSuccess,
            )
            Spacer(Modifier.height(40.dp))
            Button(
                onClick = onEnterDashboard,
                modifier = Modifier.fillMaxWidth().height(52.dp),
                shape = RoundedCornerShape(14.dp),
                colors = ButtonDefaults.buttonColors(containerColor = PairingAccent),
            ) {
                Text("Enter Dashboard", style = AppTypography.titleMedium, color = Color.White)
            }
            Spacer(Modifier.height(16.dp))
            Text(
                "Private key secured in Android Keystore",
                style = AppTypography.labelSmall,
                color = Color.White.copy(0.35f),
                textAlign = TextAlign.Center,
            )
        }
    }
}
