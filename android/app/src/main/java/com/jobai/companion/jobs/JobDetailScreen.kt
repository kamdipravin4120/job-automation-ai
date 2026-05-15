package com.jobai.companion.jobs

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.jobai.companion.core.ui.theme.AppTypography
import com.jobai.companion.core.ui.theme.Background
import com.jobai.companion.core.ui.theme.Primary
import com.jobai.companion.core.ui.theme.Surface
import com.jobai.companion.core.ui.theme.TextDisabled
import com.jobai.companion.core.ui.theme.TextMuted
import com.jobai.companion.core.ui.theme.TextPrimary

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun JobDetailScreen(
    onBack: () -> Unit,
    vm: JobDetailViewModel = hiltViewModel(),
) {
    val state by vm.uiState.collectAsStateWithLifecycle()

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Text(state.title, style = AppTypography.titleMedium, color = TextPrimary)
                },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.Default.ArrowBack, contentDescription = "Back")
                    }
                },
            )
        }
    ) { padding ->
        Column(
            Modifier
                .fillMaxSize()
                .background(Background)
                .padding(padding)
                .verticalScroll(rememberScrollState())
                .padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp),
        ) {
            Text(state.company, style = AppTypography.bodyLarge, color = TextMuted)

            if (state.isLoading) {
                Box(Modifier.fillMaxWidth(), contentAlignment = Alignment.Center) {
                    CircularProgressIndicator(color = Primary)
                }
            } else {
                ArtifactSection(
                    title = "Cover Letter",
                    content = state.coverLetter,
                    isGenerating = state.isGenerating,
                    onGenerate = { vm.triggerGeneration() },
                )
                HorizontalDivider()
                ArtifactSection(
                    title = "Tailored Resume",
                    content = state.resumeText,
                    isGenerating = state.isGenerating,
                    onGenerate = null,
                )
                state.error?.let {
                    Text(it, color = MaterialTheme.colorScheme.error, style = AppTypography.bodyMedium)
                }
            }
        }
    }
}

@Composable
private fun ArtifactSection(
    title: String,
    content: String?,
    isGenerating: Boolean,
    onGenerate: (() -> Unit)?,
) {
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Text(title, style = AppTypography.labelMedium, color = TextPrimary)
        when {
            content != null -> Card(
                shape = RoundedCornerShape(8.dp),
                colors = CardDefaults.cardColors(containerColor = Surface),
            ) {
                Text(
                    content,
                    modifier = Modifier.padding(12.dp),
                    style = AppTypography.bodyMedium,
                    color = TextMuted,
                )
            }
            isGenerating -> Row(
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                CircularProgressIndicator(
                    modifier = Modifier.size(16.dp),
                    color = Primary,
                    strokeWidth = 2.dp,
                )
                Text("Generating…", style = AppTypography.bodyMedium, color = TextMuted)
            }
            onGenerate != null -> Button(onClick = onGenerate) { Text("Generate") }
            else -> Text("Not yet generated", style = AppTypography.bodyMedium, color = TextDisabled)
        }
    }
}
