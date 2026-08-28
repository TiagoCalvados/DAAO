package com.tiagocalvados.daao

import android.Manifest
import android.annotation.SuppressLint
import android.content.Context
import android.content.pm.PackageManager
import android.hardware.GeomagneticField
import android.location.Location
import android.location.LocationListener
import android.location.LocationManager
import android.os.Bundle
import androidx.core.content.ContextCompat
import java.util.concurrent.atomic.AtomicReference

data class LocationSnapshot(
    val latitudeDegrees: Double,
    val longitudeDegrees: Double,
    val altitudeMeters: Double?,
    val horizontalAccuracyMeters: Double?,
    val timestampEpochMs: Long,
    val magneticDeclinationDegrees: Double,
)

class LocationTracker(context: Context) {
    private val applicationContext = context.applicationContext
    private val manager = applicationContext.getSystemService(LocationManager::class.java)
    private val latest = AtomicReference<LocationSnapshot?>()
    private val listener = object : LocationListener {
        override fun onLocationChanged(location: Location) = accept(location)

        override fun onProviderEnabled(provider: String) = Unit

        override fun onProviderDisabled(provider: String) = Unit

        @Deprecated("Deprecated by Android")
        override fun onStatusChanged(provider: String?, status: Int, extras: Bundle?) = Unit
    }
    private var started = false

    val hasPermission: Boolean
        get() = ContextCompat.checkSelfPermission(
            applicationContext,
            Manifest.permission.ACCESS_FINE_LOCATION,
        ) == PackageManager.PERMISSION_GRANTED || ContextCompat.checkSelfPermission(
            applicationContext,
            Manifest.permission.ACCESS_COARSE_LOCATION,
        ) == PackageManager.PERMISSION_GRANTED

    @SuppressLint("MissingPermission")
    fun start() {
        if (!hasPermission || started) {
            return
        }
        started = true
        for (provider in listOf(LocationManager.GPS_PROVIDER, LocationManager.NETWORK_PROVIDER)) {
            try {
                manager.getLastKnownLocation(provider)?.let(::accept)
                if (manager.isProviderEnabled(provider)) {
                    manager.requestLocationUpdates(provider, 1_000L, 0f, listener)
                }
            } catch (_: IllegalArgumentException) {
                // A provider can be absent even when the location API is present.
            } catch (_: SecurityException) {
                started = false
                return
            }
        }
    }

    fun stop() {
        started = false
        if (hasPermission) {
            try {
                manager.removeUpdates(listener)
            } catch (_: SecurityException) {
                // Permission can be revoked while the application is running.
            }
        }
    }

    fun snapshot(): LocationSnapshot? = latest.get()

    private fun accept(location: Location) {
        val altitude = if (location.hasAltitude()) location.altitude else null
        val field = GeomagneticField(
            location.latitude.toFloat(),
            location.longitude.toFloat(),
            (altitude ?: 0.0).toFloat(),
            location.time,
        )
        latest.set(
            LocationSnapshot(
                latitudeDegrees = location.latitude,
                longitudeDegrees = location.longitude,
                altitudeMeters = altitude,
                horizontalAccuracyMeters = if (location.hasAccuracy()) {
                    location.accuracy.toDouble()
                } else {
                    null
                },
                timestampEpochMs = location.time,
                magneticDeclinationDegrees = field.declination.toDouble(),
            ),
        )
    }
}
