package com.jobai.companion.navigation

import androidx.lifecycle.ViewModel
import com.jobai.companion.core.auth.SessionStore
import dagger.hilt.android.lifecycle.HiltViewModel
import javax.inject.Inject

@HiltViewModel
class AppNavigationViewModel @Inject constructor(
    val sessionStore: SessionStore,
) : ViewModel()
