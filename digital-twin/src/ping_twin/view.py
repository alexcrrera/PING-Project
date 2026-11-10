"""The standalone digital-twin GUI."""

from __future__ import annotations

from math import asin, atan2, hypot, pi
import time

from nicegui import ui

from .model import DigitalTwin, MOTORS
from .keyboard import KEYBOARD_SCRIPT
from .settings import VehicleSettings


def rod_rotation(a: tuple[float, float, float], b: tuple[float, float, float]) -> tuple[float, float, float]:
    """Euler angles that point NiceGUI's local +Y cylinder axis from a to b."""
    dx, dy, dz = (b[i] - a[i] for i in range(3))
    length = hypot(hypot(dx, dy), dz)
    if length == 0:
        raise ValueError("Arm endpoints must differ")
    # NiceGUI's XYZ rotation matrix gives the local +Y axis as
    # (-sin(rz)*cos(rx), cos(rz)*cos(rx), sin(rx)).
    return asin(max(-1., min(1., dz / length))), 0., atan2(-dx, dy)


class TwinPage:
    def __init__(self) -> None:
        self.settings = VehicleSettings()
        self.twin = DigitalTwin(self.settings.load())
        self.running = False
        self.focused_on_rover = False
        self.throttle = 0.0  # slider values
        self.steer = 0.0
        self.keyboard_throttle = 0.0
        self.keyboard_steer = 0.0
        self.keyboard_throttle_active = False
        self.keyboard_steer_active = False
        self.keyboard_last_at = 0.0
        ui.add_css("""
        .twin-page {max-width:1900px;width:100%;margin:auto;padding:22px;color:#e8e7df}
        .twin-head {display:flex;justify-content:space-between;align-items:center;gap:20px}
        .twin-card {background:#191a18;border:1px solid #343530;padding:16px}
        .twin-layout {display:grid;grid-template-columns:minmax(235px,270px) minmax(0,1fr) minmax(235px,270px);grid-template-areas:'left main right';gap:16px;align-items:start;width:100%}
        .twin-left {grid-area:left}.twin-main {grid-area:main;min-width:0}.twin-right {grid-area:right}
        .twin-side {display:flex;flex-direction:column;gap:16px;min-width:0}
        .twin-side .q-field {width:100%}
        .twin-readings {display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px}
        .twin-number {font-size:19px;font-variant-numeric:tabular-nums;overflow-wrap:anywhere}
        .twin-note {color:#aab09f;font-size:12px;line-height:1.5}
        .twin-grid {display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:14px}
        @media(max-width:1150px){.twin-layout{grid-template-columns:repeat(2,minmax(0,1fr));grid-template-areas:'main main' 'left right'}}
        @media(max-width:700px){.twin-layout{grid-template-columns:minmax(0,1fr);grid-template-areas:'main' 'left' 'right'}.twin-readings{grid-template-columns:repeat(2,minmax(0,1fr))}}
        """)
        with ui.column().classes("twin-page"):
            with ui.row().classes("twin-head w-full"):
                with ui.column().classes("gap-0"):
                    ui.label("PING / DIGITAL TWIN").classes("text-h5")
                    ui.label("Independent vehicle and terrain experiment").classes("twin-note")
            ui.label("Changes apply immediately and save automatically. Geometry and terrain redraw while the simulation state is retained.").classes("twin-note q-my-sm")
            with ui.element("div").classes("twin-layout"):
                with ui.element("aside").classes("twin-left twin-side").props('aria-label="Vehicle geometry and chassis configuration"'):
                    self._geometry_controls()
                    self._chassis_controls()
                with ui.element("main").classes("twin-main"):
                    self._simulation_panel()
                with ui.element("aside").classes("twin-right twin-side").props('aria-label="Powertrain and terrain configuration"'):
                    self._powertrain_controls()
                    self._terrain_controls()
        ui.on("twin_keyboard", self._keyboard_event)
        ui.add_body_html(f"<script>{KEYBOARD_SCRIPT}</script>")
        ui.timer(.05, self._tick)

    def _simulation_panel(self) -> None:
        with ui.row().classes("w-full items-center justify-between q-mb-sm"):
            ui.label("Amber = low traction · green = high traction · grey = ordinary · rocks and steps are raised").classes("twin-note")
            self.focus_button = ui.button("Inspect rover", icon="center_focus_strong", on_click=self._toggle_focus).props("flat dense")
        self._scene()
        with ui.row().classes("w-full items-center q-mt-md"):
            self.run_button = ui.button("Run", icon="play_arrow", on_click=self._toggle)
            ui.button("Reset", icon="restart_alt", on_click=self._reset).props("outline")
            ui.label("Throttle")
            ui.slider(min=-1, max=1, step=.05, value=0,
                      on_change=lambda e: setattr(self, "throttle", float(e.value))).classes("col")
            ui.label("Steer")
            ui.slider(min=-1, max=1, step=.05, value=0,
                      on_change=lambda e: setattr(self, "steer", float(e.value))).classes("col")
        ui.label("W/S drive forward and reverse; A/D steer. Arrow keys work too. Pressing a drive key starts the simulation. After editing a setting, click the 3D view to drive again.").classes("twin-note q-my-sm")
        with ui.element("div").classes("twin-readings q-mt-sm"):
            for title, key in (("Ground speed", "speed"), ("Position", "position"),
                               ("Pitch / roll / yaw", "attitude"), ("Contact", "contact")):
                with ui.column().classes("twin-card gap-1"):
                    ui.label(title).classes("twin-note")
                    setattr(self, f"reading_{key}", ui.label("—").classes("twin-number"))
        with ui.element("div").classes("twin-grid q-mt-sm"):
            for title, key in (("FL", "fl"), ("FR", "fr"), ("RL", "rl"), ("RR", "rr")):
                with ui.column().classes("twin-card gap-1"):
                    ui.label(title).classes("twin-note")
                    setattr(self, f"reading_{key}", ui.label("—").classes("text-body2"))
        self._readings()

    @ui.refreshable
    def _scene(self) -> None:
        c = self.twin.config
        with ui.scene(width=1100, height=500, grid=False,
                      camera=ui.scene.perspective_camera(fov=42, near=.05, far=80),
                      background_color="#151a16", fps=20).classes("w-full twin-card") as scene:
            self.scene = scene
            scene.move_camera(x=4.4, y=-2.5, z=5.8,
                              look_at_x=0, look_at_y=5.4, look_at_z=0, up_x=0, up_y=0, up_z=1)
            scene.box(8, 15, .025).move(0, 5.8, -.025).material("#454a42")
            for x in (-1.6, 1.6):
                scene.box(.035, 14.5, .012).move(x, 5.8, .002).material("#aeb1a3")
            scene.box(2.5, 2.1, .014).move(0, 2.15, .005).material("#98713f").with_name("Low traction")
            scene.box(2.5, 2.1, .014).move(0, 4.85, .005).material("#597c4d").with_name("High traction")
            scene.box(1.1, 1.8, c.rock_height_m * .35).move(0, 7.5, c.rock_height_m * .175).material("#666c65").with_name("Rock field")
            for x, y, scale in ((-.29, 6.95, .78), (.20, 7.10, 1.),
                                (-.12, 7.53, .85), (.31, 7.84, .72), (-.31, 8.06, .9)):
                scene.sphere(c.rock_height_m * scale).move(x, y, c.rock_height_m * .48).material("#838982")
            for i in range(3):
                z = (i + 1) * c.stair_height_m
                scene.box(2.5, c.stair_depth_m, z).move(0, 9 + (i + .5) * c.stair_depth_m, z / 2).material("#9c9d8e").with_name(f"Step {i+1}")
            with scene.group().with_name("Twin rover") as self.rover:
                radius = c.wheel_diameter_m / 2
                # Body and angled side arms are driven by the sketch dimensions.
                body_z = radius + c.body_center_above_axle_m
                scene.box(c.body_width_m, c.body_length_m, c.body_height_m).move(0, 0, body_z).material("#d1d5c5", opacity=.55)
                scene.box(c.body_width_m * .85, .07, .04).move(0, c.body_length_m / 2, body_z).material("#e8eabe")
                # The amber CG is at the geometric centre, visible through the body.
                scene.sphere(.032).move(0, 0, body_z).material("#e5a84d").with_name("CG / body centre")
                for side in (-1, 1):
                    body_side, pivot = c.joint_connection(side)
                    if c.joint_offset_m > 0:
                        self._rod(scene, body_side, pivot, .006, "#d6ad70").with_name("Body-to-joint standoff")
                        dot_radius = min(.006, c.joint_offset_m / 16)
                        for fraction in range(1, 5):
                            x = body_side[0] + (pivot[0] - body_side[0]) * fraction / 5
                            scene.sphere(dot_radius).move(x, 0, body_z).material("#aab4a7").with_name("Dotted body-to-joint link")
                    scene.sphere(.027).move(*pivot).material("#858d83").with_name("Offset arm pivot")
                self.wheel_groups = []
                for side, fore in ((-1, 1), (1, 1), (-1, -1), (1, -1)):
                    arm_start, arm_end = c.arm_endpoints(side, fore)
                    wx, wy, _ = arm_end
                    self._rod(scene, arm_start, arm_end, .018, "#b9c1b4")
                    with scene.group().move(wx, wy, radius).with_name("Drive wheel") as wheel:
                        scene.cylinder(radius, radius, c.wheel_width_m, 24).rotate(0, 0, pi / 2).material("#242a25")
                        scene.cylinder(radius * .4, radius * .4, c.wheel_width_m + .005, 16).rotate(0, 0, pi / 2).material("#9aa398")
                        scene.box(.01, radius * .9, .01).move(side * c.wheel_width_m * .52, 0, 0).material("#e3e8ca")
                    self.wheel_groups.append(wheel)
        self._update_scene()
        if self.focused_on_rover:
            self._move_camera_to_rover(duration=0)

    @staticmethod
    def _rod(scene, a, b, radius, color):
        dx, dy, dz = (b[i] - a[i] for i in range(3))
        length = hypot(hypot(dx, dy), dz)
        return scene.cylinder(radius, radius, length, 8).rotate(*rod_rotation(a, b)).move(
            *((a[i] + b[i]) / 2 for i in range(3))).material(color)

    def _geometry_controls(self) -> None:
        with ui.column().classes("twin-card w-full"):
            ui.label("GEOMETRY · SIDE VIEW").classes("text-subtitle2")
            for item in (
                ("wheel_diameter_m", "Wheel diameter", "m", .05, .7, .01),
                ("wheel_width_m", "Wheel width", "m", .01, .3, .01),
                ("body_length_m", "Body length l₁", "m", .2, 3, .01),
                ("body_height_m", "Body height h₁", "m", .03, 1, .01),
                ("arm_length_m", "Arm length", "m", .05, 1.5, .01),
                ("front_arm_deg", "Front arm α from vertical", "°", 0, 75, 1),
                ("rear_arm_deg", "Rear arm β from vertical", "°", 0, 75, 1),
            ):
                self._number(*item)

    def _chassis_controls(self) -> None:
        with ui.column().classes("twin-card w-full"):
            ui.label("CHASSIS · TOP VIEW").classes("text-subtitle2")
            for item in (
                ("mass_kg", "Vehicle mass", "kg", .5, 100, .1),
                ("body_width_m", "Body width w₁", "m", .1, 2, .01),
                ("joint_offset_m", "Arm joint offset from body side", "m", 0, 1, .01),
                ("rolling_coefficient", "Rolling resistance", "fraction", .001, .3, .001),
                ("viscous_drag_ns_m", "Viscous drag", "N·s/m", .001, 10, .01),
            ):
                self._number(*item)
            self.track_label = ui.label(f"Wheel track: {self.twin.config.track_m:.3f} m").classes("twin-note")
            ui.label("Both joints and wheels move outward together, keeping the arms straight in side view.").classes("twin-note")

    def _powertrain_controls(self) -> None:
        with ui.column().classes("twin-card w-full"):
            ui.label("POWERTRAIN").classes("text-subtitle2")
            ui.select(list(MOTORS), value=self.twin.config.motor, label="Pololu 37D 12 V gearbox",
                      on_change=lambda e: self._change("motor", e.value)).classes("w-full")
            for item in (
                ("supply_v", "Supply voltage", "V", 1, 12, .1),
                ("drive_efficiency", "Drivetrain efficiency", "fraction", .1, 1, .01),
                ("wheel_inertia_kgm2", "Wheel rotational inertia", "kg·m²", .0001, .1, .0001),
            ):
                self._number(*item)

    def _terrain_controls(self) -> None:
        with ui.column().classes("twin-card w-full"):
            ui.label("TERRAIN").classes("text-subtitle2")
            for item in (
                ("low_mu", "Low-zone friction μ", "", .01, 2, .01),
                ("high_mu", "High-zone friction μ", "", .01, 2, .01),
                ("rock_height_m", "Rock height", "m", .01, .5, .01),
                ("stair_height_m", "Stair rise", "m", .01, .35, .01),
                ("stair_depth_m", "Stair tread", "m", .1, 1, .01),
            ):
                self._number(*item)
        ui.label("Model scope: planar traction and yaw, wheel spin, geometric pitch/roll and obstacle blocking.").classes("twin-note")

    def _number(self, key, label, unit, low, high, step):
        ui.number(f"{label} ({unit})" if unit else label, value=getattr(self.twin.config, key),
                  min=low, max=high, step=step,
                  on_change=lambda e, k=key: self._change(k, e.value)).classes("w-full").props("outlined dense")

    def _change(self, key, value):
        if value is None:
            return
        try:
            self.twin.configure(**{key: value})
            self.settings.save(self.twin.config)
            self.track_label.set_text(f"Wheel track: {self.twin.config.track_m:.3f} m")
            self._scene.refresh()
        except (OSError, ValueError, TypeError) as exc:
            ui.notify(str(exc), type="negative")

    def _toggle(self):
        self.running = not self.running
        self.run_button.set_text("Pause" if self.running else "Run")
        self.run_button.props(f'icon={"pause" if self.running else "play_arrow"}')

    def _reset(self):
        self.running = False
        self.twin.reset()
        self.run_button.set_text("Run")
        self.run_button.props("icon=play_arrow")
        self._update_scene()
        self._readings()

    def _toggle_focus(self):
        self.focused_on_rover = not self.focused_on_rover
        self.focus_button.set_text("Show course" if self.focused_on_rover else "Inspect rover")
        if self.focused_on_rover:
            self._move_camera_to_rover()
        else:
            self.scene.move_camera(x=4.4, y=-2.5, z=5.8,
                                   look_at_x=0, look_at_y=5.4, look_at_z=0,
                                   up_x=0, up_y=0, up_z=1, duration=.35)

    def _move_camera_to_rover(self, *, duration: float = .35):
        s = self.twin.state
        self.scene.move_camera(x=s.x_m + 1.2, y=s.y_m - 1.4, z=s.z_m + 1.1,
                               look_at_x=s.x_m, look_at_y=s.y_m,
                               look_at_z=s.z_m + self.twin.config.wheel_diameter_m / 2,
                               up_x=0, up_y=0, up_z=1, duration=duration)

    def _keyboard_event(self, event):
        payload = event.args
        if not isinstance(payload, dict):
            return
        if payload.get("release") is True:
            self.keyboard_throttle_active = False
            self.keyboard_steer_active = False
            return
        throttle, steer = payload.get("throttle"), payload.get("steer")
        if (not isinstance(throttle, (int, float)) or isinstance(throttle, bool) or throttle not in (-1, 0, 1)
                or not isinstance(steer, (int, float)) or isinstance(steer, bool) or steer not in (-1, 0, 1)
                or not isinstance(payload.get("throttle_active"), bool)
                or not isinstance(payload.get("steer_active"), bool)):
            return
        was_active = self.keyboard_throttle_active or self.keyboard_steer_active
        self.keyboard_throttle = float(throttle)
        self.keyboard_steer = float(steer)
        self.keyboard_throttle_active = payload["throttle_active"]
        self.keyboard_steer_active = payload["steer_active"]
        self.keyboard_last_at = time.monotonic()
        if not was_active and (self.keyboard_throttle_active or self.keyboard_steer_active) and not self.running:
            self._toggle()

    def _drive_inputs(self, now: float) -> tuple[float, float]:
        fresh = now - self.keyboard_last_at < .35
        return (self.keyboard_throttle if fresh and self.keyboard_throttle_active else self.throttle,
                self.keyboard_steer if fresh and self.keyboard_steer_active else self.steer)

    def _tick(self):
        if not self.running:
            return
        throttle, steer = self._drive_inputs(time.monotonic())
        for _ in range(5):
            self.twin.step(.01, throttle, steer)
        self._update_scene()
        self._readings()

    def _update_scene(self):
        if not hasattr(self, "rover"):
            return
        s = self.twin.state
        self.rover.move(s.x_m, s.y_m, s.z_m)
        self.rover.rotate(s.pitch_deg * pi / 180, s.roll_deg * pi / 180, -s.yaw_rad)
        for wheel, angle in zip(self.wheel_groups, s.wheel_angle_rad):
            wheel.rotate(-angle, 0, 0)

    def _readings(self):
        s = self.twin.state
        self.reading_speed.set_text(f"{s.vx_mps:+.2f} m/s")
        self.reading_position.set_text(f"{s.x_m:+.1f}, {s.y_m:+.1f} m")
        self.reading_attitude.set_text(f"{s.pitch_deg:+.0f}° / {s.roll_deg:+.0f}° / {s.yaw_rad * 180 / pi:+.0f}°")
        terrain = self.twin.terrain(s.x_m, s.y_m)[2]
        self.reading_contact.set_text("BLOCKED" if s.blocked else terrain.upper())
        for i, key in enumerate(("fl", "fr", "rl", "rr")):
            getattr(self, f"reading_{key}").set_text(
                f"{s.wheel_rad_s[i] * 30 / pi:+.0f} rpm · {s.motor_current_a[i]:.1f} A · "
                f"{s.contact_force_n[i]:+.1f} N · slip {s.slip_mps[i]:+.2f} m/s · μ {s.traction_mu[i]:.2f}")


def configure_twin_page() -> None:
    @ui.page("/")
    def _twin_page() -> None:
        TwinPage()
