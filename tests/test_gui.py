import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtGui import QColor, QPixmap
    from PySide6.QtWidgets import QApplication

    from daao.gui import CameraCompassWidget
except ImportError:
    QApplication = None
    CameraCompassWidget = None


@unittest.skipIf(QApplication is None, "PySide6 is not installed")
class GuiSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_widget_accepts_compass_state(self) -> None:
        widget = CameraCompassWidget()
        self.assertIn("GPS", widget.sky_missing_inputs())
        widget.resize(800, 450)
        widget.set_heading(359.5, 2.0)
        widget.set_attitude(15.0, -12.0)
        widget.set_sky_context(
            true_heading=1.5,
            latitude=52.3676,
            longitude=4.9041,
            observation_timestamp_ns=1_785_000_000_000_000_000,
        )
        widget.horizontal_fov = 74.0
        widget.show()
        self.app.processEvents()
        self.assertEqual(widget.heading, 359.5)
        self.assertEqual(widget.heading_accuracy, 2.0)
        self.assertEqual(widget.camera_elevation, 15.0)
        self.assertEqual(widget.camera_roll, -12.0)
        self.assertEqual(widget.true_heading, 1.5)
        self.assertEqual(widget.latitude, 52.3676)
        self.assertFalse(widget.grab().toImage().isNull())
        widget.close()

    def test_widget_paints_astronomical_overlay_on_camera_frame(self) -> None:
        widget = CameraCompassWidget()
        widget.resize(800, 450)
        widget._camera_pixmap = QPixmap(800, 450)
        widget._camera_pixmap.fill(QColor("#101820"))
        widget.set_heading(180.0, 2.0)
        widget.set_attitude(35.0, 0.0)
        widget.set_sky_context(
            true_heading=180.0,
            latitude=52.3676,
            longitude=4.9041,
            observation_timestamp_ns=1_785_000_000_000_000_000,
        )
        widget.show()
        self.app.processEvents()
        self.assertFalse(widget.grab().toImage().isNull())
        widget.close()


if __name__ == "__main__":
    unittest.main()
