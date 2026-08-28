from __future__ import annotations

import base64
import binascii
from collections.abc import Mapping, Sequence
from email import policy
from email.parser import BytesParser
import json
import re
from typing import Any

from daao.attitude import normalize_roll
from daao.compass import normalize_heading
from daao.models import SensorUpdate


IMAGE_NAMES = {"camera", "image", "photo", "picture", "cameraimage"}
IMAGE_KEYS = (
    "imageBase64",
    "image_base64",
    "base64Data",
    "base64",
    "imageData",
    "image_data",
    "image",
    "photo",
    "jpeg",
    "jpg",
)
GENERIC_IMAGE_KEYS = ("data", "bytes", "content", "value")
HEADING_KEYS = (
    "magneticBearing",
    "magnetic_bearing",
    "magneticHeading",
    "heading",
    "bearing",
    "azimuth",
)
MAGNETIC_HEADING_KEYS = HEADING_KEYS[:3]
TRUE_HEADING_KEYS = (
    "trueBearing",
    "true_bearing",
    "trueHeading",
    "true_heading",
)
LATITUDE_KEYS = ("latitude", "lat")
LONGITUDE_KEYS = ("longitude", "lon", "lng")
ALTITUDE_KEYS = ("altitude", "altitudeMeters", "altitude_meters")
LOCATION_ACCURACY_KEYS = (
    "horizontalAccuracy",
    "locationAccuracy",
    "accuracyMeters",
)
DECLINATION_KEYS = (
    "magneticDeclination",
    "magnetic_declination",
    "declination",
)
CAMERA_ELEVATION_KEYS = (
    "cameraElevation",
    "camera_elevation",
    "elevation",
    "pitch",
)
CAMERA_ROLL_KEYS = (
    "cameraRoll",
    "camera_roll",
    "roll",
)
FOV_KEYS = (
    "horizontalFov",
    "horizontalFOV",
    "horizontal_fov",
    "horizontalFieldOfView",
    "fieldOfView",
    "fov",
)
DATA_URI = re.compile(r"^data:image/[^;,]+;base64,(.*)$", re.IGNORECASE | re.DOTALL)


class PayloadError(ValueError):
    """Raised when an HTTP body cannot be interpreted as Sensor Logger data."""


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    if result != result or result in (float("inf"), float("-inf")):
        return None
    return result


def _integer(value: Any) -> int | None:
    number = _number(value)
    return int(number) if number is not None else None


def _looks_like_image(data: bytes) -> bool:
    return (
        data.startswith(b"\xff\xd8\xff")
        or data.startswith(b"\x89PNG\r\n\x1a\n")
        or (len(data) >= 12 and data.startswith(b"RIFF") and data[8:12] == b"WEBP")
    )


def decode_image_value(value: Any) -> bytes | None:
    """Decode common Sensor Logger camera representations."""
    if isinstance(value, bytes):
        return value if _looks_like_image(value) else None
    if isinstance(value, bytearray):
        data = bytes(value)
        return data if _looks_like_image(data) else None
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        try:
            data = bytes(value)
        except (TypeError, ValueError):
            return None
        return data if _looks_like_image(data) else None
    if not isinstance(value, str):
        return None

    text = value.strip()
    match = DATA_URI.match(text)
    if match:
        text = match.group(1)
    text = "".join(text.split())
    if not text:
        return None
    text += "=" * (-len(text) % 4)
    try:
        data = base64.b64decode(text, validate=True)
    except (binascii.Error, ValueError):
        try:
            data = base64.urlsafe_b64decode(text)
        except (binascii.Error, ValueError):
            return None
    return data if _looks_like_image(data) else None


def _mapping_values(reading: Mapping[str, Any]) -> Mapping[str, Any]:
    values = reading.get("values")
    return values if isinstance(values, Mapping) else {}


def _reading_name(reading: Mapping[str, Any]) -> str:
    raw = reading.get("name", reading.get("sensor", reading.get("type", "")))
    return re.sub(r"[^a-z]", "", str(raw).lower())


def _first_number(mappings: Sequence[Mapping[str, Any]], keys: Sequence[str]) -> float | None:
    for mapping in mappings:
        for key in keys:
            if key in mapping:
                number = _number(mapping[key])
                if number is not None:
                    return number
    return None


def _image_from_reading(reading: Mapping[str, Any], is_camera: bool) -> bytes | None:
    values = _mapping_values(reading)
    mappings = (values, reading)
    for mapping in mappings:
        for key in IMAGE_KEYS:
            if key in mapping:
                image = decode_image_value(mapping[key])
                if image is not None:
                    return image
        if is_camera:
            for key in GENERIC_IMAGE_KEYS:
                if key in mapping:
                    image = decode_image_value(mapping[key])
                    if image is not None:
                        return image
    return None


def _top_level_image(document: Mapping[str, Any]) -> bytes | None:
    for key in IMAGE_KEYS:
        if key in document:
            image = decode_image_value(document[key])
            if image is not None:
                return image
    return None


def parse_sensor_logger_message(document: Any) -> SensorUpdate:
    """Parse a documented Sensor Logger JSON batch into a display update."""
    if isinstance(document, list):
        payload = document
        metadata: Mapping[str, Any] = {}
    elif isinstance(document, Mapping):
        metadata = document
        raw_payload = document.get("payload", [])
        if isinstance(raw_payload, Mapping):
            payload = [raw_payload]
        elif isinstance(raw_payload, list):
            payload = raw_payload
        elif raw_payload is None:
            payload = []
        else:
            raise PayloadError("'payload' must be an array or object")
    else:
        raise PayloadError("JSON body must be an object or array")

    heading = None
    true_heading = _first_number((metadata,), TRUE_HEADING_KEYS)
    if true_heading is not None:
        true_heading = normalize_heading(true_heading)
    heading_accuracy = None
    heading_time = -1
    camera_elevation = _first_number((metadata,), CAMERA_ELEVATION_KEYS)
    if camera_elevation is not None and not -90.0 <= camera_elevation <= 90.0:
        camera_elevation = None
    elevation_time = -1
    camera_roll = _first_number((metadata,), CAMERA_ROLL_KEYS)
    if camera_roll is not None:
        camera_roll = normalize_roll(camera_roll)
    roll_time = -1
    image = _top_level_image(metadata)
    image_time = _integer(metadata.get("imageTimestampNs"))
    if image_time is None and image is not None:
        image_time = _integer(metadata.get("time"))
    latest_image_time = image_time if image_time is not None else -1
    horizontal_fov = _first_number((metadata,), FOV_KEYS)
    latitude = _first_number((metadata,), LATITUDE_KEYS)
    longitude = _first_number((metadata,), LONGITUDE_KEYS)
    altitude = _first_number((metadata,), ALTITUDE_KEYS)
    location_accuracy = _first_number((metadata,), LOCATION_ACCURACY_KEYS)
    magnetic_declination = _first_number((metadata,), DECLINATION_KEYS)
    location_time = -1
    reading_count = 0

    for raw_reading in payload:
        if not isinstance(raw_reading, Mapping):
            continue
        reading_count += 1
        values = _mapping_values(raw_reading)
        name = _reading_name(raw_reading)
        timestamp = _integer(raw_reading.get("time"))
        ordering_time = timestamp if timestamp is not None else reading_count

        is_compass = name in {"compass", "heading", "magneticbearing"} or "compass" in name
        heading_keys = HEADING_KEYS if is_compass else MAGNETIC_HEADING_KEYS
        bearing = _first_number((values, raw_reading), heading_keys)
        if bearing is not None:
            if ordering_time >= heading_time:
                heading = normalize_heading(bearing)
                heading_time = ordering_time
                heading_accuracy = _first_number(
                    (values, raw_reading),
                    ("headingAccuracy", "bearingAccuracy", "accuracy"),
                )
        candidate_true_heading = _first_number(
            (values, raw_reading),
            TRUE_HEADING_KEYS,
        )
        if candidate_true_heading is not None and ordering_time >= heading_time:
            true_heading = normalize_heading(candidate_true_heading)

        is_orientation = (
            name in {"orientation", "attitude", "rotation"}
            or "orientation" in name
            or "attitude" in name
        )
        if is_orientation:
            candidate_elevation = _first_number(
                (values, raw_reading),
                CAMERA_ELEVATION_KEYS,
            )
            if (
                candidate_elevation is not None
                and -90.0 <= candidate_elevation <= 90.0
                and ordering_time >= elevation_time
            ):
                camera_elevation = candidate_elevation
                elevation_time = ordering_time

            candidate_roll = _first_number(
                (values, raw_reading),
                CAMERA_ROLL_KEYS,
            )
            if candidate_roll is not None and ordering_time >= roll_time:
                camera_roll = normalize_roll(candidate_roll)
                roll_time = ordering_time

        is_camera = name in IMAGE_NAMES or "camera" in name or "image" in name
        candidate_image = _image_from_reading(raw_reading, is_camera)
        if candidate_image is not None and ordering_time >= latest_image_time:
            image = candidate_image
            image_time = timestamp
            latest_image_time = ordering_time

        candidate_fov = _first_number((values, raw_reading), FOV_KEYS)
        if candidate_fov is not None and 1.0 < candidate_fov < 179.0:
            horizontal_fov = candidate_fov

        is_location = name in {"location", "gps", "position"} or "location" in name
        if is_location and ordering_time >= location_time:
            candidate_latitude = _first_number(
                (values, raw_reading),
                LATITUDE_KEYS,
            )
            candidate_longitude = _first_number(
                (values, raw_reading),
                LONGITUDE_KEYS,
            )
            if (
                candidate_latitude is not None
                and candidate_longitude is not None
                and -90.0 <= candidate_latitude <= 90.0
                and -180.0 <= candidate_longitude <= 180.0
            ):
                latitude = candidate_latitude
                longitude = candidate_longitude
                altitude = _first_number((values, raw_reading), ALTITUDE_KEYS)
                location_accuracy = _first_number(
                    (values, raw_reading),
                    LOCATION_ACCURACY_KEYS,
                )
                magnetic_declination = _first_number(
                    (values, raw_reading),
                    DECLINATION_KEYS,
                )
                location_time = ordering_time

    if horizontal_fov is not None and not 1.0 < horizontal_fov < 179.0:
        horizontal_fov = None
    if latitude is None or not -90.0 <= latitude <= 90.0:
        latitude = None
    if longitude is None or not -180.0 <= longitude <= 180.0:
        longitude = None
    if location_accuracy is not None and location_accuracy < 0.0:
        location_accuracy = None
    if true_heading is None and heading is not None and magnetic_declination is not None:
        true_heading = normalize_heading(heading + magnetic_declination)

    return SensorUpdate(
        heading=heading,
        true_heading=true_heading,
        heading_accuracy=heading_accuracy,
        camera_elevation=camera_elevation,
        camera_roll=camera_roll,
        image=image,
        image_timestamp_ns=image_time,
        horizontal_fov=horizontal_fov,
        latitude=latitude,
        longitude=longitude,
        altitude=altitude,
        location_accuracy=location_accuracy,
        magnetic_declination=magnetic_declination,
        message_id=_integer(metadata.get("messageId")),
        session_id=_optional_string(metadata.get("sessionId")),
        device_id=_optional_string(metadata.get("deviceId")),
        reading_count=reading_count,
    )


def _optional_string(value: Any) -> str | None:
    return str(value) if value is not None else None


def _parse_json(data: bytes) -> SensorUpdate:
    try:
        document = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise PayloadError(f"invalid JSON: {error}") from error
    return parse_sensor_logger_message(document)


def _parse_multipart(content_type: str, body: bytes) -> SensorUpdate:
    envelope = (
        f"Content-Type: {content_type}\r\nMIME-Version: 1.0\r\n\r\n".encode("ascii")
        + body
    )
    message = BytesParser(policy=policy.default).parsebytes(envelope)
    if not message.is_multipart():
        raise PayloadError("invalid multipart body")

    update = SensorUpdate()
    found = False
    for part in message.iter_parts():
        data = part.get_payload(decode=True) or b""
        part_type = part.get_content_type().lower()
        if part_type == "application/json" or part.get_param("name", header="content-disposition") == "data":
            update = update.merged_with(_parse_json(data))
            found = True
        elif part_type.startswith("image/"):
            if not _looks_like_image(data):
                raise PayloadError("multipart image is not JPEG, PNG, or WebP")
            update = update.merged_with(SensorUpdate(image=data))
            found = True
    if not found:
        raise PayloadError("multipart body contains no JSON or image part")
    return update


def parse_http_payload(content_type: str, body: bytes) -> SensorUpdate:
    """Parse JSON, raw image, or multipart Sensor Logger HTTP bodies."""
    media_type = content_type.partition(";")[0].strip().lower()
    if media_type in ("application/json", "text/json", ""):
        return _parse_json(body)
    if media_type.startswith("image/"):
        if not _looks_like_image(body):
            raise PayloadError("image body is not JPEG, PNG, or WebP")
        return SensorUpdate(image=body)
    if media_type.startswith("multipart/"):
        return _parse_multipart(content_type, body)
    raise PayloadError(f"unsupported Content-Type: {media_type}")
