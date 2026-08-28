import math
import unittest

from daao.attitude import normalize_roll, pitch_ladder_marks


class AttitudeTests(unittest.TestCase):
    def test_normalizes_roll(self) -> None:
        self.assertEqual(normalize_roll(0), 0)
        self.assertEqual(normalize_roll(181), -179)
        self.assertEqual(normalize_roll(-181), 179)

    def test_level_horizon_is_centered(self) -> None:
        marks = pitch_ladder_marks(0.0, 1000.0, 1000.0)
        horizon = next(mark for mark in marks if mark.is_horizon)
        self.assertEqual(horizon.offset_pixels, 0.0)
        self.assertEqual(horizon.label, "0°")

    def test_ladder_uses_perspective_projection(self) -> None:
        marks = pitch_ladder_marks(20.0, 1000.0, 1000.0)
        by_elevation = {mark.elevation: mark for mark in marks}
        self.assertTrue(math.isclose(by_elevation[20].offset_pixels, 0.0, abs_tol=1e-12))
        self.assertTrue(
            math.isclose(
                by_elevation[0].offset_pixels,
                1000.0 * math.tan(math.radians(20.0)),
                rel_tol=1e-12,
            )
        )
        self.assertLess(by_elevation[30].offset_pixels, 0.0)

    def test_filters_marks_outside_the_visible_area(self) -> None:
        marks = pitch_ladder_marks(0.0, 1000.0, 100.0)
        self.assertEqual([mark.elevation for mark in marks], [-5, 0, 5])


if __name__ == "__main__":
    unittest.main()
