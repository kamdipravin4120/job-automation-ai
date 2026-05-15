package com.jobai.companion.tracker

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
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
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.jobai.companion.core.api.BriefingItemDto
import com.jobai.companion.core.api.RecruiterDto
import com.jobai.companion.core.ui.components.StatusBadge
import com.jobai.companion.core.ui.theme.AppTypography
import com.jobai.companion.core.ui.theme.Background
import com.jobai.companion.core.ui.theme.Primary
import com.jobai.companion.core.ui.theme.Surface
import com.jobai.companion.core.ui.theme.TextMuted
import com.jobai.companion.core.ui.theme.TextPrimary

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ApplicationDetailScreen(
    onBack: () -> Unit,
    vm: ApplicationDetailViewModel = hiltViewModel(),
) {
    val state by vm.uiState.collectAsStateWithLifecycle()

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Text(
                        state.title.ifBlank { "Application" },
                        style = AppTypography.titleMedium,
                        color = TextPrimary,
                    )
                },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.Default.ArrowBack, contentDescription = "Back")
                    }
                },
            )
        }
    ) { padding ->
        if (state.isLoading) {
            Box(
                Modifier.fillMaxSize().padding(padding),
                contentAlignment = Alignment.Center,
            ) {
                CircularProgressIndicator(color = Primary)
            }
        } else {
            LazyColumn(
                Modifier
                    .fillMaxSize()
                    .background(Background)
                    .padding(padding),
                contentPadding = PaddingValues(16.dp),
                verticalArrangement = Arrangement.spacedBy(12.dp),
            ) {
                item {
                    Row(
                        horizontalArrangement = Arrangement.spacedBy(8.dp),
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        StatusBadge(state.currentStatus)
                        if (state.emailStatus == "follow_up_needed") {
                            Box(
                                modifier = Modifier
                                    .background(Color(0xFFFF6B35), RoundedCornerShape(4.dp))
                                    .padding(horizontal = 8.dp, vertical = 2.dp),
                            ) {
                                Text(
                                    "Follow Up",
                                    style = AppTypography.labelSmall,
                                    color = Color.White,
                                )
                            }
                        }
                    }
                }
                state.recruiter?.let { recruiter ->
                    item { RecruiterCard(recruiter, state.lastContactAt) }
                }
                item {
                    Text("Interview Prep", style = AppTypography.titleMedium, color = TextPrimary)
                }
                if (state.briefingItems.isEmpty()) {
                    item {
                        if (state.isGenerating) {
                            Row(
                                verticalAlignment = Alignment.CenterVertically,
                                horizontalArrangement = Arrangement.spacedBy(8.dp),
                            ) {
                                CircularProgressIndicator(
                                    modifier = Modifier.size(20.dp),
                                    color = Primary,
                                )
                                Text("Generating…", style = AppTypography.bodyMedium, color = TextMuted)
                            }
                        } else {
                            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                                Text(
                                    "No interview brief yet.",
                                    style = AppTypography.bodyMedium,
                                    color = TextMuted,
                                )
                                Button(onClick = { vm.generateBrief() }) {
                                    Text("Generate Interview Brief")
                                }
                            }
                        }
                    }
                } else {
                    items(state.briefingItems) { item -> BriefingCard(item) }
                }
                state.error?.let {
                    item {
                        Text(it, color = MaterialTheme.colorScheme.error, style = AppTypography.bodySmall)
                    }
                }
            }
        }
    }
}

@Composable
private fun RecruiterCard(recruiter: RecruiterDto, lastContactAt: String?) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(8.dp),
        colors = CardDefaults.cardColors(containerColor = Surface),
        elevation = CardDefaults.cardElevation(defaultElevation = 1.dp),
    ) {
        Column(
            Modifier.padding(12.dp),
            verticalArrangement = Arrangement.spacedBy(4.dp),
        ) {
            Text("Recruiter", style = AppTypography.titleSmall, color = TextPrimary)
            recruiter.name?.let {
                Text(it, style = AppTypography.bodyMedium, color = TextPrimary)
            }
            recruiter.email?.let {
                Text(it, style = AppTypography.bodySmall, color = TextMuted)
            }
            recruiter.company?.let {
                Text(it, style = AppTypography.bodySmall, color = TextMuted)
            }
            lastContactAt?.let {
                val date = it.substringBefore("T")
                Text("Last contact: $date", style = AppTypography.labelSmall, color = TextMuted)
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun BriefingCard(item: BriefingItemDto) {
    var expanded by remember { mutableStateOf(false) }
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(8.dp),
        colors = CardDefaults.cardColors(containerColor = Surface),
        elevation = CardDefaults.cardElevation(defaultElevation = 1.dp),
        onClick = { expanded = !expanded },
    ) {
        Column(
            Modifier.padding(12.dp),
            verticalArrangement = Arrangement.spacedBy(6.dp),
        ) {
            Text(item.question, style = AppTypography.titleSmall, color = TextPrimary)
            Text(item.rationale, style = AppTypography.bodySmall, color = TextMuted)
            if (expanded) {
                HorizontalDivider(Modifier.padding(vertical = 4.dp))
                item.starPoints.forEach { point ->
                    Text("• $point", style = AppTypography.bodySmall, color = TextPrimary)
                }
            }
        }
    }
}
