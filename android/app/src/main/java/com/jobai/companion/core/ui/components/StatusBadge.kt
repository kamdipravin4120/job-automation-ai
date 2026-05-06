package com.jobai.companion.core.ui.components

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import com.jobai.companion.core.ui.theme.AppTypography
import com.jobai.companion.core.ui.theme.Primary
import com.jobai.companion.core.ui.theme.PrimarySurface

@Composable
fun StatusBadge(status: String, modifier: Modifier = Modifier) {
    val (bg, fg) = when (status.lowercase()) {
        "applied" -> Color(0xFFEFF6FF) to Color(0xFF1D4ED8)
        "screening", "screens" -> Color(0xFFFEF3C7) to Color(0xFFD97706)
        "interview" -> Color(0xFFFFEDD5) to Color(0xFFEA580C)
        "offer" -> Color(0xFFDCFCE7) to Color(0xFF15803D)
        "rejected", "closed" -> Color(0xFFFFF1F2) to Color(0xFFBE123C)
        "success" -> Color(0xFFDCFCE7) to Color(0xFF15803D)
        "failed", "error" -> Color(0xFFFFF1F2) to Color(0xFFBE123C)
        "running" -> PrimarySurface to Primary
        else -> Color(0xFFF1F5F9) to Color(0xFF475569)
    }
    Text(
        text = status.replaceFirstChar { it.uppercase() },
        style = AppTypography.labelSmall,
        color = fg,
        modifier = modifier
            .background(bg, RoundedCornerShape(6.dp))
            .padding(horizontal = 8.dp, vertical = 3.dp),
    )
}
