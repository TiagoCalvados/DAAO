from __future__ import annotations

from dataclasses import dataclass
import math


J2000_JULIAN_DATE = 2_451_545.0


@dataclass(frozen=True, slots=True)
class Star:
    """A named star in the J2000 equatorial reference frame."""

    name: str
    right_ascension_degrees: float
    declination_degrees: float
    magnitude: float
    kind: str = "star"


@dataclass(frozen=True, slots=True)
class HorizontalPosition:
    """A local sky position: azimuth is clockwise from true north."""

    altitude_degrees: float
    azimuth_degrees: float


@dataclass(frozen=True, slots=True)
class ProjectedStar:
    star: Star
    altitude_degrees: float
    azimuth_degrees: float
    x: float
    y: float
    in_view: bool
    direction_x: float
    direction_y: float


@dataclass(frozen=True, slots=True)
class ViewportProjection:
    x: float
    y: float
    in_view: bool
    direction_x: float
    direction_y: float


# A compact naked-eye catalog of bright and navigational stars. Coordinates and
# magnitudes use the IAU Working Group on Star Names table (J2000).
BRIGHT_STARS = (
    Star("Sirius", 101.287155, -16.716116, -1.44),
    Star("Canopus", 95.987958, -52.695661, -0.62),
    Star("Rigil Kentaurus", 219.902066, -60.833975, -0.01),
    Star("Arcturus", 213.915300, 19.182409, -0.05),
    Star("Vega", 279.234735, 38.783689, 0.03),
    Star("Capella", 79.172328, 45.997991, 0.08),
    Star("Rigel", 78.634467, -8.201638, 0.18),
    Star("Procyon", 114.825493, 5.224993, 0.40),
    Star("Betelgeuse", 88.792939, 7.407064, 0.45),
    Star("Achernar", 24.428523, -57.236753, 0.45),
    Star("Hadar", 210.955856, -60.373035, 0.61),
    Star("Altair", 297.695827, 8.868321, 0.76),
    Star("Aldebaran", 68.980163, 16.509302, 0.87),
    Star("Spica", 201.298247, -11.161319, 0.98),
    Star("Antares", 247.351915, -26.432003, 1.06),
    Star("Pollux", 116.328958, 28.026199, 1.16),
    Star("Fomalhaut", 344.412693, -29.622237, 1.17),
    Star("Deneb", 310.357980, 45.280339, 1.25),
    Star("Mimosa", 191.930263, -59.688764, 1.25),
    Star("Acrux", 186.649563, -63.099093, 1.33),
    Star("Regulus", 152.092962, 11.967209, 1.36),
    Star("Adhara", 104.656453, -28.972086, 1.50),
    Star("Gacrux", 187.791498, -57.113213, 1.59),
    Star("Bellatrix", 81.282764, 6.349703, 1.64),
    Star("Elnath", 81.572971, 28.607452, 1.65),
    Star("Polaris", 37.954561, 89.264109, 1.97),
    Star("Castor", 113.649428, 31.888276, 1.98),
)


@dataclass(frozen=True, slots=True)
class _OrbitalElements:
    base: tuple[float, float, float, float, float, float]
    rate: tuple[float, float, float, float, float, float]
    anomaly_terms: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)


# JPL approximate elements for 3000 BC–3000 AD. Entries are a, e, I, L,
# longitude of perihelion, and longitude of ascending node, followed by their
# rates per Julian century. The long-range anomaly terms apply to outer planets.
_ORBITS = {
    "Mercury": _OrbitalElements(
        (0.38709843, 0.20563661, 7.00559432, 252.25166724, 77.45771895, 48.33961819),
        (0.0, 0.00002123, -0.00590158, 149472.67486623, 0.15940013, -0.12214182),
    ),
    "Venus": _OrbitalElements(
        (0.72332102, 0.00676399, 3.39777545, 181.97970850, 131.76755713, 76.67261496),
        (-0.00000026, -0.00005107, 0.00043494, 58517.81560260, 0.05679648, -0.27274174),
    ),
    "Earth": _OrbitalElements(
        (1.00000018, 0.01673163, -0.00054346, 100.46691572, 102.93005885, -5.11260389),
        (-0.00000003, -0.00003661, -0.01337178, 35999.37306329, 0.31795260, -0.24123856),
    ),
    "Mars": _OrbitalElements(
        (1.52371243, 0.09336511, 1.85181869, -4.56813164, -23.91744784, 49.71320984),
        (0.00000097, 0.00009149, -0.00724757, 19140.29934243, 0.45223625, -0.26852431),
    ),
    "Jupiter": _OrbitalElements(
        (5.20248019, 0.04853590, 1.29861416, 34.33479152, 14.27495244, 100.29282654),
        (-0.00002864, 0.00018026, -0.00322699, 3034.90371757, 0.18199196, 0.13024619),
        (-0.00012452, 0.06064060, -0.35635438, 38.35125000),
    ),
    "Saturn": _OrbitalElements(
        (9.54149883, 0.05550825, 2.49424102, 50.07571329, 92.86136063, 113.63998702),
        (-0.00003065, -0.00032044, 0.00451969, 1222.11494724, 0.54179478, -0.25015002),
        (0.00025899, -0.13434469, 0.87320147, 38.35125000),
    ),
    "Uranus": _OrbitalElements(
        (19.18797948, 0.04685740, 0.77298127, 314.20276625, 172.43404441, 73.96250215),
        (-0.00020455, -0.00001550, -0.00180155, 428.49512595, 0.09266985, 0.05739699),
        (0.00058331, -0.97731848, 0.17689245, 7.67025000),
    ),
    "Neptune": _OrbitalElements(
        (30.06952752, 0.00895439, 1.77005520, 304.22289287, 46.68158724, 131.78635853),
        (0.00006447, 0.00000818, 0.00022400, 218.46515314, 0.01009938, -0.00606302),
        (-0.00041348, 0.68346318, -0.10162547, 7.67025000),
    ),
}

_PLANET_MAGNITUDES = {
    "Mercury": -0.5,
    "Venus": -4.4,
    "Mars": -1.5,
    "Jupiter": -2.7,
    "Saturn": 0.5,
    "Uranus": 5.7,
    "Neptune": 7.8,
}


def julian_date(epoch_nanoseconds: int) -> float:
    """Convert Unix epoch nanoseconds to a Julian date in UTC."""
    return 2_440_587.5 + epoch_nanoseconds / 1_000_000_000.0 / 86_400.0


def greenwich_sidereal_degrees(julian_date_utc: float) -> float:
    """Return Greenwich mean sidereal time using a standard low-order model."""
    days = julian_date_utc - J2000_JULIAN_DATE
    centuries = days / 36_525.0
    angle = (
        280.46061837
        + 360.98564736629 * days
        + 0.000387933 * centuries * centuries
        - centuries * centuries * centuries / 38_710_000.0
    )
    return angle % 360.0


def precess_j2000(
    right_ascension_degrees: float,
    declination_degrees: float,
    julian_date_utc: float,
) -> tuple[float, float]:
    """Precess J2000 coordinates to the observation date (IAU 1976 model)."""
    centuries = (julian_date_utc - J2000_JULIAN_DATE) / 36_525.0
    zeta = math.radians(
        (
            2306.2181 * centuries
            + 0.30188 * centuries**2
            + 0.017998 * centuries**3
        )
        / 3600.0
    )
    z = math.radians(
        (
            2306.2181 * centuries
            + 1.09468 * centuries**2
            + 0.018203 * centuries**3
        )
        / 3600.0
    )
    theta = math.radians(
        (
            2004.3109 * centuries
            - 0.42665 * centuries**2
            - 0.041833 * centuries**3
        )
        / 3600.0
    )

    right_ascension = math.radians(right_ascension_degrees)
    declination = math.radians(declination_degrees)
    a = math.cos(declination) * math.sin(right_ascension + zeta)
    b = (
        math.cos(theta) * math.cos(declination) * math.cos(right_ascension + zeta)
        - math.sin(theta) * math.sin(declination)
    )
    c = (
        math.sin(theta) * math.cos(declination) * math.cos(right_ascension + zeta)
        + math.cos(theta) * math.sin(declination)
    )
    return (math.degrees(math.atan2(a, b) + z) % 360.0, math.degrees(math.asin(c)))


def _heliocentric_ecliptic(
    elements: _OrbitalElements,
    centuries: float,
) -> tuple[float, float, float]:
    a, eccentricity, inclination, longitude, perihelion, node = (
        base + rate * centuries for base, rate in zip(elements.base, elements.rate)
    )
    b, c, s, f = elements.anomaly_terms
    mean_anomaly = math.radians(
        (
            longitude
            - perihelion
            + b * centuries**2
            + c * math.cos(math.radians(f * centuries))
            + s * math.sin(math.radians(f * centuries))
        )
        % 360.0
    )
    eccentric_anomaly = mean_anomaly
    for _ in range(12):
        correction = (
            eccentric_anomaly
            - eccentricity * math.sin(eccentric_anomaly)
            - mean_anomaly
        ) / (1.0 - eccentricity * math.cos(eccentric_anomaly))
        eccentric_anomaly -= correction
        if abs(correction) < 1e-12:
            break

    orbital_x = a * (math.cos(eccentric_anomaly) - eccentricity)
    orbital_y = a * math.sqrt(1.0 - eccentricity**2) * math.sin(eccentric_anomaly)
    argument = math.radians(perihelion - node)
    node = math.radians(node)
    inclination = math.radians(inclination)
    return (
        (
            math.cos(argument) * math.cos(node)
            - math.sin(argument) * math.sin(node) * math.cos(inclination)
        )
        * orbital_x
        + (
            -math.sin(argument) * math.cos(node)
            - math.cos(argument) * math.sin(node) * math.cos(inclination)
        )
        * orbital_y,
        (
            math.cos(argument) * math.sin(node)
            + math.sin(argument) * math.cos(node) * math.cos(inclination)
        )
        * orbital_x
        + (
            -math.sin(argument) * math.sin(node)
            + math.cos(argument) * math.cos(node) * math.cos(inclination)
        )
        * orbital_y,
        math.sin(argument) * math.sin(inclination) * orbital_x
        + math.cos(argument) * math.sin(inclination) * orbital_y,
    )


def solar_system_objects(julian_date_utc: float) -> tuple[Star, ...]:
    """Approximate geocentric J2000 positions of the Sun and other planets."""
    centuries = (julian_date_utc - J2000_JULIAN_DATE) / 36_525.0
    earth = _heliocentric_ecliptic(_ORBITS["Earth"], centuries)
    vectors = {"Sun": tuple(-coordinate for coordinate in earth)}
    for name, elements in _ORBITS.items():
        if name != "Earth":
            planet = _heliocentric_ecliptic(elements, centuries)
            vectors[name] = tuple(planet[index] - earth[index] for index in range(3))

    obliquity = math.radians(23.43928)
    result = []
    for name, (ecliptic_x, ecliptic_y, ecliptic_z) in vectors.items():
        equatorial_x = ecliptic_x
        equatorial_y = (
            math.cos(obliquity) * ecliptic_y - math.sin(obliquity) * ecliptic_z
        )
        equatorial_z = (
            math.sin(obliquity) * ecliptic_y + math.cos(obliquity) * ecliptic_z
        )
        right_ascension = math.degrees(math.atan2(equatorial_y, equatorial_x)) % 360.0
        declination = math.degrees(
            math.atan2(
                equatorial_z,
                math.hypot(equatorial_x, equatorial_y),
            )
        )
        result.append(
            Star(
                name,
                right_ascension,
                declination,
                -26.74 if name == "Sun" else _PLANET_MAGNITUDES[name],
                "sun" if name == "Sun" else "planet",
            )
        )
    return tuple(result)


def equatorial_to_horizontal(
    right_ascension_degrees: float,
    declination_degrees: float,
    latitude_degrees: float,
    longitude_degrees: float,
    julian_date_utc: float,
    *,
    precess: bool = True,
) -> HorizontalPosition:
    """Convert equatorial coordinates into local geometric altitude/azimuth."""
    if precess:
        right_ascension_degrees, declination_degrees = precess_j2000(
            right_ascension_degrees,
            declination_degrees,
            julian_date_utc,
        )

    local_sidereal = (
        greenwich_sidereal_degrees(julian_date_utc) + longitude_degrees
    ) % 360.0
    hour_angle = math.radians((local_sidereal - right_ascension_degrees) % 360.0)
    declination = math.radians(declination_degrees)
    latitude = math.radians(latitude_degrees)

    altitude = math.asin(
        math.sin(declination) * math.sin(latitude)
        + math.cos(declination) * math.cos(latitude) * math.cos(hour_angle)
    )
    # This form returns azimuth clockwise from true north after adding 180°.
    azimuth = math.atan2(
        math.sin(hour_angle),
        math.cos(hour_angle) * math.sin(latitude)
        - math.tan(declination) * math.cos(latitude),
    )
    return HorizontalPosition(
        altitude_degrees=math.degrees(altitude),
        azimuth_degrees=(math.degrees(azimuth) + 180.0) % 360.0,
    )


def project_horizontal(
    altitude_degrees: float,
    azimuth_degrees: float,
    camera_elevation_degrees: float,
    camera_azimuth_degrees: float,
    camera_roll_degrees: float,
    focal_pixels: float,
    center_x: float,
    center_y: float,
) -> tuple[float, float] | None:
    """Project a local sky direction through a rolled pinhole camera."""
    camera_x, camera_y, camera_z = _camera_components(
        altitude_degrees,
        azimuth_degrees,
        camera_elevation_degrees,
        camera_azimuth_degrees,
        camera_roll_degrees,
    )
    if camera_z <= 0.0:
        return None
    return (
        center_x + focal_pixels * camera_x / camera_z,
        center_y - focal_pixels * camera_y / camera_z,
    )


def _camera_components(
    altitude_degrees: float,
    azimuth_degrees: float,
    camera_elevation_degrees: float,
    camera_azimuth_degrees: float,
    camera_roll_degrees: float,
) -> tuple[float, float, float]:
    """Express a local sky direction in the rolled camera coordinate frame."""
    altitude = math.radians(altitude_degrees)
    azimuth = math.radians(azimuth_degrees)
    elevation = math.radians(camera_elevation_degrees)
    camera_azimuth = math.radians(camera_azimuth_degrees)
    roll = math.radians(camera_roll_degrees)

    direction = (
        math.cos(altitude) * math.sin(azimuth),
        math.cos(altitude) * math.cos(azimuth),
        math.sin(altitude),
    )
    forward = (
        math.cos(elevation) * math.sin(camera_azimuth),
        math.cos(elevation) * math.cos(camera_azimuth),
        math.sin(elevation),
    )
    unrolled_right = (math.cos(camera_azimuth), -math.sin(camera_azimuth), 0.0)
    unrolled_up = (
        -math.sin(elevation) * math.sin(camera_azimuth),
        -math.sin(elevation) * math.cos(camera_azimuth),
        math.cos(elevation),
    )
    right = tuple(
        unrolled_right[index] * math.cos(roll)
        + unrolled_up[index] * math.sin(roll)
        for index in range(3)
    )
    up = tuple(
        -unrolled_right[index] * math.sin(roll)
        + unrolled_up[index] * math.cos(roll)
        for index in range(3)
    )

    return (
        sum(direction[index] * right[index] for index in range(3)),
        sum(direction[index] * up[index] for index in range(3)),
        sum(direction[index] * forward[index] for index in range(3)),
    )


def project_horizontal_to_viewport(
    altitude_degrees: float,
    azimuth_degrees: float,
    camera_elevation_degrees: float,
    camera_azimuth_degrees: float,
    camera_roll_degrees: float,
    focal_pixels: float,
    viewport_width: float,
    viewport_height: float,
    edge_margin_pixels: float = 28.0,
) -> ViewportProjection:
    """Project a direction into the view or onto an oriented viewport edge."""
    camera_x, camera_y, camera_z = _camera_components(
        altitude_degrees,
        azimuth_degrees,
        camera_elevation_degrees,
        camera_azimuth_degrees,
        camera_roll_degrees,
    )
    center_x = viewport_width / 2.0
    center_y = viewport_height / 2.0
    if camera_z > 0.0:
        x = center_x + focal_pixels * camera_x / camera_z
        y = center_y - focal_pixels * camera_y / camera_z
        if 0.0 <= x <= viewport_width and 0.0 <= y <= viewport_height:
            return ViewportProjection(x, y, True, 0.0, 0.0)

    # Angular displacement gives a stable chase direction even for an object
    # behind the camera, where ordinary pinhole projection is undefined.
    horizontal_angle = math.atan2(camera_x, camera_z)
    vertical_angle = math.atan2(camera_y, math.hypot(camera_x, camera_z))
    horizontal_half_fov = math.atan(viewport_width / (2.0 * focal_pixels))
    vertical_half_fov = math.atan(viewport_height / (2.0 * focal_pixels))
    direction_x = horizontal_angle / max(horizontal_half_fov, 1e-9)
    direction_y = -vertical_angle / max(vertical_half_fov, 1e-9)
    length = math.hypot(direction_x, direction_y)
    if length < 1e-9:
        direction_x = 1.0
        direction_y = 0.0
        length = 1.0

    margin = min(
        max(0.0, edge_margin_pixels),
        max(0.0, center_x - 1.0),
        max(0.0, center_y - 1.0),
    )
    safe_half_width = max(1.0, center_x - margin)
    safe_half_height = max(1.0, center_y - margin)
    scale = min(
        safe_half_width / abs(direction_x) if abs(direction_x) > 1e-9 else math.inf,
        safe_half_height / abs(direction_y) if abs(direction_y) > 1e-9 else math.inf,
    )
    return ViewportProjection(
        x=center_x + direction_x * scale,
        y=center_y + direction_y * scale,
        in_view=False,
        direction_x=direction_x / length,
        direction_y=direction_y / length,
    )


def project_sky_objects(
    *,
    latitude_degrees: float,
    longitude_degrees: float,
    epoch_nanoseconds: int,
    camera_elevation_degrees: float,
    camera_azimuth_degrees: float,
    camera_roll_degrees: float,
    focal_pixels: float,
    viewport_width: float,
    viewport_height: float,
    catalog: tuple[Star, ...] | None = None,
    edge_margin_pixels: float = 28.0,
) -> list[ProjectedStar]:
    """Project all above-horizon objects into the view or onto its border."""
    date = julian_date(epoch_nanoseconds)
    result: list[ProjectedStar] = []
    objects = catalog if catalog is not None else BRIGHT_STARS + solar_system_objects(date)
    for star in objects:
        horizontal = equatorial_to_horizontal(
            star.right_ascension_degrees,
            star.declination_degrees,
            latitude_degrees,
            longitude_degrees,
            date,
        )
        if horizontal.altitude_degrees < 0.0:
            continue
        projection = project_horizontal_to_viewport(
            horizontal.altitude_degrees,
            horizontal.azimuth_degrees,
            camera_elevation_degrees,
            camera_azimuth_degrees,
            camera_roll_degrees,
            focal_pixels,
            viewport_width,
            viewport_height,
            edge_margin_pixels,
        )
        result.append(
            ProjectedStar(
                star=star,
                altitude_degrees=horizontal.altitude_degrees,
                azimuth_degrees=horizontal.azimuth_degrees,
                x=projection.x,
                y=projection.y,
                in_view=projection.in_view,
                direction_x=projection.direction_x,
                direction_y=projection.direction_y,
            )
        )
    return sorted(result, key=lambda item: item.star.magnitude)


def project_visible_stars(
    *,
    latitude_degrees: float,
    longitude_degrees: float,
    epoch_nanoseconds: int,
    camera_elevation_degrees: float,
    camera_azimuth_degrees: float,
    camera_roll_degrees: float,
    focal_pixels: float,
    viewport_width: float,
    viewport_height: float,
    catalog: tuple[Star, ...] | None = None,
) -> list[ProjectedStar]:
    """Return only objects that project inside the viewport."""
    return [
        item
        for item in project_sky_objects(
            latitude_degrees=latitude_degrees,
            longitude_degrees=longitude_degrees,
            epoch_nanoseconds=epoch_nanoseconds,
            camera_elevation_degrees=camera_elevation_degrees,
            camera_azimuth_degrees=camera_azimuth_degrees,
            camera_roll_degrees=camera_roll_degrees,
            focal_pixels=focal_pixels,
            viewport_width=viewport_width,
            viewport_height=viewport_height,
            catalog=catalog,
        )
        if item.in_view
    ]
