from __future__ import annotations

from datetime import datetime
import math
import time

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, Slot
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontDatabase,
    QLinearGradient,
    QPainter,
    QPen,
    QPixmap,
    QPolygonF,
)
from PySide6.QtWidgets import (
    QDoubleSpinBox,
    QLabel,
    QMainWindow,
    QSizePolicy,
    QStatusBar,
)

from daao import __version__
from daao.attitude import pitch_ladder_marks
from daao.compass import compass_marks, focal_length_pixels, project_delta_to_x
from daao.models import SensorUpdate
from daao.stars import ProjectedStar, project_sky_objects


def overlay_font(point_size: int, weight: QFont.Weight) -> QFont:
    """Resolve a platform monospace font without assuming a family is installed."""
    font = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
    font.setStyleHint(QFont.StyleHint.Monospace)
    font.setPointSize(point_size)
    font.setWeight(weight)
    return font


class CameraCompassWidget(QLabel):
    TAPE_HEIGHT = 112
    ROLL_SCALE_TICKS = (-60, -45, -30, -20, -10, 0, 10, 20, 30, 45, 60)

    def __init__(self) -> None:
        super().__init__()
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumSize(640, 360)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setStyleSheet("background: #03070b;")
        self._camera_pixmap: QPixmap | None = None
        self.heading: float | None = None
        self.true_heading: float | None = None
        self.heading_accuracy: float | None = None
        self.camera_elevation: float | None = None
        self.camera_roll: float | None = None
        self.horizontal_fov = 74.0
        self.bearing_offset = 0.0
        self.latitude: float | None = None
        self.longitude: float | None = None
        self.observation_timestamp_ns: int | None = None
        self.location_accuracy: float | None = None
        self.sky_in_view_count = 0
        self.sky_offscreen_count = 0

    def set_camera_image(self, data: bytes) -> bool:
        pixmap = QPixmap()
        if not pixmap.loadFromData(data):
            return False
        self._camera_pixmap = pixmap
        self.update()
        return True

    def set_heading(self, heading: float | None, accuracy: float | None = None) -> None:
        self.heading = heading
        self.heading_accuracy = accuracy
        self.update()

    def set_attitude(
        self,
        camera_elevation: float | None,
        camera_roll: float | None,
    ) -> None:
        if camera_elevation is not None:
            self.camera_elevation = camera_elevation
        if camera_roll is not None:
            self.camera_roll = camera_roll
        self.update()

    def set_sky_context(
        self,
        true_heading: float | None,
        latitude: float | None,
        longitude: float | None,
        observation_timestamp_ns: int | None,
        location_accuracy: float | None = None,
    ) -> None:
        if true_heading is not None:
            self.true_heading = true_heading
        if latitude is not None:
            self.latitude = latitude
        if longitude is not None:
            self.longitude = longitude
        if observation_timestamp_ns is not None:
            self.observation_timestamp_ns = observation_timestamp_ns
        if location_accuracy is not None:
            self.location_accuracy = location_accuracy
        self.update()

    def paintEvent(self, event: object) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        image_scale = self._draw_camera(painter)
        sky_objects = self._project_sky_objects(image_scale)
        self._draw_sky_objects(painter, sky_objects)
        self._draw_attitude(painter, image_scale)
        self._draw_compass(painter, image_scale)
        self._draw_edge_indicators(painter, sky_objects)
        painter.end()

    def _draw_camera(self, painter: QPainter) -> float:
        width = self.width()
        height = self.height()
        if self._camera_pixmap is None or self._camera_pixmap.isNull():
            painter.fillRect(self.rect(), QColor("#03070b"))
            painter.setPen(QColor("#7f929f"))
            font = QFont()
            font.setPointSize(15)
            painter.setFont(font)
            painter.drawText(
                self.rect().adjusted(40, self.TAPE_HEIGHT, -40, -40),
                Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap,
                "Waiting for Sensor Logger camera data…\n"
                "Enable Camera + Compass and push to the URL in the status bar.",
            )
            return 1.0

        source_width = self._camera_pixmap.width()
        source_height = self._camera_pixmap.height()
        scale = max(width / source_width, height / source_height)
        draw_width = source_width * scale
        draw_height = source_height * scale
        target = QRectF(
            (width - draw_width) / 2.0,
            (height - draw_height) / 2.0,
            draw_width,
            draw_height,
        )
        painter.drawPixmap(target, self._camera_pixmap, QRectF(self._camera_pixmap.rect()))
        return scale

    def _focal_pixels(self, width: float, image_scale: float) -> float:
        if self._camera_pixmap is not None and not self._camera_pixmap.isNull():
            return focal_length_pixels(
                float(self._camera_pixmap.width()),
                self.horizontal_fov,
            ) * image_scale
        return focal_length_pixels(width, self.horizontal_fov)

    def _project_sky_objects(self, image_scale: float) -> list[ProjectedStar]:
        if self.sky_missing_inputs():
            self.sky_in_view_count = 0
            self.sky_offscreen_count = 0
            return []

        width = float(self.width())
        height = float(self.height())
        objects = project_sky_objects(
            latitude_degrees=self.latitude,
            longitude_degrees=self.longitude,
            epoch_nanoseconds=self.observation_timestamp_ns,
            camera_elevation_degrees=self.camera_elevation,
            camera_azimuth_degrees=(self.true_heading + self.bearing_offset) % 360.0,
            camera_roll_degrees=self.camera_roll,
            focal_pixels=self._focal_pixels(width, image_scale),
            viewport_width=width,
            viewport_height=height,
        )
        self.sky_in_view_count = sum(item.in_view for item in objects)
        self.sky_offscreen_count = len(objects) - self.sky_in_view_count
        return objects

    def sky_missing_inputs(self) -> tuple[str, ...]:
        missing = []
        if self._camera_pixmap is None or self._camera_pixmap.isNull():
            missing.append("camera")
        if self.latitude is None or self.longitude is None:
            missing.append("GPS")
        if self.true_heading is None:
            missing.append("true north")
        if self.camera_elevation is None or self.camera_roll is None:
            missing.append("attitude")
        if self.observation_timestamp_ns is None:
            missing.append("frame time")
        return tuple(missing)

    def _draw_sky_objects(
        self,
        painter: QPainter,
        objects: list[ProjectedStar],
    ) -> None:
        objects = [item for item in objects if item.in_view]
        if not objects:
            return

        width = float(self.width())
        height = float(self.height())
        painter.save()
        painter.setFont(overlay_font(9, QFont.Weight.Bold))
        metrics = painter.fontMetrics()
        placed_labels: list[QRectF] = []
        for item in objects:
            self._draw_sky_marker(painter, item)
            label_width = float(metrics.horizontalAdvance(item.star.name) + 12)
            label_height = float(metrics.height() + 5)
            candidates = (
                QRectF(item.x + 8.0, item.y - label_height - 5.0, label_width, label_height),
                QRectF(item.x + 8.0, item.y + 5.0, label_width, label_height),
                QRectF(item.x - label_width - 8.0, item.y - label_height - 5.0, label_width, label_height),
                QRectF(item.x - label_width - 8.0, item.y + 5.0, label_width, label_height),
            )
            label = next(
                (
                    candidate
                    for candidate in candidates
                    if candidate.left() >= 3.0
                    and candidate.right() <= width - 3.0
                    and candidate.top() >= 3.0
                    and candidate.bottom() <= height - 3.0
                    and not any(candidate.intersects(existing) for existing in placed_labels)
                ),
                None,
            )
            if label is None:
                label = QRectF(candidates[0])
                label.moveLeft(max(3.0, min(label.left(), width - label_width - 3.0)))
                label.moveTop(max(3.0, min(label.top(), height - label_height - 3.0)))
            placed_labels.append(label.adjusted(-3.0, -2.0, 3.0, 2.0))
            color = self._sky_color(item)
            painter.setPen(QPen(QColor(0, 0, 0, 220), 3.0))
            painter.drawText(label, Qt.AlignmentFlag.AlignCenter, item.star.name)
            painter.setPen(color)
            painter.drawText(label, Qt.AlignmentFlag.AlignCenter, item.star.name)
        painter.restore()

    def _draw_edge_indicators(
        self,
        painter: QPainter,
        objects: list[ProjectedStar],
    ) -> None:
        objects = [item for item in objects if not item.in_view]
        if not objects:
            return

        width = float(self.width())
        height = float(self.height())
        painter.save()
        painter.setFont(overlay_font(8, QFont.Weight.Bold))
        metrics = painter.fontMetrics()
        label_specs: list[tuple[ProjectedStar, str, QRectF]] = []
        for item in objects:
            label_width = float(metrics.horizontalAdvance(item.star.name) + 14)
            label_height = float(metrics.height() + 7)
            side = self._indicator_side(item, width, height)
            label_specs.append(
                (
                    item,
                    side,
                    self._edge_label_rect(
                        item,
                        side,
                        label_width,
                        label_height,
                    ),
                )
            )

        labels = self._layout_edge_labels(label_specs, width, height)
        for item in objects:
            color = self._sky_color(item)
            label = labels[item]

            arrow = QPointF(item.x, item.y)
            label_center = label.center()
            painter.setPen(QPen(QColor(0, 0, 0, 210), 4.5))
            painter.drawLine(arrow, label_center)
            painter.setPen(QPen(color.darker(130), 1.2))
            painter.drawLine(arrow, label_center)

            angle = math.degrees(math.atan2(item.direction_y, item.direction_x))
            painter.save()
            painter.translate(arrow)
            painter.rotate(angle)
            pointer = QPolygonF(
                [
                    QPointF(11.0, 0.0),
                    QPointF(-5.0, -7.0),
                    QPointF(-2.0, 0.0),
                    QPointF(-5.0, 7.0),
                ]
            )
            painter.setPen(QPen(QColor(0, 0, 0, 220), 5.0))
            painter.setBrush(color)
            painter.drawPolygon(pointer)
            painter.setPen(QPen(color, 1.5))
            painter.drawPolygon(pointer)
            painter.restore()

            painter.setBrush(QColor(0, 8, 14, 218))
            painter.setPen(QPen(color, 1.1))
            painter.drawRoundedRect(label, 4.0, 4.0)
            painter.drawText(label, Qt.AlignmentFlag.AlignCenter, item.star.name)
        painter.restore()

    @staticmethod
    def _indicator_side(
        item: ProjectedStar,
        width: float,
        height: float,
    ) -> str:
        distances = {
            "left": item.x,
            "right": width - item.x,
            "top": item.y,
            "bottom": height - item.y,
        }
        return min(distances, key=distances.get)

    @staticmethod
    def _edge_label_rect(
        item: ProjectedStar,
        side: str,
        label_width: float,
        label_height: float,
    ) -> QRectF:
        gap = 17.0
        if side == "left":
            return QRectF(item.x + gap, item.y - label_height / 2.0, label_width, label_height)
        if side == "right":
            return QRectF(
                item.x - gap - label_width,
                item.y - label_height / 2.0,
                label_width,
                label_height,
            )
        if side == "top":
            return QRectF(item.x - label_width / 2.0, item.y + gap, label_width, label_height)
        return QRectF(
            item.x - label_width / 2.0,
            item.y - gap - label_height,
            label_width,
            label_height,
        )

    @staticmethod
    def _layout_edge_labels(
        specs: list[tuple[ProjectedStar, str, QRectF]],
        width: float,
        height: float,
    ) -> dict[ProjectedStar, QRectF]:
        result: dict[ProjectedStar, QRectF] = {}
        for side in ("left", "right", "top", "bottom"):
            horizontal = side in {"top", "bottom"}
            group = [spec for spec in specs if spec[1] == side]
            group.sort(key=lambda spec: spec[2].center().x() if horizontal else spec[2].center().y())
            if not group:
                continue

            lower = 3.0
            upper = (width if horizontal else height) - 3.0
            sizes = [spec[2].width() if horizontal else spec[2].height() for spec in group]
            desired = [
                (spec[2].center().x() if horizontal else spec[2].center().y()) - size / 2.0
                for spec, size in zip(group, sizes)
            ]
            starts: list[float] = []
            for index, (position, size) in enumerate(zip(desired, sizes)):
                start = max(lower, min(position, upper - size))
                if index:
                    start = max(start, starts[index - 1] + sizes[index - 1] + 4.0)
                starts.append(start)

            overflow = starts[-1] + sizes[-1] - upper
            if overflow > 0.0:
                starts[-1] -= overflow
                for index in range(len(starts) - 2, -1, -1):
                    starts[index] = min(
                        starts[index],
                        starts[index + 1] - sizes[index] - 4.0,
                    )
            if starts[0] < lower:
                shift = lower - starts[0]
                starts = [start + shift for start in starts]

            for (item, _side, base), start in zip(group, starts):
                label = QRectF(base)
                if horizontal:
                    label.moveLeft(start)
                    label.moveTop(max(3.0, min(label.top(), height - label.height() - 3.0)))
                else:
                    label.moveTop(start)
                    label.moveLeft(max(3.0, min(label.left(), width - label.width() - 3.0)))
                result[item] = label
        return result

    @staticmethod
    def _sky_color(item: ProjectedStar) -> QColor:
        if item.star.kind == "sun":
            return QColor("#ffd45d")
        if item.star.kind == "planet":
            return QColor("#ffae6b")
        return QColor("#eaf6ff")

    def _draw_sky_marker(self, painter: QPainter, item: ProjectedStar) -> None:
        color = self._sky_color(item)
        if item.star.kind == "sun":
            radius = 7.0
        elif item.star.kind == "planet":
            radius = 4.2
        else:
            radius = max(2.2, min(5.5, 4.8 - 0.65 * (item.star.magnitude + 1.0)))
        center = QPointF(item.x, item.y)
        painter.setBrush(QColor(0, 0, 0, 160))
        painter.setPen(QPen(QColor(0, 0, 0, 210), 4.0))
        painter.drawEllipse(center, radius + 1.5, radius + 1.5)
        painter.setBrush(color if item.star.kind != "planet" else Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(color, 2.0))
        painter.drawEllipse(center, radius, radius)
        if item.star.kind == "sun":
            painter.drawLine(QPointF(item.x - 11.0, item.y), QPointF(item.x + 11.0, item.y))
            painter.drawLine(QPointF(item.x, item.y - 11.0), QPointF(item.x, item.y + 11.0))

    def _draw_attitude(self, painter: QPainter, image_scale: float) -> None:
        if self.camera_elevation is None or self.camera_roll is None:
            return

        width = float(self.width())
        height = float(self.height())
        center_x = width / 2.0
        center_y = height / 2.0
        focal = self._focal_pixels(width, image_scale)
        marks = pitch_ladder_marks(
            self.camera_elevation,
            focal,
            math.hypot(width, height) * 0.75,
        )

        ladder_color = QColor("#a8ffc2")
        horizon_color = QColor("#ffcf5a")
        shadow_color = QColor(0, 0, 0, 190)
        painter.save()
        painter.translate(center_x, center_y)
        painter.rotate(self.camera_roll)
        painter.setFont(overlay_font(9, QFont.Weight.Bold))
        metrics = painter.fontMetrics()

        for mark in marks:
            y = mark.offset_pixels
            if mark.is_horizon:
                half_length = min(width * 0.34, 360.0)
                gap = 28.0
                line_width = 2.8
                color = horizon_color
            else:
                half_length = 104.0 if mark.is_major else 70.0
                gap = 24.0
                line_width = 2.0 if mark.is_major else 1.3
                color = ladder_color

            segments = (
                (QPointF(-half_length, y), QPointF(-gap, y)),
                (QPointF(gap, y), QPointF(half_length, y)),
            )
            painter.setPen(QPen(shadow_color, line_width + 3.0))
            for start, end in segments:
                painter.drawLine(start, end)
            painter.setPen(QPen(color, line_width))
            for start, end in segments:
                painter.drawLine(start, end)

            if mark.is_horizon:
                painter.drawLine(
                    QPointF(-half_length, y),
                    QPointF(-half_length, y - 10.0),
                )
                painter.drawLine(
                    QPointF(half_length, y),
                    QPointF(half_length, y - 10.0),
                )

            if mark.is_major:
                label_width = metrics.horizontalAdvance(mark.label) + 10.0
                painter.setPen(QPen(shadow_color, 3.0))
                for x in (-half_length - label_width - 7.0, half_length + 7.0):
                    rect = QRectF(x, y - 11.0, label_width, 22.0)
                    painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, mark.label)
                painter.setPen(color)
                for x in (-half_length - label_width - 7.0, half_length + 7.0):
                    rect = QRectF(x, y - 11.0, label_width, 22.0)
                    painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, mark.label)

        painter.restore()
        self._draw_roll_indicator(painter)

    def _draw_roll_indicator(self, painter: QPainter) -> None:
        if self.camera_roll is None:
            return

        center = QPointF(float(self.width()) / 2.0, float(self.TAPE_HEIGHT) + 80.0)
        radius = 58.0
        arc = QRectF(
            center.x() - radius,
            center.y() - radius,
            radius * 2.0,
            radius * 2.0,
        )
        scale_color = QColor("#a8ffc2")
        pointer_color = QColor("#ffcf5a")
        shadow_color = QColor(0, 0, 0, 190)

        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(shadow_color, 4.5))
        painter.drawArc(arc, 30 * 16, 120 * 16)
        painter.setPen(QPen(scale_color, 1.5))
        painter.drawArc(arc, 30 * 16, 120 * 16)

        for tick in self.ROLL_SCALE_TICKS:
            angle = math.radians(90.0 - tick)
            outer = QPointF(
                center.x() + radius * math.cos(angle),
                center.y() - radius * math.sin(angle),
            )
            tick_length = 10.0 if tick in (-60, -30, 0, 30, 60) else 6.0
            inner_radius = radius - tick_length
            inner = QPointF(
                center.x() + inner_radius * math.cos(angle),
                center.y() - inner_radius * math.sin(angle),
            )
            painter.setPen(QPen(shadow_color, 4.0))
            painter.drawLine(inner, outer)
            painter.setPen(QPen(scale_color, 1.6 if tick else 2.4))
            painter.drawLine(inner, outer)

        displayed_roll = max(-60.0, min(60.0, self.camera_roll))
        angle = math.radians(90.0 - displayed_roll)
        direction = QPointF(math.cos(angle), -math.sin(angle))
        perpendicular = QPointF(-direction.y(), direction.x())
        tip = center + direction * (radius + 5.0)
        base = center + direction * (radius - 8.0)
        marker = QPolygonF(
            [
                tip,
                base + perpendicular * 5.0,
                base - perpendicular * 5.0,
            ]
        )
        painter.setPen(QPen(shadow_color, 4.0))
        painter.setBrush(pointer_color)
        painter.drawPolygon(marker)
        painter.setPen(pointer_color)
        painter.setFont(overlay_font(9, QFont.Weight.Bold))
        painter.drawText(
            QRectF(center.x() - 95.0, center.y() + 8.0, 190.0, 22.0),
            Qt.AlignmentFlag.AlignCenter,
            f"ROLL {self.camera_roll:+05.1f}°",
        )

    def _draw_compass(self, painter: QPainter, image_scale: float) -> None:
        width = float(self.width())
        gradient = QLinearGradient(0.0, 0.0, 0.0, float(self.TAPE_HEIGHT))
        gradient.setColorAt(0.0, QColor(0, 8, 14, 220))
        gradient.setColorAt(0.7, QColor(0, 8, 14, 155))
        gradient.setColorAt(1.0, QColor(0, 8, 14, 0))
        painter.fillRect(QRectF(0.0, 0.0, width, self.TAPE_HEIGHT), gradient)

        baseline = 70.0
        tape_color = QColor("#88f4ff")
        painter.setPen(QPen(tape_color, 1.2))
        painter.drawLine(QPointF(0.0, baseline), QPointF(width, baseline))

        if self.heading is None:
            painter.setFont(overlay_font(11, QFont.Weight.DemiBold))
            painter.drawText(
                QRectF(0.0, 16.0, width, 30.0),
                Qt.AlignmentFlag.AlignCenter,
                "WAITING FOR COMPASS",
            )
            return

        display_heading = (self.heading + self.bearing_offset) % 360.0
        focal = self._focal_pixels(width, image_scale)

        painter.setFont(overlay_font(10, QFont.Weight.DemiBold))
        metrics = painter.fontMetrics()
        for mark in compass_marks(display_heading):
            x = project_delta_to_x(mark.delta, width / 2.0, focal)
            if not -20.0 <= x <= width + 20.0:
                continue
            tick_height = 30.0 if mark.is_major else 20.0 if mark.is_medium else 10.0
            painter.setPen(QPen(tape_color, 2.0 if mark.is_major else 1.2))
            painter.drawLine(QPointF(x, baseline), QPointF(x, baseline - tick_height))
            if mark.label is not None:
                label_width = metrics.horizontalAdvance(mark.label) + 12
                painter.drawText(
                    QRectF(x - label_width / 2.0, 10.0, label_width, 24.0),
                    Qt.AlignmentFlag.AlignCenter,
                    mark.label,
                )

        center_x = width / 2.0
        pointer_color = QColor("#ffcf5a")
        painter.setPen(QPen(pointer_color, 2.5))
        painter.drawLine(QPointF(center_x, 6.0), QPointF(center_x, baseline + 12.0))
        pointer = QPolygonF(
            [
                QPointF(center_x - 6.0, baseline + 8.0),
                QPointF(center_x + 6.0, baseline + 8.0),
                QPointF(center_x, baseline + 17.0),
            ]
        )
        painter.setBrush(pointer_color)
        painter.drawPolygon(pointer)

        readout = f"{display_heading:06.2f}° M"
        if self.heading_accuracy is not None and self.heading_accuracy >= 0:
            readout += f"  ±{self.heading_accuracy:.1f}°"
        painter.setFont(overlay_font(10, QFont.Weight.Bold))
        painter.setPen(pointer_color)
        painter.drawText(
            QRectF(center_x - 105.0, 82.0, 210.0, 22.0),
            Qt.AlignmentFlag.AlignCenter,
            readout,
        )


class MainWindow(QMainWindow):
    def __init__(self, push_url: str) -> None:
        super().__init__()
        self.setWindowTitle(f"DIY Astronomical Attic Observatory — v{__version__}")
        self.resize(1280, 800)
        self.viewer = CameraCompassWidget()
        self.setCentralWidget(self.viewer)
        self._push_url = push_url
        self._last_update_monotonic: float | None = None
        self._last_image_time: int | None = None
        self._build_status_bar()

        self._status_timer = QTimer(self)
        self._status_timer.timeout.connect(self._refresh_status)
        self._status_timer.start(500)
        self._refresh_status()

    def _build_status_bar(self) -> None:
        status = QStatusBar(self)
        status.setSizeGripEnabled(False)
        self.setStatusBar(status)

        self.connection_label = QLabel()
        self.connection_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        status.addWidget(self.connection_label, 1)

        status.addPermanentWidget(QLabel("Horizontal FOV"))
        self.fov_control = QDoubleSpinBox()
        self.fov_control.setRange(10.0, 160.0)
        self.fov_control.setDecimals(1)
        self.fov_control.setSingleStep(0.5)
        self.fov_control.setSuffix("°")
        self.fov_control.setValue(self.viewer.horizontal_fov)
        self.fov_control.valueChanged.connect(self._set_fov)
        status.addPermanentWidget(self.fov_control)

        status.addPermanentWidget(QLabel("Bearing offset"))
        self.offset_control = QDoubleSpinBox()
        self.offset_control.setRange(-180.0, 180.0)
        self.offset_control.setDecimals(1)
        self.offset_control.setSingleStep(0.5)
        self.offset_control.setSuffix("°")
        self.offset_control.valueChanged.connect(self._set_bearing_offset)
        status.addPermanentWidget(self.offset_control)

    @Slot(float)
    def _set_fov(self, value: float) -> None:
        self.viewer.horizontal_fov = value
        self.viewer.update()

    @Slot(float)
    def _set_bearing_offset(self, value: float) -> None:
        self.viewer.bearing_offset = value
        self.viewer.update()

    @Slot(object)
    def apply_sensor_update(self, update: SensorUpdate) -> None:
        self._last_update_monotonic = time.monotonic()
        if update.heading is not None:
            self.viewer.set_heading(update.heading, update.heading_accuracy)
        if update.camera_elevation is not None or update.camera_roll is not None:
            self.viewer.set_attitude(update.camera_elevation, update.camera_roll)
        self.viewer.set_sky_context(
            update.true_heading,
            update.latitude,
            update.longitude,
            update.image_timestamp_ns,
            update.location_accuracy,
        )
        if update.image is not None and self.viewer.set_camera_image(update.image):
            self._last_image_time = update.image_timestamp_ns
        if update.horizontal_fov is not None:
            self.fov_control.setValue(update.horizontal_fov)
        self._refresh_status()

    def _refresh_status(self) -> None:
        if self._last_update_monotonic is None:
            state = "Listening"
        else:
            age = time.monotonic() - self._last_update_monotonic
            state = "Receiving" if age <= 3.0 else f"Waiting ({age:.0f}s since last push)"

        detail = ""
        if self._last_image_time is not None:
            image_time = datetime.fromtimestamp(self._last_image_time / 1_000_000_000)
            detail = f" · image {image_time:%H:%M:%S}"
        if self.viewer.latitude is not None and self.viewer.longitude is not None:
            gps = f" · GPS {self.viewer.latitude:.4f}, {self.viewer.longitude:.4f}"
            if self.viewer.location_accuracy is not None:
                gps += f" ±{self.viewer.location_accuracy:.0f}m"
            detail += gps
        missing = self.viewer.sky_missing_inputs()
        if missing:
            detail += f" · sky waiting for {', '.join(missing)}"
        else:
            detail += (
                f" · sky {self.viewer.sky_in_view_count} in view, "
                f"{self.viewer.sky_offscreen_count} chase"
            )
        self.connection_label.setText(f"{state} · Sensor Logger URL: {self._push_url}{detail}")
