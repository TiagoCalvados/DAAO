from __future__ import annotations

from dataclasses import dataclass, replace


@dataclass(frozen=True, slots=True)
class SensorUpdate:
    heading: float | None = None
    true_heading: float | None = None
    heading_accuracy: float | None = None
    camera_elevation: float | None = None
    camera_roll: float | None = None
    image: bytes | None = None
    image_timestamp_ns: int | None = None
    horizontal_fov: float | None = None
    latitude: float | None = None
    longitude: float | None = None
    altitude: float | None = None
    location_accuracy: float | None = None
    magnetic_declination: float | None = None
    message_id: int | None = None
    session_id: str | None = None
    device_id: str | None = None
    reading_count: int = 0

    def merged_with(self, newer: SensorUpdate) -> SensorUpdate:
        """Merge independently transported parts of the same update."""
        values = {}
        for field in (
            "heading",
            "true_heading",
            "heading_accuracy",
            "camera_elevation",
            "camera_roll",
            "image",
            "image_timestamp_ns",
            "horizontal_fov",
            "latitude",
            "longitude",
            "altitude",
            "location_accuracy",
            "magnetic_declination",
            "message_id",
            "session_id",
            "device_id",
        ):
            value = getattr(newer, field)
            if value is not None:
                values[field] = value
        values["reading_count"] = self.reading_count + newer.reading_count
        return replace(self, **values)
