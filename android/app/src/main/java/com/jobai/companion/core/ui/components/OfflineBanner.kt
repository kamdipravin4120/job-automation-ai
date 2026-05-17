package com.jobai.companion.core.ui.components

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.slideInVertically
import androidx.compose.animation.slideOutVertically
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import com.jobai.companion.core.ui.theme.AppTypography

@Composable
fun OfflineBanner(visible: Boolean, lastSyncLabel: String) {
    AnimatedVisibility(
        visible = visible,
        enter = slideInVertically { -it },
        exit = slideOutVertically { -it },
    ) {
        Box(
            Modifier
                .fillMaxWidth()
                .background(Color(0xFF92400E))
                .padding(8.dp),
            contentAlignment = Alignment.Center,
        ) {
            Text(
                text = "Offline · Last synced $lastSyncLabel",
                style = AppTypography.labelMedium,
                color = Color(0xFFFEF3C7),
            )
        }
    }
}
