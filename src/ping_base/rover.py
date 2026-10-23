"""Procedural four-wheel PING rover, rendered locally by NiceGUI/Three.js.

The model is an illustrative test chassis, not a CAD representation. Body axes
are x = right, y = forward, z = up; telemetry angles are in degrees.
"""

from __future__ import annotations

import math
import time
from typing import Protocol

from nicegui import ui


class AttitudeSnapshot(Protocol):
    roll_deg: float
    pitch_deg: float
    heading_deg: float
    speed_mps: float
    wheel_rpm: tuple[float, float, float, float] | None


class MotionSnapshot(Protocol):
    x_m: float
    y_m: float


class RoverView:
    """Embeddable scene with orbit controls and explicit telemetry updates.

    Construct inside the desired NiceGUI container. The dashboard owns its
    section header and can attach a reset button to :meth:`reset_view`.
    """

    WHEEL_RADIUS = .33
    # Match the FL / FR / RL / RR order in the telemetry protocol.
    WHEEL_POSITIONS = ((-.91, .77), (.91, .77), (-.91, -.77), (.91, -.77))
    BODY_COLOR = "#c7c9bf"
    DARK_COLOR = "#414740"
    TYRE_COLOR = "#262b25"
    METAL_COLOR = "#899084"

    def __init__(self, *, height: int = 260, background_color: str = "#191c1a") -> None:
        self.scene = ui.scene(
            width=800, height=height, grid=False,
            camera=ui.scene.perspective_camera(fov=34, near=.1, far=80),
            background_color=background_color, fps=20,
        ).classes("w-full rover-scene").style("min-width: 0; min-height: 0; height: 100%")
        self._wheels: list = []
        self._wheel_angles = [0.0] * 4
        self._last_update: float | None = None
        with self.scene:
            self._build_ground()
            with self.scene.group().with_name("PING four-wheel test chassis") as self.body:
                self._build_body()
                self._build_suspension()
                self._build_wheels()
                self._build_mast()
        self.reset_view(duration=0)

    def reset_view(self, *, duration: float = .35) -> None:
        self.scene.move_camera(
            x=3.55, y=4.75, z=2.9,
            look_at_x=0, look_at_y=0, look_at_z=.68,
            up_x=0, up_y=0, up_z=1, duration=duration,
        )

    def _box(self, width: float, length: float, height: float,
             x: float, y: float, z: float, color: str):
        return self.scene.box(width, length, height).move(x, y, z).material(color)

    def _build_ground(self) -> None:
        # Move the world grid beneath a centered chassis, preserving the datum
        # while showing travel without driving the model out of view.
        with self.scene.group().with_name("World ground datum") as self._ground:
            for coordinate in range(-4, 5):
                color = "#343b33" if coordinate == 0 else "#2b322b"
                self.scene.line([-4.5, coordinate, -.015], [4.5, coordinate, -.015]).material(color)
                self.scene.line([coordinate, -4.5, -.015], [coordinate, 4.5, -.015]).material(color)
        self.scene.cylinder(1.48, 1.48, .012, 64).rotate(math.pi / 2, 0, 0).move(z=-.025) \
            .material("#30372e", opacity=.30)

    def _build_body(self) -> None:
        self._box(1.28, 1.91, .28, 0, 0, .69, self.BODY_COLOR).with_name("Low rover chassis")
        self._box(1.06, 1.52, .07, 0, -.06, .87, "#aab0a3")
        self._box(1.10, 1.55, .13, 0, -.04, .49, self.DARK_COLOR)
        # Distinct longitudinal battery/payload modules and deck panels.
        for x in (-.30, .30):
            self._box(.48, 1.23, .055, x, -.13, .928, "#71796c")
            for y in (-.62, -.24, .14, .52):
                self._box(.40, .012, .012, x, y, .96, "#9ba391")
        self._box(.10, 1.75, .045, 0, -.02, .94, "#d4d6cc")
        self._box(1.40, .085, .12, 0, 1.01, .61, self.DARK_COLOR)
        self._box(1.40, .085, .12, 0, -1.01, .61, self.DARK_COLOR)
        # Front optics give a clear heading cue without a saturated accent.
        for x in (-.47, .47):
            self._box(.20, .06, .09, x, 1.06, .68, "#e2e5d7")
        for x in (-.55, .55):
            for y in (-.82, .82):
                self.scene.cylinder(.028, .028, .015, 8).rotate(math.pi / 2, 0, 0) \
                    .move(x, y, .85).material(self.DARK_COLOR)
        self._box(.38, .09, .14, 0, -1.04, .72, "#727b6b")
        # Short antenna on the rear deck.
        self._rod((-.43, -.65, .91), (-.43, -.65, 1.47), .013, self.METAL_COLOR)
        self.scene.sphere(.025).move(-.43, -.65, 1.48).material("#c5caba")

    def _rod(self, start: tuple[float, float, float], end: tuple[float, float, float],
             radius: float, color: str):
        """Place a cylinder between points, using the native cylinder +y axis."""
        dx, dy, dz = (end[index] - start[index] for index in range(3))
        length = math.sqrt(dx * dx + dy * dy + dz * dz)
        # Three.js uses intrinsic XYZ Euler angles. For a native +y cylinder,
        # this maps its axis to (-sin(rz), cos(rx)*cos(rz), sin(rx)*cos(rz)).
        rx = math.atan2(dz, dy)
        rz = -math.asin(max(-1.0, min(1.0, dx / length)))
        return self.scene.cylinder(radius, radius, length, 10).rotate(rx, 0, rz) \
            .move(*((start[index] + end[index]) / 2 for index in range(3))).material(color)

    def _build_suspension(self) -> None:
        for x, y in self.WHEEL_POSITIONS:
            side = math.copysign(1, x)
            hub = (x, y, .34)
            # Two control arms and an exposed angled damper per wheel.
            self._rod((side * .53, y - .23, .55), hub, .035, self.METAL_COLOR)
            self._rod((side * .53, y + .23, .55), hub, .035, self.METAL_COLOR)
            upper = (side * .58, y - .09, .78)
            lower = (side * .88, y - .04, .36)
            self._rod(upper, lower, .034, "#aeb5a4")
            middle = tuple((upper[index] + lower[index]) / 2 for index in range(3))
            self._rod(upper, middle, .064, self.DARK_COLOR)
            # Spring hoops; the slanted damper remains easy to identify.
            for fraction in (.14, .26, .38, .50, .62):
                a = tuple(upper[index] + (lower[index] - upper[index]) * (fraction - .016) for index in range(3))
                b = tuple(upper[index] + (lower[index] - upper[index]) * (fraction + .016) for index in range(3))
                self._rod(a, b, .075, "#a3ad96")

    def _build_wheels(self) -> None:
        for x, y in self.WHEEL_POSITIONS:
            side = math.copysign(1, x)
            with self.scene.group().move(x, y, self.WHEEL_RADIUS).with_name("Independent drive wheel") as wheel:
                self.scene.cylinder(self.WHEEL_RADIUS, self.WHEEL_RADIUS, .24, 28) \
                    .rotate(0, 0, math.pi / 2).material(self.TYRE_COLOR)
                # Radial tread bars form an off-road silhouette, not smooth toy wheels.
                for index in range(18):
                    angle = index * math.tau / 18
                    self._box(.26, .072, .038, 0,
                              math.sin(angle) * .329, math.cos(angle) * .329, "#353c31") \
                        .rotate(-angle, 0, 0)
                self.scene.cylinder(.207, .207, .258, 24).rotate(0, 0, math.pi / 2) \
                    .material(self.METAL_COLOR)
                self.scene.cylinder(.147, .147, .27, 20).rotate(0, 0, math.pi / 2) \
                    .material(self.DARK_COLOR)
                self.scene.cylinder(.070, .070, .28, 12).rotate(0, 0, math.pi / 2) \
                    .material("#c6cdbb")
                for index in range(6):
                    angle = index * math.tau / 6
                    self.scene.cylinder(.016, .016, .02, 6).rotate(0, 0, math.pi / 2) \
                        .move(side * .144, math.sin(angle) * .11, math.cos(angle) * .11) \
                        .material("#c7cdbb")
            self._wheels.append(wheel)

    def _build_mast(self) -> None:
        self._box(.28, .27, .06, 0, .52, .97, self.DARK_COLOR)
        self._box(.083, .083, .59, 0, .52, 1.27, self.METAL_COLOR)
        self._box(.46, .20, .19, 0, .55, 1.61, self.BODY_COLOR).with_name("Stereo camera mast")
        self._box(.40, .018, .13, 0, .66, 1.61, self.DARK_COLOR)
        for x in (-.13, .13):
            self.scene.cylinder(.054, .054, .026, 24).move(x, .68, 1.61).material("#20271f")
            self.scene.cylinder(.030, .030, .031, 20).move(x, .69, 1.61).material("#788571")

    def update(self, snapshot: AttitudeSnapshot) -> None:
        """Apply real or simulated attitude without rebuilding scene geometry."""
        values = (snapshot.roll_deg, snapshot.pitch_deg, snapshot.heading_deg, snapshot.speed_mps)
        if not all(math.isfinite(value) for value in values):
            return
        now = time.monotonic()
        dt = min(.5, max(0.0, now - self._last_update)) if self._last_update is not None else 0.0
        self._last_update = now
        self.body.rotate(math.radians(snapshot.pitch_deg), math.radians(snapshot.roll_deg),
                         -math.radians(snapshot.heading_deg))
        rpms = getattr(snapshot, "wheel_rpm", None)
        if rpms is not None and len(rpms) == 4 and all(math.isfinite(rpm) for rpm in rpms):
            angular_speeds = tuple(rpm * math.tau / 60 for rpm in rpms)
        else:
            angular_speeds = (snapshot.speed_mps / self.WHEEL_RADIUS,) * 4
        for index, (wheel, angular_speed) in enumerate(zip(self._wheels, angular_speeds)):
            self._wheel_angles[index] = (self._wheel_angles[index] + angular_speed * dt) % math.tau
            wheel.rotate(-self._wheel_angles[index], 0, 0)

    def update_motion(self, snapshot: MotionSnapshot) -> None:
        """Show virtual travel beneath the fixed-center attitude instrument."""
        if math.isfinite(snapshot.x_m) and math.isfinite(snapshot.y_m):
            self._ground.move(-(snapshot.x_m % 1), -(snapshot.y_m % 1), 0)

