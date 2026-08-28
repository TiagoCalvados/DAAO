import unittest

from daao.stars import (
    J2000_JULIAN_DATE,
    equatorial_to_horizontal,
    greenwich_sidereal_degrees,
    julian_date,
    project_horizontal,
    project_horizontal_to_viewport,
    solar_system_objects,
)


class StarPositionTests(unittest.TestCase):
    def test_unix_epoch_julian_date(self) -> None:
        self.assertEqual(julian_date(0), 2_440_587.5)

    def test_j2000_greenwich_sidereal_angle(self) -> None:
        self.assertAlmostEqual(
            greenwich_sidereal_degrees(J2000_JULIAN_DATE),
            280.46061837,
            places=8,
        )

    def test_equatorial_star_on_meridian_is_due_south(self) -> None:
        local_sidereal = greenwich_sidereal_degrees(J2000_JULIAN_DATE)
        position = equatorial_to_horizontal(
            local_sidereal,
            0.0,
            45.0,
            0.0,
            J2000_JULIAN_DATE,
            precess=False,
        )
        self.assertAlmostEqual(position.altitude_degrees, 45.0, places=8)
        self.assertAlmostEqual(position.azimuth_degrees, 180.0, places=8)

    def test_polaris_altitude_tracks_northern_latitude(self) -> None:
        position = equatorial_to_horizontal(
            37.954561,
            89.264109,
            52.0,
            5.0,
            2_460_000.5,
        )
        self.assertAlmostEqual(position.altitude_degrees, 52.0, delta=0.8)

    def test_camera_axis_projects_to_viewport_center(self) -> None:
        point = project_horizontal(25.0, 135.0, 25.0, 135.0, 0.0, 500.0, 400.0, 225.0)
        self.assertIsNotNone(point)
        assert point is not None
        self.assertAlmostEqual(point[0], 400.0, places=8)
        self.assertAlmostEqual(point[1], 225.0, places=8)

    def test_positive_roll_rotates_an_upward_star_clockwise(self) -> None:
        unrolled = project_horizontal(10.0, 0.0, 0.0, 0.0, 0.0, 500.0, 400.0, 225.0)
        rolled = project_horizontal(10.0, 0.0, 0.0, 0.0, 30.0, 500.0, 400.0, 225.0)
        assert unrolled is not None and rolled is not None
        self.assertAlmostEqual(unrolled[0], 400.0, places=8)
        self.assertLess(unrolled[1], 225.0)
        self.assertGreater(rolled[0], 400.0)
        self.assertLess(rolled[1], 225.0)

    def test_offscreen_object_gets_right_edge_chase_arrow(self) -> None:
        projection = project_horizontal_to_viewport(
            0.0,
            90.0,
            0.0,
            0.0,
            0.0,
            500.0,
            800.0,
            450.0,
        )
        self.assertFalse(projection.in_view)
        self.assertAlmostEqual(projection.x, 772.0, places=8)
        self.assertAlmostEqual(projection.y, 225.0, places=8)
        self.assertGreater(projection.direction_x, 0.99)
        self.assertAlmostEqual(projection.direction_y, 0.0, places=8)

    def test_offscreen_object_gets_top_edge_chase_arrow(self) -> None:
        projection = project_horizontal_to_viewport(
            80.0,
            0.0,
            0.0,
            0.0,
            0.0,
            500.0,
            800.0,
            450.0,
        )
        self.assertFalse(projection.in_view)
        self.assertAlmostEqual(projection.x, 400.0, places=8)
        self.assertAlmostEqual(projection.y, 28.0, places=8)
        self.assertLess(projection.direction_y, -0.99)

    def test_offscreen_object_gets_left_edge_chase_arrow(self) -> None:
        projection = project_horizontal_to_viewport(
            0.0,
            270.0,
            0.0,
            0.0,
            0.0,
            500.0,
            800.0,
            450.0,
        )
        self.assertFalse(projection.in_view)
        self.assertAlmostEqual(projection.x, 28.0, places=8)
        self.assertLess(projection.direction_x, -0.99)

    def test_above_horizon_object_can_get_bottom_edge_arrow(self) -> None:
        projection = project_horizontal_to_viewport(
            0.0,
            0.0,
            80.0,
            0.0,
            0.0,
            500.0,
            800.0,
            450.0,
        )
        self.assertFalse(projection.in_view)
        self.assertAlmostEqual(projection.y, 422.0, places=8)
        self.assertGreater(projection.direction_y, 0.99)

    def test_chase_arrow_follows_camera_roll(self) -> None:
        projection = project_horizontal_to_viewport(
            80.0,
            0.0,
            0.0,
            0.0,
            90.0,
            500.0,
            800.0,
            450.0,
        )
        self.assertFalse(projection.in_view)
        self.assertGreater(projection.direction_x, 0.99)
        self.assertAlmostEqual(projection.direction_y, 0.0, places=8)

    def test_object_behind_camera_still_has_chase_direction(self) -> None:
        projection = project_horizontal_to_viewport(
            0.0,
            179.0,
            0.0,
            0.0,
            0.0,
            500.0,
            800.0,
            450.0,
        )
        self.assertFalse(projection.in_view)
        self.assertGreater(projection.direction_x, 0.99)

    def test_solar_system_catalog_has_sun_and_seven_planets(self) -> None:
        objects = solar_system_objects(J2000_JULIAN_DATE)
        self.assertEqual(
            {item.name for item in objects},
            {"Sun", "Mercury", "Venus", "Mars", "Jupiter", "Saturn", "Uranus", "Neptune"},
        )
        sun = next(item for item in objects if item.name == "Sun")
        self.assertAlmostEqual(sun.right_ascension_degrees, 281.3, delta=0.2)
        self.assertAlmostEqual(sun.declination_degrees, -23.0, delta=0.2)


if __name__ == "__main__":
    unittest.main()
