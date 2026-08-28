from __future__ import annotations

from dataclasses import dataclass
import math


@dataclass(frozen=True, slots=True)
class PitchMark:
    elevation: int
    offset_pixels: float
    label: str
    is_horizon: bool
    is_major: bool


def normalize_roll(roll: float) -> float:
    """Normalize camera roll to the half-open range [-180, 180)."""
    return (float(roll) + 180.0) % 360.0 - 180.0


def pitch_ladder_marks(
    camera_elevation: float,
    focal_pixels: float,
    maximum_offset_pixels: float,
    step_degrees: int = 5,
) -> tuple[PitchMark, ...]:
    """Project constant-elevation pitch marks into the camera image."""
    if not math.isfinite(camera_elevation) or not -90.0 <= camera_elevation <= 90.0:
        raise ValueError("camera_elevation must be between -90 and 90 degrees")
    if not math.isfinite(focal_pixels) or focal_pixels <= 0.0:
        raise ValueError("focal_pixels must be positive")
    if not math.isfinite(maximum_offset_pixels) or maximum_offset_pixels <= 0.0:
        raise ValueError("maximum_offset_pixels must be positive")
    if step_degrees <= 0 or 90 % step_degrees:
        raise ValueError("step_degrees must divide 90")

    marks = []
    for elevation in range(-90, 91, step_degrees):
        delta = camera_elevation - elevation
        if not -89.0 < delta < 89.0:
            continue
        offset = focal_pixels * math.tan(math.radians(delta))
        if abs(offset) > maximum_offset_pixels:
            continue
        marks.append(
            PitchMark(
                elevation=elevation,
                offset_pixels=offset,
                label=f"{elevation:+d}°" if elevation else "0°",
                is_horizon=elevation == 0,
                is_major=elevation % 10 == 0,
            )
        )
    return tuple(marks)
