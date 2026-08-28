package com.tiagocalvados.daao

import android.Manifest
import android.content.pm.PackageManager
import android.graphics.Bitmap
import android.os.Build
import android.os.Bundle
import android.os.SystemClock
import android.view.Surface
import android.view.WindowManager
import android.widget.Button
import android.widget.EditText
import android.widget.TextView
import androidx.activity.ComponentActivity
import androidx.activity.result.contract.ActivityResultContracts
import androidx.camera.core.AspectRatio
import androidx.camera.core.CameraSelector
import androidx.camera.core.ImageAnalysis
import androidx.camera.core.ImageProxy
import androidx.camera.core.Preview
import androidx.camera.core.resolutionselector.AspectRatioStrategy
import androidx.camera.core.resolutionselector.ResolutionSelector
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.camera.view.PreviewView
import androidx.core.content.ContextCompat
import androidx.core.content.edit
import java.io.ByteArrayOutputStream
import java.net.URI
import java.util.concurrent.Executors
import java.util.concurrent.atomic.AtomicBoolean

class MainActivity : ComponentActivity() {
    private lateinit var previewView: PreviewView
    private lateinit var serverUrl: EditText
    private lateinit var streamButton: Button
    private lateinit var orientationText: TextView
    private lateinit var statusText: TextView

    private val cameraExecutor = Executors.newSingleThreadExecutor()
    private val networkExecutor = Executors.newSingleThreadExecutor()
    private val sending = AtomicBoolean(false)
    private val orientationTracker by lazy { OrientationTracker(this) }
    private val locationTracker by lazy { LocationTracker(this) }
    private val protocol by lazy {
        DaaoProtocol(deviceId = "${Build.MANUFACTURER} ${Build.MODEL}")
    }

    @Volatile
    private var streaming = false
    @Volatile
    private var streamingEndpoint: URI? = null
    private var nextFrameAtNs = 0L
    private var sentFrames = 0L
    @Volatile
    private var imageTargetRotationDegrees = 0

    private val requestCameraPermission =
        registerForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
            if (granted) {
                startCamera()
                requestLocationIfNeeded()
            } else {
                setStatus("Camera permission is required to stream images.")
            }
        }

    private val requestLocationPermission =
        registerForActivityResult(ActivityResultContracts.RequestMultiplePermissions()) { result ->
            if (result.values.any { it }) {
                locationTracker.start()
            } else {
                setStatus("Location permission was denied; the sky overlay will wait for GPS.")
            }
        }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)
        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)

        previewView = findViewById(R.id.preview)
        serverUrl = findViewById(R.id.server_url)
        streamButton = findViewById(R.id.stream_button)
        orientationText = findViewById(R.id.orientation)
        statusText = findViewById(R.id.status)

        val preferences = getSharedPreferences("daao", MODE_PRIVATE)
        serverUrl.setText(
            preferences.getString(
                "server_url",
                "",
            ),
        )
        streamButton.setOnClickListener {
            if (streaming) {
                stopStreaming()
            } else {
                val endpoint = validateEndpoint() ?: return@setOnClickListener
                preferences.edit { putString("server_url", endpoint.toString()) }
                serverUrl.setText(endpoint.toString())
                startStreaming(endpoint)
            }
        }

        if (!orientationTracker.isAvailable) {
            orientationText.text = getString(R.string.no_orientation_sensor)
            streamButton.isEnabled = false
        } else {
            orientationText.text = getString(
                R.string.sensor_name,
                orientationTracker.sensorName,
            )
        }

        if (ContextCompat.checkSelfPermission(this, Manifest.permission.CAMERA) ==
            PackageManager.PERMISSION_GRANTED
        ) {
            startCamera()
            requestLocationIfNeeded()
        } else {
            requestCameraPermission.launch(Manifest.permission.CAMERA)
        }
    }

    override fun onResume() {
        super.onResume()
        orientationTracker.start()
        locationTracker.start()
    }

    override fun onPause() {
        orientationTracker.stop()
        locationTracker.stop()
        super.onPause()
    }

    override fun onDestroy() {
        streaming = false
        cameraExecutor.shutdown()
        networkExecutor.shutdown()
        super.onDestroy()
    }

    private fun startCamera() {
        val providerFuture = ProcessCameraProvider.getInstance(this)
        providerFuture.addListener(
            {
                try {
                    val provider = providerFuture.get()
                    val targetRotation = previewView.display.rotation
                    imageTargetRotationDegrees = when (targetRotation) {
                        Surface.ROTATION_0 -> 0
                        Surface.ROTATION_90 -> 90
                        Surface.ROTATION_180 -> 180
                        Surface.ROTATION_270 -> 270
                        else -> 0
                    }
                    val preview = Preview.Builder()
                        .setTargetRotation(targetRotation)
                        .build()
                        .also { it.surfaceProvider = previewView.surfaceProvider }
                    val resolutionSelector = ResolutionSelector.Builder()
                        .setAspectRatioStrategy(
                            AspectRatioStrategy(
                                AspectRatio.RATIO_16_9,
                                AspectRatioStrategy.FALLBACK_RULE_AUTO,
                            ),
                        )
                        .build()
                    val analysis = ImageAnalysis.Builder()
                        .setResolutionSelector(resolutionSelector)
                        .setTargetRotation(targetRotation)
                        .setOutputImageFormat(ImageAnalysis.OUTPUT_IMAGE_FORMAT_RGBA_8888)
                        .setOutputImageRotationEnabled(true)
                        .setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST)
                        .build()
                    analysis.setAnalyzer(cameraExecutor, ::analyzeFrame)

                    provider.unbindAll()
                    provider.bindToLifecycle(
                        this,
                        CameraSelector.DEFAULT_BACK_CAMERA,
                        preview,
                        analysis,
                    )
                    setStatus("Camera ready. Enter the desktop URL and tap Start streaming.")
                } catch (error: Exception) {
                    setStatus("Could not start camera: ${error.message}")
                }
            },
            ContextCompat.getMainExecutor(this),
        )
    }

    private fun requestLocationIfNeeded() {
        if (locationTracker.hasPermission) {
            locationTracker.start()
        } else {
            requestLocationPermission.launch(
                arrayOf(
                    Manifest.permission.ACCESS_FINE_LOCATION,
                    Manifest.permission.ACCESS_COARSE_LOCATION,
                ),
            )
        }
    }

    private fun analyzeFrame(image: ImageProxy) {
        try {
            if (!streaming) {
                return
            }
            val now = SystemClock.elapsedRealtimeNanos()
            if (now < nextFrameAtNs || !sending.compareAndSet(false, true)) {
                return
            }
            nextFrameAtNs = now + FRAME_INTERVAL_NS

            val snapshot = orientationTracker.snapshot()
            if (snapshot == null) {
                sending.set(false)
                setStatus("Waiting for an orientation reading…")
                return
            }

            val jpeg = image.toJpeg()
            val capturedAtEpochNs = System.currentTimeMillis() * 1_000_000L
            val json = protocol.sensorJson(
                snapshot = snapshot,
                capturedAtEpochNs = capturedAtEpochNs,
                imageTimestampNs = capturedAtEpochNs,
                cameraRollDegrees = OrientationMath.cameraRollForTarget(
                    snapshot.cameraPose.cameraRollDegrees,
                    imageTargetRotationDegrees,
                ),
                location = locationTracker.snapshot(),
            )
            val multipart = DaaoProtocol.multipart(json, jpeg)
            val endpoint = streamingEndpoint
            if (endpoint == null) {
                sending.set(false)
                setStatus("The receiver address is unavailable.")
                return
            }
            updateOrientation(snapshot)

            networkExecutor.execute {
                try {
                    val result = DaaoHttpSender.send(endpoint, multipart)
                    if (result.statusCode in 200..299) {
                        sentFrames += 1
                        setStatus(
                            "Streaming • HTTP ${result.statusCode} • frame $sentFrames • " +
                                "${jpeg.size / 1024} KiB",
                        )
                    } else {
                        setStatus(
                            "Receiver returned HTTP ${result.statusCode}: " +
                                result.responseText.take(120),
                        )
                    }
                } catch (error: Exception) {
                    setStatus("Send failed: ${error.message}")
                } finally {
                    sending.set(false)
                }
            }
        } catch (error: Exception) {
            sending.set(false)
            setStatus("Frame conversion failed: ${error.message}")
        } finally {
            image.close()
        }
    }

    private fun ImageProxy.toJpeg(): ByteArray {
        val bitmap = toBitmap()
        return try {
            ByteArrayOutputStream().use { output ->
                check(bitmap.compress(Bitmap.CompressFormat.JPEG, JPEG_QUALITY, output)) {
                    "JPEG encoder rejected the camera frame"
                }
                output.toByteArray()
            }
        } finally {
            bitmap.recycle()
        }
    }

    private fun startStreaming(endpoint: URI) {
        streamingEndpoint = endpoint
        streaming = true
        sentFrames = 0
        nextFrameAtNs = 0
        streamButton.text = getString(R.string.stop_streaming)
        serverUrl.isEnabled = false
        setStatus("Starting stream…")
    }

    private fun stopStreaming() {
        streaming = false
        streamingEndpoint = null
        streamButton.text = getString(R.string.start_streaming)
        serverUrl.isEnabled = true
        setStatus("Streaming stopped.")
    }

    private fun validateEndpoint(): URI? {
        return try {
            DaaoProtocol.normalizeEndpoint(serverUrl.text.toString())
        } catch (error: IllegalArgumentException) {
            serverUrl.error = error.message
            null
        }
    }

    private fun updateOrientation(snapshot: OrientationSnapshot) {
        val heading = snapshot.cameraPose.magneticBearingDegrees
        val headingText = heading?.let { "%06.2f° M".format(it) } ?: "vertical"
        runOnUiThread {
            orientationText.text = getString(
                R.string.orientation_readout,
                headingText,
                snapshot.cameraPose.elevationDegrees,
            )
        }
    }

    private fun setStatus(message: String) {
        runOnUiThread { statusText.text = message }
    }

    companion object {
        private const val FRAME_INTERVAL_NS = 1_000_000_000L
        private const val JPEG_QUALITY = 80
    }
}
