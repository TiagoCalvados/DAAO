package com.tiagocalvados.daao

import org.json.JSONArray
import org.json.JSONObject
import java.io.ByteArrayOutputStream
import java.net.URI
import java.util.UUID
import java.util.concurrent.atomic.AtomicLong

class DaaoProtocol(
    private val sessionId: String = UUID.randomUUID().toString(),
    private val deviceId: String,
    private val horizontalFovDegrees: Double = 74.0,
) {
    private val messageId = AtomicLong()

    fun sensorJson(
        snapshot: OrientationSnapshot,
        capturedAtEpochNs: Long,
        imageTimestampNs: Long,
        cameraRollDegrees: Double? = snapshot.cameraPose.cameraRollDegrees,
        location: LocationSnapshot? = null,
    ): String {
        val compassValues = JSONObject()
        snapshot.cameraPose.magneticBearingDegrees?.let {
            compassValues.put("magneticBearing", it)
        }
        snapshot.headingAccuracyDegrees?.let {
            compassValues.put("headingAccuracy", it)
        }
        if (location != null) {
            compassValues.put("magneticDeclination", location.magneticDeclinationDegrees)
            snapshot.cameraPose.magneticBearingDegrees?.let {
                compassValues.put(
                    "trueBearing",
                    normalizeDegrees(it + location.magneticDeclinationDegrees),
                )
            }
        }

        val orientationValues = JSONObject()
            .put("cameraElevation", snapshot.cameraPose.elevationDegrees)
            .put("pitch", snapshot.pitchDegrees)
            .put("roll", snapshot.rollDegrees)
            .put("quaternionW", snapshot.quaternionW)
            .put("quaternionX", snapshot.quaternionX)
            .put("quaternionY", snapshot.quaternionY)
            .put("quaternionZ", snapshot.quaternionZ)
            .put("sensorAccuracy", snapshot.sensorAccuracy)
            .put("sensorTimestampNs", snapshot.sensorTimestampNs)
        cameraRollDegrees?.let {
            orientationValues.put("cameraRoll", it)
        }
        snapshot.cameraPose.deviceTopBearingDegrees?.let {
            orientationValues.put("deviceTopBearing", it)
        }

        val payload = JSONArray()
            .put(
                JSONObject()
                    .put("name", "compass")
                    .put("time", capturedAtEpochNs)
                    .put("values", compassValues),
            )
            .put(
                JSONObject()
                    .put("name", "orientation")
                    .put("time", capturedAtEpochNs)
                    .put("values", orientationValues),
            )
            .put(
                JSONObject()
                    .put("name", "camera")
                    .put("time", capturedAtEpochNs)
                    .put(
                        "values",
                        JSONObject().put("horizontalFov", horizontalFovDegrees),
                    ),
            )
        if (location != null) {
            val locationValues = JSONObject()
                .put("latitude", location.latitudeDegrees)
                .put("longitude", location.longitudeDegrees)
                .put("locationTimestampEpochMs", location.timestampEpochMs)
                .put("magneticDeclination", location.magneticDeclinationDegrees)
            location.altitudeMeters?.let { locationValues.put("altitudeMeters", it) }
            location.horizontalAccuracyMeters?.let {
                locationValues.put("horizontalAccuracy", it)
            }
            payload.put(
                JSONObject()
                    .put("name", "location")
                    .put("time", location.timestampEpochMs * 1_000_000L)
                    .put("values", locationValues),
            )
        }

        return JSONObject()
            .put("protocol", "daao-mobile-v1")
            .put("messageId", messageId.incrementAndGet())
            .put("sessionId", sessionId)
            .put("deviceId", deviceId)
            .put("imageTimestampNs", imageTimestampNs)
            .put("payload", payload)
            .toString()
    }

    companion object {
        private fun normalizeDegrees(value: Double): Double = ((value % 360.0) + 360.0) % 360.0

        fun normalizeEndpoint(input: String): URI {
            val trimmed = input.trim()
            require(trimmed.isNotEmpty()) { "Enter the DAAO receiver address" }
            val withScheme = if ("://" in trimmed) trimmed else "http://$trimmed"
            val parsed = URI(withScheme)
            require(parsed.scheme == "http" || parsed.scheme == "https") {
                "The address must use http:// or https://"
            }
            require(!parsed.host.isNullOrBlank()) { "The receiver hostname is missing" }
            if (parsed.path.isNullOrEmpty() || parsed.path == "/") {
                return URI(
                    parsed.scheme,
                    parsed.userInfo,
                    parsed.host,
                    parsed.port,
                    "/data",
                    parsed.query,
                    parsed.fragment,
                )
            }
            return parsed
        }

        fun multipart(
            json: String,
            jpeg: ByteArray,
            boundary: String = "daao-${UUID.randomUUID()}",
        ): MultipartBody {
            val output = ByteArrayOutputStream(json.length + jpeg.size + 512)
            fun text(value: String) = output.write(value.toByteArray(Charsets.UTF_8))

            text("--$boundary\r\n")
            text("Content-Disposition: form-data; name=\"data\"\r\n")
            text("Content-Type: application/json; charset=utf-8\r\n\r\n")
            text(json)
            text("\r\n--$boundary\r\n")
            text("Content-Disposition: form-data; name=\"image\"; filename=\"frame.jpg\"\r\n")
            text("Content-Type: image/jpeg\r\n\r\n")
            output.write(jpeg)
            text("\r\n--$boundary--\r\n")

            return MultipartBody(
                contentType = "multipart/form-data; boundary=$boundary",
                bytes = output.toByteArray(),
            )
        }
    }
}

data class MultipartBody(
    val contentType: String,
    val bytes: ByteArray,
)
