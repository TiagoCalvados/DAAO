package com.tiagocalvados.daao

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.os.SystemClock
import android.speech.RecognitionListener
import android.speech.RecognizerIntent
import android.speech.SpeechRecognizer
import android.speech.tts.TextToSpeech
import android.speech.tts.UtteranceProgressListener
import android.view.WindowManager
import android.view.inputmethod.EditorInfo
import android.widget.Button
import android.widget.EditText
import android.widget.TextView
import androidx.activity.ComponentActivity
import androidx.activity.result.contract.ActivityResultContracts
import androidx.camera.core.CameraSelector
import androidx.camera.core.Preview
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.camera.view.PreviewView
import androidx.core.content.ContextCompat
import java.util.Locale

class MainActivity : ComponentActivity(), TextToSpeech.OnInitListener {
    private lateinit var previewView: PreviewView
    private lateinit var answerText: TextView
    private lateinit var statusText: TextView
    private lateinit var readingsText: TextView
    private lateinit var questionInput: EditText
    private val handler = Handler(Looper.getMainLooper())
    private val orientationTracker by lazy { OrientationTracker(this) }
    private val locationTracker by lazy { LocationTracker(this) }
    private var recognizer: SpeechRecognizer? = null
    private var speechEngine: TextToSpeech? = null
    private var cloneVoice: VoiceOutput? = null
    private var speechReady = false
    private var listening = false
    private var speaking = false
    private var active = false
    private var microphoneDenied = false
    private var readingsExpanded = false
    private val readingsUpdater = object : Runnable {
        override fun run() {
            updateReadings()
            if (active) handler.postDelayed(this, 1_000)
        }
    }

    private val askForCamera = registerForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
        if (granted) startCamera() else statusText.text = getString(R.string.camera_permission_needed)
        requestLocationPermission()
    }
    private val askForLocation = registerForActivityResult(ActivityResultContracts.RequestMultiplePermissions()) { result ->
        if (result.values.any { it }) locationTracker.start()
        requestMicrophonePermission()
    }
    private val askForMicrophone = registerForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
        microphoneDenied = !granted
        if (granted) startListening() else statusText.text = getString(R.string.microphone_permission_needed)
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)
        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        previewView = findViewById(R.id.preview)
        answerText = findViewById(R.id.answer)
        statusText = findViewById(R.id.status)
        readingsText = findViewById(R.id.readings)
        readingsText.setOnClickListener {
            readingsExpanded = !readingsExpanded
            updateReadings()
        }
        questionInput = findViewById(R.id.question)
        val askButton: Button = findViewById(R.id.ask_button)
        askButton.setOnClickListener { submitTypedQuestion() }
        questionInput.setOnEditorActionListener { _, actionId, _ ->
            if (actionId == EditorInfo.IME_ACTION_SEND) {
                submitTypedQuestion()
                true
            } else false
        }
        if (resources.getBoolean(R.bool.use_private_voice)) {
            try {
                cloneVoice = Class.forName("com.tiagocalvados.daao.CloneVoice")
                    .getConstructor(android.content.Context::class.java)
                    .newInstance(this) as VoiceOutput
            } catch (_: Exception) {
                statusText.text = getString(R.string.private_voice_unavailable)
            }
        } else {
            speechEngine = TextToSpeech(this, this)
        }

        if (ContextCompat.checkSelfPermission(this, Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED) {
            startCamera()
            requestLocationPermission()
        } else {
            askForCamera.launch(Manifest.permission.CAMERA)
        }
    }

    private fun requestLocationPermission() {
        if (!locationTracker.hasPermission) {
            askForLocation.launch(arrayOf(Manifest.permission.ACCESS_FINE_LOCATION, Manifest.permission.ACCESS_COARSE_LOCATION))
        } else requestMicrophonePermission()
    }

    private fun requestMicrophonePermission() {
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED) {
            askForMicrophone.launch(Manifest.permission.RECORD_AUDIO)
        } else startListening()
    }

    override fun onResume() {
        super.onResume()
        active = true
        orientationTracker.start()
        locationTracker.start()
        handler.post(readingsUpdater)
        startListening()
    }

    override fun onPause() {
        active = false
        handler.removeCallbacksAndMessages(null)
        stopListening()
        speechEngine?.stop()
        cloneVoice?.stop()
        speaking = false
        orientationTracker.stop()
        locationTracker.stop()
        super.onPause()
    }

    override fun onDestroy() {
        recognizer?.destroy()
        recognizer = null
        speechEngine?.shutdown()
        speechEngine = null
        cloneVoice?.shutdown()
        cloneVoice = null
        super.onDestroy()
    }

    private fun startCamera() {
        val providerFuture = ProcessCameraProvider.getInstance(this)
        providerFuture.addListener({
            try {
                val provider = providerFuture.get()
                val preview = Preview.Builder().build()
                preview.surfaceProvider = previewView.surfaceProvider
                provider.unbindAll()
                provider.bindToLifecycle(this, CameraSelector.DEFAULT_BACK_CAMERA, preview)
            } catch (_: Exception) {
                statusText.text = getString(R.string.camera_unavailable)
            }
        }, ContextCompat.getMainExecutor(this))
    }

    private fun updateReadings() {
        val now = System.currentTimeMillis()
        val location = locationTracker.snapshot()?.takeIf { now - it.timestampEpochMs in 0L..60_000L }
        val orientation = orientationTracker.snapshot()?.takeIf {
            SystemClock.elapsedRealtimeNanos() - it.sensorTimestampNs in 0L..5_000_000_000L
        }
        val magneticBearing = orientation?.cameraPose?.magneticBearingDegrees
        val trueBearing = if (magneticBearing != null && location != null) {
            (magneticBearing + location.magneticDeclinationDegrees + 360.0) % 360.0
        } else null
        val bearingText = when {
            trueBearing != null -> String.format(Locale.getDefault(), "Az %.0f° T", trueBearing)
            magneticBearing != null -> String.format(Locale.getDefault(), "Heading %.0f° M", magneticBearing)
            orientation != null -> "Pointing vertically"
            else -> "Pointing: waiting for sensors"
        }
        val elevationText = orientation?.cameraPose?.elevationDegrees?.let {
            String.format(Locale.getDefault(), " · Elev %+.1f°", it)
        } ?: ""
        val gpsText = location?.let {
            val accuracy = it.horizontalAccuracyMeters?.let { meters ->
                String.format(Locale.getDefault(), " · ±%.0f m", meters)
            } ?: ""
            String.format(Locale.getDefault(), "GPS %.5f, %.5f", it.latitudeDegrees, it.longitudeDegrees) + accuracy
        } ?: "GPS: waiting for location"
        val details = if (readingsExpanded) {
            val pitch = orientation?.pitchDegrees?.let { String.format(Locale.getDefault(), "%+.1f°", it) } ?: "—"
            val roll = orientation?.rollDegrees?.let { String.format(Locale.getDefault(), "%+.1f°", it) } ?: "—"
            val altitude = location?.altitudeMeters?.let { String.format(Locale.getDefault(), "%.0f m", it) } ?: "—"
            val compass = orientation?.headingAccuracyDegrees?.let { String.format(Locale.getDefault(), "±%.0f°", it) } ?: "—"
            "\nPitch $pitch · Roll $roll · Height $altitude\nCompass accuracy $compass"
        } else ""
        readingsText.text = "$bearingText$elevationText\n$gpsText$details  ${if (readingsExpanded) "▴" else "▾"}"
    }

    private fun submitTypedQuestion() {
        val question = questionInput.text.toString().trim()
        if (question.isEmpty()) return
        questionInput.text.clear()
        answer(question)
    }

    private fun answer(question: String) {
        stopListening()
        val location = locationTracker.snapshot()
        val orientation = orientationTracker.snapshot()
        val locationFresh = location != null &&
            System.currentTimeMillis() - location.timestampEpochMs in 0L..900_000L
        val orientationFresh = orientation != null &&
            SystemClock.elapsedRealtimeNanos() - orientation.sensorTimestampNs in 0L..5_000_000_000L
        val compassReliable = orientation?.headingAccuracyDegrees?.let { it <= 20.0 } ?: true
        val bearing = orientation?.cameraPose?.magneticBearingDegrees?.let {
            (it + (location?.magneticDeclinationDegrees ?: 0.0) + 360.0) % 360.0
        }
        val objects = location?.takeIf { locationFresh }?.let {
            SkyGuide.objects(it.latitudeDegrees, it.longitudeDegrees, System.currentTimeMillis())
        }
        val reply = if (!compassReliable) {
            "The compass is too uncertain to identify this direction. Move away from metal and try again."
        } else SkyGuide.answer(
            question,
            objects,
            orientation?.cameraPose?.elevationDegrees?.takeIf { orientationFresh },
            bearing?.takeIf { orientationFresh },
        )
        answerText.text = reply
        val privateVoice = cloneVoice
        if (privateVoice != null) {
            speaking = true
            privateVoice.speak(reply) { error ->
                handler.post {
                    speaking = false
                    if (error != null) statusText.text = getString(R.string.private_voice_unavailable)
                    scheduleListening(350)
                }
            }
        } else if (speechReady) {
            speaking = true
            if (speechEngine?.speak(reply, TextToSpeech.QUEUE_FLUSH, null, "daao-answer") == TextToSpeech.ERROR) {
                speaking = false
                scheduleListening(600)
            }
        } else {
            scheduleListening(600)
        }
    }

    override fun onInit(status: Int) {
        if (status != TextToSpeech.SUCCESS) return
        val engine = speechEngine ?: return
        speechReady = engine.setLanguage(Locale.getDefault()) >= TextToSpeech.LANG_AVAILABLE
        engine.setOnUtteranceProgressListener(object : UtteranceProgressListener() {
            override fun onStart(utteranceId: String?) = Unit
            override fun onDone(utteranceId: String?) { handler.post { speaking = false; scheduleListening(350) } }
            @Deprecated("Deprecated in Java")
            override fun onError(utteranceId: String?) { handler.post { speaking = false; scheduleListening(350) } }
        })
    }

    private fun startListening() {
        if (!active || speaking || listening || microphoneDenied ||
            ContextCompat.checkSelfPermission(this, Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED) return
        val onDeviceAvailable = Build.VERSION.SDK_INT >= 31 && SpeechRecognizer.isOnDeviceRecognitionAvailable(this)
        if (!onDeviceAvailable) {
            statusText.text = getString(R.string.offline_speech_unavailable)
            return
        }
        if (recognizer == null) {
            recognizer = SpeechRecognizer.createOnDeviceSpeechRecognizer(this)
            recognizer?.setRecognitionListener(object : RecognitionListener {
                override fun onReadyForSpeech(params: Bundle?) { statusText.text = getString(R.string.listening) }
                override fun onBeginningOfSpeech() = Unit
                override fun onRmsChanged(rmsdB: Float) = Unit
                override fun onBufferReceived(buffer: ByteArray?) = Unit
                override fun onEndOfSpeech() = Unit
                override fun onPartialResults(partialResults: Bundle?) = Unit
                override fun onEvent(eventType: Int, params: Bundle?) = Unit
                override fun onError(error: Int) {
                    listening = false
                    if (error == SpeechRecognizer.ERROR_INSUFFICIENT_PERMISSIONS) {
                        microphoneDenied = true
                        statusText.text = getString(R.string.microphone_permission_needed)
                    } else {
                        statusText.text = getString(R.string.listening_paused)
                        scheduleListening(if (error == SpeechRecognizer.ERROR_RECOGNIZER_BUSY) 1500 else 500)
                    }
                }
                override fun onResults(results: Bundle?) {
                    listening = false
                    val heard = results?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)?.firstOrNull()
                    if (heard.isNullOrBlank()) scheduleListening(400) else answer(heard)
                }
            })
        }
        val intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
            putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
            putExtra(RecognizerIntent.EXTRA_PREFER_OFFLINE, true)
            putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, false)
            putExtra(RecognizerIntent.EXTRA_CALLING_PACKAGE, packageName)
        }
        try {
            listening = true
            recognizer?.startListening(intent)
        } catch (_: Exception) {
            listening = false
            statusText.text = getString(R.string.speech_unavailable)
        }
    }

    private fun stopListening() {
        if (listening) {
            listening = false
            recognizer?.cancel()
        }
    }

    private fun scheduleListening(delayMillis: Long) {
        if (active) handler.postDelayed({ startListening() }, delayMillis)
    }
}
