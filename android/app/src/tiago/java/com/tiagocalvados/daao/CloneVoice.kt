package com.tiagocalvados.daao

import android.content.Context
import android.media.AudioAttributes
import android.media.AudioFormat
import android.media.AudioTrack
import com.k2fsa.sherpa.onnx.GenerationConfig
import com.k2fsa.sherpa.onnx.OfflineTts
import com.k2fsa.sherpa.onnx.OfflineTtsConfig
import com.k2fsa.sherpa.onnx.OfflineTtsModelConfig
import com.k2fsa.sherpa.onnx.OfflineTtsPocketModelConfig
import java.io.File
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.util.concurrent.Executors
import java.util.concurrent.atomic.AtomicInteger

/** The Tiago build keeps all synthesis, including the voice reference, on this device. */
class CloneVoice(private val context: Context) : VoiceOutput {
    private val worker = Executors.newSingleThreadExecutor()
    private val generation = AtomicInteger(0)
    @Volatile private var track: AudioTrack? = null
    @Volatile private var closed = false
    private var tts: OfflineTts? = null
    private var reference: FloatArray? = null

    override fun speak(text: String, onFinished: (String?) -> Unit) {
        stop()
        val request = generation.get()
        worker.execute {
            if (closed || request != generation.get()) return@execute
            try {
                ensureReady()
                if (closed || request != generation.get()) return@execute
                val audio = checkNotNull(tts).generateWithConfig(
                    text,
                    GenerationConfig(
                        referenceAudio = checkNotNull(reference),
                        referenceSampleRate = 24000,
                        numSteps = 3,
                    ),
                )
                if (closed || request != generation.get()) return@execute
                play(audio.samples, audio.sampleRate, request)
                if (request == generation.get()) onFinished(null)
            } catch (error: Exception) {
                if (request == generation.get()) onFinished(error.message ?: "Voice generation failed")
            }
        }
    }

    override fun stop() {
        generation.incrementAndGet()
        track?.let { current ->
            try { current.pause(); current.flush() } catch (_: IllegalStateException) { }
        }
    }

    override fun shutdown() {
        closed = true
        stop()
        worker.execute { tts?.release(); tts = null }
        worker.shutdown()
    }

    private fun ensureReady() {
        if (tts != null) return
        val folder = File(context.filesDir, "pocket-tts")
        folder.mkdirs()
        val names = listOf(
            "lm_flow.int8.onnx", "lm_main.int8.onnx", "encoder.onnx", "decoder.int8.onnx",
            "text_conditioner.onnx", "vocab.json", "token_scores.json",
        )
        for (name in names) {
            val target = File(folder, name)
            if (!target.isFile || target.length() != context.assets.open("pocket/$name").use { it.available().toLong() }) {
                val temporary = File(folder, "$name.part")
                context.assets.open("pocket/$name").use { source ->
                    temporary.outputStream().use { output -> source.copyTo(output) }
                }
                if (target.exists()) check(target.delete()) { "Cannot replace offline voice model" }
                check(temporary.renameTo(target)) { "Cannot prepare offline voice model" }
            }
        }
        reference = readReference(context.assets.open("voice/tiago-reference.wav").use { it.readBytes() })
        val pocket = OfflineTtsPocketModelConfig(
            lmFlow = File(folder, "lm_flow.int8.onnx").absolutePath,
            lmMain = File(folder, "lm_main.int8.onnx").absolutePath,
            encoder = File(folder, "encoder.onnx").absolutePath,
            decoder = File(folder, "decoder.int8.onnx").absolutePath,
            textConditioner = File(folder, "text_conditioner.onnx").absolutePath,
            vocabJson = File(folder, "vocab.json").absolutePath,
            tokenScoresJson = File(folder, "token_scores.json").absolutePath,
        )
        tts = OfflineTts(config = OfflineTtsConfig(model = OfflineTtsModelConfig(pocket = pocket, numThreads = 2)))
    }

    private fun readReference(bytes: ByteArray): FloatArray {
        val buffer = ByteBuffer.wrap(bytes).order(ByteOrder.LITTLE_ENDIAN)
        require(bytes.size >= 44 && String(bytes, 0, 4, Charsets.US_ASCII) == "RIFF")
        var position = 12
        var sampleRate = 0
        var channels = 0
        var bits = 0
        var dataStart = -1
        var dataLength = 0
        while (position + 8 <= bytes.size) {
            val id = String(bytes, position, 4, Charsets.US_ASCII)
            val length = buffer.getInt(position + 4)
            require(length >= 0 && position + 8L + length <= bytes.size)
            if (id == "fmt ") {
                require(length >= 16 && buffer.getShort(position + 8).toInt() == 1)
                channels = buffer.getShort(position + 10).toInt()
                sampleRate = buffer.getInt(position + 12)
                bits = buffer.getShort(position + 22).toInt()
            } else if (id == "data") {
                dataStart = position + 8
                dataLength = length
                break
            }
            position += 8 + length + (length and 1)
        }
        require(channels == 1 && sampleRate == 24000 && bits == 16 && dataStart >= 0)
        return FloatArray(dataLength / 2) { index ->
            buffer.getShort(dataStart + index * 2) / 32768f
        }
    }

    private fun play(samples: FloatArray, sampleRate: Int, request: Int) {
        if (samples.isEmpty()) return
        val format = AudioFormat.Builder()
            .setEncoding(AudioFormat.ENCODING_PCM_FLOAT)
            .setSampleRate(sampleRate)
            .setChannelMask(AudioFormat.CHANNEL_OUT_MONO)
            .build()
        val minBytes = AudioTrack.getMinBufferSize(sampleRate, AudioFormat.CHANNEL_OUT_MONO, AudioFormat.ENCODING_PCM_FLOAT)
        check(minBytes > 0)
        val player = AudioTrack.Builder()
            .setAudioAttributes(AudioAttributes.Builder().setUsage(AudioAttributes.USAGE_ASSISTANT).setContentType(AudioAttributes.CONTENT_TYPE_SPEECH).build())
            .setAudioFormat(format)
            .setBufferSizeInBytes(maxOf(minBytes, 16_384))
            .setTransferMode(AudioTrack.MODE_STREAM)
            .build()
        track = player
        try {
            player.play()
            var offset = 0
            while (offset < samples.size && request == generation.get() && !closed) {
                val written = player.write(samples, offset, minOf(4096, samples.size - offset), AudioTrack.WRITE_BLOCKING)
                check(written > 0) { "Audio playback failed" }
                offset += written
            }
            val deadline = android.os.SystemClock.elapsedRealtime() + samples.size * 1000L / sampleRate + 2000L
            while (request == generation.get() && !closed && player.playbackHeadPosition < offset &&
                android.os.SystemClock.elapsedRealtime() < deadline) {
                Thread.sleep(20)
            }
        } finally {
            track = null
            try { player.stop() } catch (_: IllegalStateException) { }
            player.release()
        }
    }
}
