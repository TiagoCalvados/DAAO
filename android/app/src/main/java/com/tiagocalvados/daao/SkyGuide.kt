package com.tiagocalvados.daao

import kotlin.math.acos
import kotlin.math.asin
import kotlin.math.atan2
import kotlin.math.cos
import kotlin.math.hypot
import kotlin.math.roundToInt
import kotlin.math.sin
import kotlin.math.sqrt

data class SkyObject(val name: String, val altitude: Double, val azimuth: Double, val magnitude: Double)

/** A small, offline sky catalog. Coordinates are approximate and are never treated as image recognition. */
object SkyGuide {
    private data class Equatorial(val name: String, val ra: Double, val dec: Double, val magnitude: Double)
    private val stars = listOf(
        Equatorial("Sirius", 101.287, -16.716, -1.46),
        Equatorial("Canopus", 95.988, -52.696, -0.74),
        Equatorial("Arcturus", 213.915, 19.182, -0.05),
        Equatorial("Vega", 279.235, 38.784, 0.03),
        Equatorial("Capella", 79.172, 45.998, 0.08),
        Equatorial("Rigel", 78.634, -8.202, 0.18),
        Equatorial("Procyon", 114.826, 5.225, 0.40),
        Equatorial("Betelgeuse", 88.792, 7.407, 0.45),
        Equatorial("Altair", 297.696, 8.868, 0.76),
        Equatorial("Aldebaran", 68.980, 16.509, 0.87),
        Equatorial("Spica", 201.298, -11.161, 0.98),
        Equatorial("Antares", 247.352, -26.432, 1.06),
        Equatorial("Pollux", 116.329, 28.026, 1.16),
        Equatorial("Fomalhaut", 344.413, -29.622, 1.17),
        Equatorial("Deneb", 310.358, 45.280, 1.25),
        Equatorial("Regulus", 152.093, 11.967, 1.36),
        Equatorial("Bellatrix", 81.573, 6.350, 1.64),
        Equatorial("Polaris", 37.955, 89.264, 1.97),
    )

    private fun rad(degrees: Double) = Math.toRadians(degrees)
    private fun deg(radians: Double) = Math.toDegrees(radians)
    private fun wrap(degrees: Double) = (degrees % 360.0 + 360.0) % 360.0
    private fun signed(degrees: Double) = wrap(degrees + 180.0) - 180.0

    private fun horizontal(objectPosition: Equatorial, latitude: Double, longitude: Double, jd: Double): SkyObject {
        val days = jd - 2451545.0
        val centuries = days / 36525.0
        val sidereal = wrap(280.46061837 + 360.98564736629 * days +
            0.000387933 * centuries * centuries + longitude)
        val hourAngle = rad(signed(sidereal - objectPosition.ra))
        val dec = rad(objectPosition.dec)
        val lat = rad(latitude)
        val altitude = asin(sin(dec) * sin(lat) + cos(dec) * cos(lat) * cos(hourAngle))
        val azimuth = atan2(sin(hourAngle), cos(hourAngle) * sin(lat) -
            sin(dec) / cos(dec) * cos(lat))
        return SkyObject(objectPosition.name, deg(altitude), wrap(deg(azimuth) + 180.0), objectPosition.magnitude)
    }

    private fun ecliptic(name: String, longitude: Double, latitude: Double, magnitude: Double, jd: Double): Equatorial {
        val obliquity = rad(23.439 - 0.00000036 * (jd - 2451545.0))
        val lon = rad(longitude)
        val lat = rad(latitude)
        val x = cos(lon) * cos(lat)
        val y = sin(lon) * cos(lat) * cos(obliquity) - sin(lat) * sin(obliquity)
        val z = sin(lon) * cos(lat) * sin(obliquity) + sin(lat) * cos(obliquity)
        return Equatorial(name, wrap(deg(atan2(y, x))), deg(asin(z)), magnitude)
    }

    private fun moon(jd: Double): Equatorial {
        // Short lunar series, valid for present-day observing to roughly a degree.
        val days = jd - 2451545.0
        val meanLongitude = wrap(218.316 + 13.176396 * days)
        val meanAnomaly = wrap(134.963 + 13.064993 * days)
        val argumentLatitude = wrap(93.272 + 13.229350 * days)
        val solarAnomaly = wrap(357.529 + 0.98560028 * days)
        val elongation = wrap(297.850 + 12.190749 * days)
        val longitude = meanLongitude + 6.289 * sin(rad(meanAnomaly)) +
            1.274 * sin(rad(2 * elongation - meanAnomaly)) +
            0.658 * sin(rad(2 * elongation)) + 0.214 * sin(rad(2 * meanAnomaly)) -
            0.186 * sin(rad(solarAnomaly))
        val latitude = 5.128 * sin(rad(argumentLatitude)) +
            0.280 * sin(rad(meanAnomaly + argumentLatitude)) +
            0.277 * sin(rad(meanAnomaly - argumentLatitude))
        return ecliptic("Moon", longitude, latitude, -12.0, jd)
    }

    private fun heliocentric(
        semiMajor: Double, eccentricity: Double, inclination: Double,
        longitude: Double, perihelion: Double, node: Double,
    ): DoubleArray {
        val anomaly = rad(wrap(longitude - perihelion))
        var eccentricAnomaly = anomaly
        repeat(10) {
            eccentricAnomaly -= (eccentricAnomaly - eccentricity * sin(eccentricAnomaly) - anomaly) /
                (1.0 - eccentricity * cos(eccentricAnomaly))
        }
        val orbitalX = semiMajor * (cos(eccentricAnomaly) - eccentricity)
        val orbitalY = semiMajor * sqrt(1.0 - eccentricity * eccentricity) * sin(eccentricAnomaly)
        val argument = rad(perihelion - node)
        val ascending = rad(node)
        val tilt = rad(inclination)
        val x1 = orbitalX * cos(argument) - orbitalY * sin(argument)
        val y1 = orbitalX * sin(argument) + orbitalY * cos(argument)
        return doubleArrayOf(
            x1 * cos(ascending) - y1 * cos(tilt) * sin(ascending),
            x1 * sin(ascending) + y1 * cos(tilt) * cos(ascending),
            y1 * sin(tilt),
        )
    }

    private fun mars(jd: Double): Equatorial {
        val t = (jd - 2451545.0) / 36525.0
        val earth = heliocentric(1.00000018 - 0.00000003 * t, 0.01673163 - 0.00003661 * t,
            -0.00054346 - 0.01337178 * t, 100.46691572 + 35999.37306329 * t,
            102.93005885 + 0.31795260 * t, -5.11260389 - 0.24123856 * t)
        val planet = heliocentric(1.52371243 + 0.00000097 * t, 0.09336511 + 0.00009149 * t,
            1.85181869 - 0.00724757 * t, -4.56813164 + 19140.29934243 * t,
            -23.91744784 + 0.45223625 * t, 49.71320984 - 0.26852431 * t)
        val x = planet[0] - earth[0]
        val y = planet[1] - earth[1]
        val z = planet[2] - earth[2]
        return ecliptic("Mars", wrap(deg(atan2(y, x))), deg(atan2(z, hypot(x, y))), -1.5, jd)
    }

    fun objects(latitude: Double, longitude: Double, epochMillis: Long): List<SkyObject> {
        val jd = 2440587.5 + epochMillis / 86400000.0
        return (stars + moon(jd) + mars(jd))
            .map { horizontal(it, latitude, longitude, jd) }
            .filter { it.altitude >= 0.0 }
    }

    fun separation(aAlt: Double, aAz: Double, bAlt: Double, bAz: Double): Double =
        deg(acos((sin(rad(aAlt)) * sin(rad(bAlt)) +
            cos(rad(aAlt)) * cos(rad(bAlt)) * cos(rad(aAz - bAz))).coerceIn(-1.0, 1.0)))

    fun answer(question: String, objects: List<SkyObject>?, elevation: Double?, trueBearing: Double?): String {
        if (objects == null || elevation == null || trueBearing == null) {
            return "I need your location and compass reading to answer from the sky in front of you."
        }
        val q = question.lowercase().trim()
        val inView = objects.filter { separation(elevation, trueBearing, it.altitude, it.azimuth) <= 18.0 }
            .sortedBy { separation(elevation, trueBearing, it.altitude, it.azimuth) }
        val requested = when {
            Regex("\\bmars\\b").containsMatchIn(q) -> "Mars"
            Regex("\\bmoon\\b").containsMatchIn(q) -> "Moon"
            else -> null
        }
        if (requested != null && ("where" in q || "find" in q || "locate" in q || "show" in q)) {
            val target = objects.find { it.name == requested }
                ?: return "$requested is below the horizon from your location right now."
            val turn = signed(target.azimuth - trueBearing).roundToInt()
            val lift = (target.altitude - elevation).roundToInt()
            if (separation(elevation, trueBearing, target.altitude, target.azimuth) < 6.0) {
                return "$requested should be near the center of your camera."
            }
            val horizontal = when {
                turn > 4 -> "turn about $turn degrees right"
                turn < -4 -> "turn about ${-turn} degrees left"
                else -> "keep this direction"
            }
            val vertical = when {
                lift > 4 -> "raise the phone about $lift degrees"
                lift < -4 -> "lower the phone about ${-lift} degrees"
                else -> "keep this height"
            }
            return "To find $requested, $horizontal and $vertical."
        }
        if ("describe" in q || "what do you see" in q || "what can i see" in q) {
            if (inView.isEmpty()) return "I can't match a bright catalog object in this camera direction. Fainter stars may still be there."
            return "The sky map places ${inView.take(3).joinToString { it.name }} in this direction. Check them against the camera view."
        }
        if ("what" in q || "star" in q || "bright" in q || "looking" in q || "in front" in q) {
            val nearest = inView.firstOrNull()
                ?: return "I can't identify a bright catalog object in front of the camera. Try pointing directly at it."
            val distance = separation(elevation, trueBearing, nearest.altitude, nearest.azimuth)
            return if (distance <= 8.0) {
                "The sky map places ${nearest.name} about ${distance.roundToInt()} degrees from center. Check it against what you see."
            } else {
                "${nearest.name} is in the camera's general direction, about ${distance.roundToInt()} degrees from center. Point closer for a better match."
            }
        }
        return "Ask what bright object is in front of you, describe this direction, or ask where to find Mars or the Moon."
    }
}
