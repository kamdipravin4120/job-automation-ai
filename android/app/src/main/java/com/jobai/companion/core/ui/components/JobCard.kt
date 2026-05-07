package com.jobai.companion.core.ui.components

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import com.jobai.companion.core.model.Job
import com.jobai.companion.core.ui.theme.*

@Composable
fun JobCard(
    job: Job,
    onStar: () -> Unit,
    onDismiss: () -> Unit,
    modifier: Modifier = Modifier,
) {
    Card(
        modifier = modifier.fillMaxWidth(),
        shape = RoundedCornerShape(12.dp),
        colors = CardDefaults.cardColors(containerColor = Surface),
        elevation = CardDefaults.cardElevation(defaultElevation = 1.dp),
    ) {
        Row(Modifier.padding(12.dp), verticalAlignment = Alignment.CenterVertically) {
            Box(
                Modifier.size(40.dp).background(PrimarySurface, CircleShape),
                contentAlignment = Alignment.Center,
            ) {
                Text(
                    job.company.take(1).uppercase(),
                    style = AppTypography.titleMedium,
                    color = Primary,
                )
            }
            Spacer(Modifier.width(12.dp))
            Column(Modifier.weight(1f)) {
                Text(job.title, style = AppTypography.titleMedium, color = TextPrimary, maxLines = 1)
                Text(
                    "${job.company}${job.location?.let { " · $it" } ?: ""}",
                    style = AppTypography.bodyMedium,
                    color = TextMuted,
                    maxLines = 1,
                )
                Spacer(Modifier.height(4.dp))
                StatusBadge(job.status)
            }
            Spacer(Modifier.width(8.dp))
            Column(horizontalAlignment = Alignment.CenterHorizontally) {
                Box(Modifier.size(36.dp), contentAlignment = Alignment.Center) {
                    ScoreRing(score = job.matchScore ?: 0f, modifier = Modifier.fillMaxSize())
                    Text(
                        job.matchScore?.let { "%.0f".format(it) } ?: "—",
                        style = AppTypography.labelSmall,
                        color = job.matchScore?.let { scoreColor(it) } ?: TextDisabled,
                    )
                }
                Spacer(Modifier.height(4.dp))
                IconButton(onClick = onStar, modifier = Modifier.size(24.dp)) {
                    Text(if (job.starred) "★" else "☆", color = if (job.starred) Accent else TextDisabled)
                }
            }
        }
    }
}
