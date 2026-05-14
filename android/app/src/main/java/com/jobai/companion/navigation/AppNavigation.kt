package com.jobai.companion.navigation

import androidx.compose.foundation.layout.padding
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.navigation.NavDestination.Companion.hierarchy
import androidx.navigation.NavGraph.Companion.findStartDestination
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.rememberNavController
import com.jobai.companion.auth.*
import com.jobai.companion.dlq.DlqScreen
import com.jobai.companion.home.HomeScreen
import com.jobai.companion.jobs.JobsScreen
import com.jobai.companion.runs.RunsScreen
import com.jobai.companion.tracker.TrackerScreen

sealed class Screen(val route: String) {
    object Welcome : Screen("welcome")
    object QrScan : Screen("qr_scan")
    object Connecting : Screen("connecting")
    object Paired : Screen("paired")
    object Home : Screen("home")
    object Jobs : Screen("jobs")
    object Tracker : Screen("tracker")
    object Runs : Screen("runs")
    object More : Screen("more")
    object Dlq : Screen("dlq")
}

@Composable
fun AppNavigation(
    navVm: AppNavigationViewModel = hiltViewModel(),
) {
    val navController = rememberNavController()
    val startDestination = if (navVm.sessionStore.isPaired) Screen.Home.route else Screen.Welcome.route

    val pairingVm: PairingViewModel = hiltViewModel()
    val pairingState by pairingVm.state.collectAsStateWithLifecycle()

    LaunchedEffect(pairingState) {
        when (pairingState) {
            is PairingState.Scanning -> navController.navigate(Screen.QrScan.route)
            is PairingState.Connecting -> if (navController.currentDestination?.route != Screen.Connecting.route)
                navController.navigate(Screen.Connecting.route)
            is PairingState.Paired -> navController.navigate(Screen.Paired.route) {
                popUpTo(Screen.Welcome.route) { inclusive = true }
            }
            else -> {}
        }
    }

    val bottomTabs = listOf(
        Screen.Home to "Home",
        Screen.Jobs to "Jobs",
        Screen.Tracker to "Applied",
        Screen.Runs to "Runs",
        Screen.More to "More",
    )

    val navBackStackEntry by navController.currentBackStackEntryAsState()
    val showBottomBar = navBackStackEntry?.destination?.route in listOf(
        Screen.Home.route, Screen.Jobs.route, Screen.Tracker.route, Screen.Runs.route, Screen.More.route,
    )

    Scaffold(
        bottomBar = {
            if (showBottomBar) {
                NavigationBar(containerColor = Color.White) {
                    val currentDestination = navBackStackEntry?.destination
                    bottomTabs.forEach { (screen, label) ->
                        NavigationBarItem(
                            selected = currentDestination?.hierarchy?.any { it.route == screen.route } == true,
                            onClick = {
                                navController.navigate(screen.route) {
                                    popUpTo(navController.graph.findStartDestination().id) { saveState = true }
                                    launchSingleTop = true
                                    restoreState = true
                                }
                            },
                            icon = { Text(label.take(1)) },
                            label = { Text(label) },
                            colors = NavigationBarItemDefaults.colors(indicatorColor = Color(0xFFEFF6FF)),
                        )
                    }
                }
            }
        }
    ) { innerPadding ->
        NavHost(
            navController = navController,
            startDestination = startDestination,
            modifier = Modifier.padding(innerPadding),
        ) {
            composable(Screen.Welcome.route) {
                WelcomeScreen(onStartPairing = { pairingVm.startScan() })
            }
            composable(Screen.QrScan.route) {
                QrScanScreen(
                    onScanned = { pairingVm.onQrScanned(it) },
                    onBack = { navController.popBackStack() },
                )
            }
            composable(Screen.Connecting.route) {
                val state = pairingState
                ConnectingScreen(
                    activeStep = if (state is PairingState.Connecting) state.step else 0,
                    error = if (state is PairingState.Failed) state.error else null,
                )
            }
            composable(Screen.Paired.route) {
                val state = pairingState
                PairedScreen(
                    deviceId = if (state is PairingState.Paired) state.deviceId else "",
                    onEnterDashboard = {
                        navController.navigate(Screen.Home.route) {
                            popUpTo(0) { inclusive = true }
                        }
                    },
                )
            }
            composable(Screen.Home.route) { HomeScreen() }
            composable(Screen.Jobs.route) { JobsScreen() }
            composable(Screen.Tracker.route) { TrackerScreen() }
            composable(Screen.Runs.route) { RunsScreen() }
            composable(Screen.More.route) {
                Text("Settings coming in SP3")
            }
            composable(Screen.Dlq.route) {
                DlqScreen(onBack = { navController.popBackStack() })
            }
        }
    }
}
