package com.jobai.companion.auth

import android.Manifest
import androidx.camera.core.CameraSelector
import androidx.camera.core.ImageAnalysis
import androidx.camera.core.Preview
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.camera.view.PreviewView
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Text
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalLifecycleOwner
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.core.content.ContextCompat
import com.google.accompanist.permissions.ExperimentalPermissionsApi
import com.google.accompanist.permissions.isGranted
import com.google.accompanist.permissions.rememberPermissionState
import com.google.mlkit.vision.barcode.BarcodeScannerOptions
import com.google.mlkit.vision.barcode.BarcodeScanning
import com.google.mlkit.vision.barcode.common.Barcode
import com.google.mlkit.vision.common.InputImage
import com.jobai.companion.core.ui.theme.*
import java.util.concurrent.Executors

@OptIn(ExperimentalPermissionsApi::class)
@Composable
fun QrScanScreen(onScanned: (String) -> Unit, onBack: () -> Unit) {
    val cameraPermission = rememberPermissionState(Manifest.permission.CAMERA)
    val context = LocalContext.current
    val lifecycleOwner = LocalLifecycleOwner.current
    var scanned by remember { mutableStateOf(false) }

    LaunchedEffect(Unit) {
        if (!cameraPermission.status.isGranted) cameraPermission.launchPermissionRequest()
    }

    Box(Modifier.fillMaxSize().background(Color(0xFF0A0A0A))) {
        if (cameraPermission.status.isGranted) {
            AndroidView(
                factory = { ctx ->
                    val previewView = PreviewView(ctx)
                    val cameraFuture = ProcessCameraProvider.getInstance(ctx)
                    cameraFuture.addListener({
                        val provider = cameraFuture.get()
                        val preview = Preview.Builder().build()
                            .also { it.setSurfaceProvider(previewView.surfaceProvider) }
                        val scanner = BarcodeScanning.getClient(
                            BarcodeScannerOptions.Builder()
                                .setBarcodeFormats(Barcode.FORMAT_QR_CODE)
                                .build()
                        )
                        val analysis = ImageAnalysis.Builder()
                            .setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST)
                            .build()
                        analysis.setAnalyzer(Executors.newSingleThreadExecutor()) { proxy ->
                            val mediaImage = proxy.image
                            if (mediaImage != null && !scanned) {
                                val image = InputImage.fromMediaImage(mediaImage, proxy.imageInfo.rotationDegrees)
                                scanner.process(image)
                                    .addOnSuccessListener { barcodes ->
                                        barcodes.firstOrNull()?.rawValue?.let { raw ->
                                            if (!scanned) {
                                                scanned = true
                                                onScanned(raw)
                                            }
                                        }
                                    }
                                    .addOnCompleteListener { proxy.close() }
                            } else proxy.close()
                        }
                        provider.unbindAll()
                        provider.bindToLifecycle(lifecycleOwner, CameraSelector.DEFAULT_BACK_CAMERA, preview, analysis)
                    }, ContextCompat.getMainExecutor(ctx))
                    previewView
                },
                modifier = Modifier.fillMaxSize(),
            )
        }

        Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
            Box(Modifier.size(220.dp).border(2.dp, PairingNeon, RoundedCornerShape(16.dp)))
        }

        Box(Modifier.fillMaxSize().padding(16.dp), contentAlignment = Alignment.TopStart) {
            androidx.compose.material3.TextButton(onClick = onBack) {
                Text("← Back", color = PairingAccent, style = AppTypography.bodyMedium)
            }
        }

        Box(Modifier.fillMaxSize().padding(bottom = 48.dp), contentAlignment = Alignment.BottomCenter) {
            Column(horizontalAlignment = Alignment.CenterHorizontally) {
                Text("Scan QR from VPS terminal", style = AppTypography.bodyMedium, color = Color.White.copy(0.7f))
                Spacer(Modifier.height(4.dp))
                Text(
                    "docker logs jobai | grep QR",
                    style = AppTypography.labelMedium.copy(fontFamily = FiraCodeFamily),
                    color = PairingNeon,
                )
            }
        }
    }
}
