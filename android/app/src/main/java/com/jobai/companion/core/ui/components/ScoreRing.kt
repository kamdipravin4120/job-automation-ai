package com.jobai.companion.core.ui.components

import androidx.compose.foundation.Canvas
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.Stroke
import com.jobai.companion.core.ui.theme.Border
import com.jobai.companion.core.ui.theme.ScoreHigh
import com.jobai.companion.core.ui.theme.ScoreLow
import com.jobai.companion.core.ui.theme.ScoreMid

fun scoreColor(score: Float) = when {
    score >= 75f -> ScoreHigh
    score >= 50f -> ScoreMid
    else -> ScoreLow
}

@Composable
fun ScoreRing(score: Float, modifier: Modifier = Modifier) {
    val color = scoreColor(score)
    val sweep = (score / 100f) * 360f
    Canvas(modifier = modifier) {
        val strokeWidth = size.minDimension * 0.12f
        val inset = strokeWidth / 2f
        val arcSize = Size(size.width - strokeWidth, size.height - strokeWidth)
        val topLeft = Offset(inset, inset)
        drawArc(
            color = Border,
            startAngle = -90f,
            sweepAngle = 360f,
            useCenter = false,
            topLeft = topLeft,
            size = arcSize,
            style = Stroke(width = strokeWidth),
        )
        if (score > 0f) {
            drawArc(
                color = color,
                startAngle = -90f,
                sweepAngle = sweep,
                useCenter = false,
                topLeft = topLeft,
                size = arcSize,
                style = Stroke(width = strokeWidth, cap = StrokeCap.Round),
            )
        }
    }
}
