package com.tiagocalvados.daao

import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class DaaoProtocolTest {
    @Test
    fun normalizesBareHostAndAddsDataPath() {
        assertEquals(
            "http://192.168.1.10:8000/data",
            DaaoProtocol.normalizeEndpoint("192.168.1.10:8000").toString(),
        )
    }

    @Test(expected = IllegalArgumentException::class)
    fun rejectsNonHttpSchemes() {
        DaaoProtocol.normalizeEndpoint("file:///tmp/data")
    }

    @Test
    fun emitsCompassCameraAndFutureOrientationData() {
        val protocol = DaaoProtocol(
            sessionId = "test-session",
            deviceId = "test-phone",
        )
        val snapshot = OrientationSnapshot(
            sensorTimestampNs = 123,
            cameraPose = CameraPose(
                magneticBearingDegrees = 45.0,
                elevationDegrees = 30.0,
                deviceTopBearingDegrees = 90.0,
                cameraRollDegrees = 12.0,
            ),
            pitchDegrees = 1.0,
            rollDegrees = 2.0,
            quaternionW = 1.0,
            quaternionX = 0.0,
            quaternionY = 0.0,
            quaternionZ = 0.0,
            headingAccuracyDegrees = 3.0,
            sensorAccuracy = 3,
        )

        val document = JSONObject(protocol.sensorJson(snapshot, 456, 789))
        val payload = document.getJSONArray("payload")

        assertEquals("daao-mobile-v1", document.getString("protocol"))
        assertEquals(789, document.getLong("imageTimestampNs"))
        assertEquals(45.0, payload.getJSONObject(0).getJSONObject("values")
            .getDouble("magneticBearing"), 0.0)
        assertEquals(30.0, payload.getJSONObject(1).getJSONObject("values")
            .getDouble("cameraElevation"), 0.0)
        assertEquals(12.0, payload.getJSONObject(1).getJSONObject("values")
            .getDouble("cameraRoll"), 0.0)
        assertEquals(74.0, payload.getJSONObject(2).getJSONObject("values")
            .getDouble("horizontalFov"), 0.0)
    }

    @Test
    fun multipartContainsJsonAndUnmodifiedJpeg() {
        val jpeg = byteArrayOf(0xff.toByte(), 0xd8.toByte(), 0xff.toByte(), 7, 8, 9)
        val body = DaaoProtocol.multipart("""{"messageId":1}""", jpeg, "test-boundary")
        val text = body.bytes.toString(Charsets.ISO_8859_1)

        assertEquals("multipart/form-data; boundary=test-boundary", body.contentType)
        assertTrue(text.contains("name=\"data\""))
        assertTrue(text.contains("name=\"image\"; filename=\"frame.jpg\""))
        assertTrue(body.bytes.indexOfSubsequence(jpeg) >= 0)
    }

    @Test
    fun emitsLocationDeclinationAndTrueBearing() {
        val protocol = DaaoProtocol(sessionId = "test-session", deviceId = "test-phone")
        val snapshot = OrientationSnapshot(
            sensorTimestampNs = 123,
            cameraPose = CameraPose(359.0, 20.0, 0.0, 0.0),
            pitchDegrees = 0.0,
            rollDegrees = 0.0,
            quaternionW = 1.0,
            quaternionX = 0.0,
            quaternionY = 0.0,
            quaternionZ = 0.0,
            headingAccuracyDegrees = 2.0,
            sensorAccuracy = 3,
        )
        val location = LocationSnapshot(
            latitudeDegrees = 52.3676,
            longitudeDegrees = 4.9041,
            altitudeMeters = 12.5,
            horizontalAccuracyMeters = 4.0,
            timestampEpochMs = 1_785_000_000_000,
            magneticDeclinationDegrees = 3.0,
        )

        val document = JSONObject(protocol.sensorJson(snapshot, 456, 789, location = location))
        val payload = document.getJSONArray("payload")
        val compass = payload.getJSONObject(0).getJSONObject("values")
        val gps = payload.getJSONObject(3).getJSONObject("values")

        assertEquals(2.0, compass.getDouble("trueBearing"), 0.0)
        assertEquals(3.0, compass.getDouble("magneticDeclination"), 0.0)
        assertEquals(52.3676, gps.getDouble("latitude"), 0.0)
        assertEquals(4.9041, gps.getDouble("longitude"), 0.0)
        assertEquals(4.0, gps.getDouble("horizontalAccuracy"), 0.0)
    }

    private fun ByteArray.indexOfSubsequence(needle: ByteArray): Int {
        return indices.firstOrNull { start ->
            start + needle.size <= size &&
                needle.indices.all { offset -> this[start + offset] == needle[offset] }
        } ?: -1
    }
}
