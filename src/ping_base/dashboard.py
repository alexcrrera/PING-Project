"""NiceGUI presentation. Receives services; never owns device connections."""

from __future__ import annotations

from datetime import datetime
from html import escape
import math
from pathlib import Path
import time
from typing import Literal
from urllib.parse import urlencode

from fastapi import Query, Response
from nicegui import app, context, ui

from .fonts import register_fonts
from .camera import FFmpegCameraSource, OpenCVCameraSource, SimulatedCameraSource
from .camera_filters import CameraFilterSettings, CameraFrameProcessor, FILTER_LABELS, VISION_EFFECTS
from .gimbal import GimbalPose, StabilizationMode
from .hud import gimbal_indicator, heading_tape, range_readout
from .keyboard import KEYBOARD_SCRIPT
from .navigation import MAP_ZOOM_LEVELS, campus_map, simulated_position
from .preferences import loadPort, savePort
from .orientation import heading_indicator, pitch_indicator, roll_indicator, wheel_slip_indicator
from .rover import RoverView
from .station import BaseStation
from .telemetry import RadioBenchSource, SerialTelemetrySource, SimulatedTelemetrySource
from .telemetry.model import RoverTelemetrySample
from .telemetry.rvr import GROUP_EXPIRY
from .telemetry.serial import RAW_LOG_LINES
from .theme import CSS


PING_ICON_PATH = Path(__file__).with_name("assets") / "pinguin-icon.png"
PING_ICON_URL = "/assets/pinguin-icon.png"


ICONS = {
    "camera": '<rect x="3" y="5" width="18" height="14" rx="1"/><circle cx="12" cy="12" r="4"/>',
    "rover": '<path d="m3 8 9-5 9 5v9l-9 5-9-5zM3 8l9 5 9-5M12 13v9"/>',
    "telemetry": '<path d="M3 13h4l3-8 4 15 3-9h4"/>',
}
CAMERA_ZOOM_LEVELS = (1, 2, 5, 12, 20)
STABILIZATION_LABELS = {
    StabilizationMode.OFF: ("FOLLOW BOTH", "Follows rover yaw and pitch"),
    StabilizationMode.LOCK: ("HEADLESS", "World yaw and pitch locked"),
    StabilizationMode.FOLLOW: ("FOLLOW YAW", "Follows rover yaw · Pitch locked"),
}
STABILIZATION_HINT = "Z: Follow Both / Headless / Follow Yaw"

NAVIGATION_MODES = {
    "NAVIGATION_TRACTION": "TRACTION",
    "NAVIGATION_NO_TRACTION": "NO TRACTION",
    "NAVIGATION_OBSTACLE": "OBSTACLE",
}


GROUP_TITLES = {
    "ATVL": "Motion", "WSST": "Wheel speed and slip", "ACCL": "Acceleration",
    "GPD": "GNSS", "GMBL": "Gimbal", "WGD": "Wheel data", "RGM": "Regime",
}
GROUP_FIELDS = {
    ("RGM", 10): ("Regime", "Dynamic", "Max velocity (m/s)", "Max acceleration (m/s²)",
                  "Max yaw rate (°/s)", "Max yaw acceleration (°/s²)", "Pitch/roll limit (°)",
                  "Yaw limit (°)", "Min output (%)", "Max output (%)"),
    ("ATVL", 5): ("Vx (m/s)", "Vy (m/s)", "Yaw (°)", "Pitch (°)", "Roll (°)"),
    ("WSST", 8): tuple(f"{wheel} {channel}" for channel in ("RPM", "slip")
                      for wheel in ("FL", "FR", "RL", "RR")),
    ("ACCL", 3): ("Accel X (m/s²)", "Accel Y (m/s²)", "Accel Z (m/s²)"),
    ("GPD", 10): ("Valid fix", "Satellites", "Latitude (deg)", "Longitude (deg)",
                   "Ellipsoid altitude (m)", "North velocity (m/s)", "East velocity (m/s)",
                   "Down velocity (m/s)", "Horizontal uncertainty (m)", "Velocity uncertainty (m/s)"),
    ("GPD", 4): ("Valid fix", "Latitude (°)", "Longitude (°)", "Altitude MSL (m)"),
    ("GMBL", 7): ("Range 1 (m)", "Range 2 (m)", "Validity mask", "Mode",
                  "LiDAR (m)", "Pan (°)", "Tilt (°)"),
    ("WGD", 16): tuple(f"{wheel} {channel}" for wheel in ("FL", "FR", "RL", "RR")
                       for channel in ("RPM", "current (A)", "torque (Nm)", "slip")),
}
LEGACY_GROUP_TITLES = {"P1": "Motion", "P2": "Wheels", "P3": "Sensors", "F": "Flags", "LP": "Low priority"}
GROUP_FIELDS.update({
    ("P1", 5): ("Vx (m/s)", "Vy (m/s)", "Yaw (°)", "Pitch (°)", "Roll (°)"),
    ("P1", 4): ("Speed (m/s)", "Yaw (°)", "Pitch (°)", "Roll (°)"),
    ("P2", 13): tuple(f"{wheel} {channel}" for channel in ("ω (rad/s)", "slip", "current (A)")
                      for wheel in ("FL", "FR", "RL", "RR")) + ("Roll (°)",),
    ("P3", 11): ("Accel X (m/s²)", "Accel Y (m/s²)", "Accel Z (m/s²)", "Longitude (°)",
                 "Latitude (°)", "Altitude (m)", "Gimbal pitch (°)", "Gimbal pan (°)",
                 "Range 1 (m)", "Range 2 (m)", "Validity mask"),
    ("F", 2): ("Brake override", "Regime"),
})


def _icon(name: str) -> str:
    return f'<svg width="20" height="20" viewBox="0 0 24 26" fill="none" stroke="currentColor" stroke-width="1.1">{ICONS[name]}</svg>'


def rover_group_details(sample: RoverTelemetrySample) -> str:
    lines = []
    if sample.acceleration_mps2 is not None:
        ax, ay, az = sample.acceleration_mps2
        lines.append(f"Accel XYZ {ax:+.2f}, {ay:+.2f}, {az:+.2f} m/s²")
    if sample.latitude_deg is not None and sample.longitude_deg is not None and sample.altitude_m is not None:
        lines.append(f"GPS {sample.latitude_deg:.6f}°, {sample.longitude_deg:.6f}° / {sample.altitude_m:.1f} m")
    if sample.gimbal_pitch_deg is not None and sample.gimbal_pan_deg is not None:
        lines.append(f"Gimbal pitch {sample.gimbal_pitch_deg:+.1f}° / pan {sample.gimbal_pan_deg:+.1f}°")
    if sample.gimbal_validity is not None:
        ranges = (sample.gimbal_distance_1_m, sample.gimbal_distance_2_m)
        rangeText = " / ".join(f"{value:.2f} m" if value is not None else "-" for value in ranges)
        lines.append(f"Gimbal ranges {rangeText}")
    if sample.brake_override is not None:
        brake = "ON" if sample.brake_override else "OFF"
        lines.append(f"Brake override {brake} / Regime {sample.regime_mode}")
    if sample.low_priority_fields is not None:
        lines.append("LP " + ", ".join(sample.low_priority_fields))
    return "\n".join(lines)


def target_speed_indicator(throttle: float | None, max_velocity: float | None,
                           steering: float = 0.0, max_yaw_rate: float | None = None) -> str:
    """Draw the local drive request and its regime-scaled estimates."""
    if throttle is None or not math.isfinite(throttle):
        return '<div class="target-unavailable">INPUT UNAVAILABLE</div>'
    throttle = max(-1.0, min(1.0, throttle))
    steering = max(-1.0, min(1.0, steering))
    speedColor = "#f17168" if abs(throttle) >= .9 else "#c9db92"
    turnColor = "#f17168" if abs(steering) >= .9 else "#c9db92"
    speedY = 51 - throttle * 32
    turnX = 95 + steering * 34
    velocity = f"{throttle * max_velocity:+.2f} m/s" if max_velocity is not None else "— m/s"
    yawRate = f"{steering * max_yaw_rate:+.1f}°/s" if max_yaw_rate is not None else "— °/s"
    return (
        f'<svg viewBox="0 0 140 124" role="img" aria-label="Speed request {throttle:+.0%}, estimated {velocity}; '
        f'turn request {steering:+.0%}, estimated {yawRate}">'
        '<g font-size="8" fill="#a4a89b">'
        '<text x="15" y="14">+100%</text><text x="15" y="54">0%</text><text x="15" y="94">−100%</text>'
        '<text x="95" y="57" text-anchor="middle">TURN REQUEST</text>'
        '<text x="61" y="89">L</text><text x="129" y="89" text-anchor="end">R</text>'
        '<text x="70" y="116" text-anchor="middle">ESTIMATED FROM REGIME LIMITS</text></g>'
        '<path d="M40 19V83 M61 73H129" stroke="#363d33" stroke-width="6" stroke-linecap="round"/>'
        f'<path d="M40 51V{speedY:.1f}" stroke="{speedColor}" stroke-width="6" stroke-linecap="round"/>'
        f'<path d="M95 73H{turnX:.1f}" stroke="{turnColor}" stroke-width="6" stroke-linecap="round"/>'
        '<path d="M35 51H45 M95 68V78" stroke="#e8e7df" stroke-width="1"/>'
        f'<text x="95" y="22" text-anchor="middle" font-size="14" fill="{speedColor}">{velocity}</text>'
        f'<text x="95" y="37" text-anchor="middle" font-size="10" fill="{speedColor}">{throttle:+.0%}</text>'
        f'<text x="95" y="101" text-anchor="middle" font-size="9" fill="{turnColor}">{steering:+.0%} · {yawRate}</text>'
        '</svg>'
    )


def sparkline(history, fresh: bool) -> str:
    """Only validated numbers enter this SVG; values are historical by design."""
    values = [sample.speed_mps for sample in history if sample.speed_mps is not None][-300:]
    if len(values) < 2:
        return '<svg viewBox="0 0 244 46"><path d="M0 40H244" stroke="#36392f"/></svg>'
    ceiling = max(1.5, max(abs(value) for value in values))
    points = [(i * 244 / (len(values) - 1), 42 - min(abs(v) / ceiling, 1) * 37)
              for i, v in enumerate(values)]
    path = " ".join(f"{'M' if i == 0 else 'L'}{x:.1f},{y:.1f}" for i, (x, y) in enumerate(points))
    opacity = "1" if fresh else ".35"
    return (f'<svg viewBox="0 0 244 46" preserveAspectRatio="none" style="width:100%;height:100%;opacity:{opacity}">'
            '<path d="M0 42H244M0 20H244" stroke="#30332a" stroke-width=".5"/>'
            f'<path d="{path} L244,46 L0,46Z" fill="#c4c9ab" opacity=".05"/>'
            f'<path d="{path}" stroke="#c4c9ab" stroke-width="1.2" fill="none"/></svg>')


def horizon_overlay(pitch: float, roll: float) -> str:
    """A camera attitude ladder; positive pitch moves the zero line downward."""
    if not math.isfinite(pitch) or not math.isfinite(roll):
        return ""
    marks = []
    for degrees in (-20, -10, 0, 10, 20):
        y = -degrees * 3
        width = 100 if degrees == 0 else 65
        marks.append(f'<path d="M{-width},{y}h{width - 14}M14,{y}H{width}"/>'
                     f'<text x="{width + 7}" y="{y + 3}">{degrees:+d}°</text>')
    return ('<svg viewBox="-150 -90 300 180" aria-hidden="true">'
            f'<g transform="rotate({-roll:.2f}) translate(0 {pitch * 3:.2f})" '
            'fill="none" stroke="#e5eacb" stroke-width="1" opacity=".8">'
            + "".join(marks) + '</g></svg>')


class Dashboard:
    def __init__(self, station: BaseStation, *, font_css: str = "", has_suisse: bool = True):
        self.station = station
        self.client = context.client
        self.has_suisse = has_suisse
        self.values = {}
        self._last_camera = -1
        self._last_history_count = -1
        self.cameraRotation = 0
        self._resetting_filters = False
        self._last_horizon: tuple[float, float] | None = None
        self._last_orientation: tuple | None = None
        self._navigation_request: tuple[str, float] | None = None
        self._last_heading: float | None = None
        self._group_fields: dict[str, tuple[str, ...] | None] = {}
        self._log_source: SerialTelemetrySource | None = None
        self._log_cursor = 0
        self._last_navigation: tuple | None = None
        self._navigation_trail: list[tuple[float, float]] = []
        self.map_expanded = False
        self.map_zoom_index = MAP_ZOOM_LEVELS.index(1)
        self.map_zoom_controls = []
        self._map_toggle_sequence = station.map_toggle_sequence
        self._controller_action_sequence = station.controller_action_sequence
        self.camera_zoom_index = 0
        ui.colors(primary="#d2d6b9", secondary="#999b91", accent="#d2d6b9")
        ui.add_css(font_css + "\n" + CSS)
        self._settings()
        self._build()
        self.input_guard = ui.element("div").props('id="virtual-drive-input" data-mode="keyboard" data-enabled="false"').style("display:none")
        ui.on("virtual_drive", self._drive_event)
        ui.on("camera_zoom", self.cycle_camera_zoom)
        ui.on("camera_zoom_in", lambda: self.step_camera_zoom(1))
        ui.on("camera_zoom_out", lambda: self.step_camera_zoom(-1))
        ui.on("map_zoom", self.cycle_map_zoom)
        ui.on("drive_brake_toggle", self.toggle_brake)
        ui.on("camera_gimbal", self._gimbal_event)
        ui.on("camera_home", self.reset_gimbal)
        ui.on("camera_stabilization", self.toggle_stabilization)
        ui.on("map_toggle", self.toggle_map)
        ui.on("map_close", self.close_map)
        self.client.on_disconnect(self._release_inputs)
        ui.add_body_html(f"<script>{KEYBOARD_SCRIPT}</script>")
        self.refresh()
        # Page timers are disposed with their browser client; service polling
        # happens once globally, regardless of how many pages are open.
        ui.timer(0.1, self.refresh)

    def _label(self, key: str, text: str = "—", classes: str = ""):
        label = ui.label(text).classes(classes)
        self.values[key] = label
        return label

    def _text(self, key: str, text: str) -> None:
        label = self.values[key]
        if label.text != text:
            label.set_text(text)

    def _build(self) -> None:
        with ui.element("header").classes("topbar"):
            with ui.element("div").classes("brand"):
                ui.element("img").props(f'src="{PING_ICON_URL}" alt="" width="32" height="32"').classes("brand-icon")
                ui.label("PINGUIN").classes("brand-word")
                ui.element("div").classes("brand-divider")
                ui.html("GROUND SYSTEMS<br>ROVER / 01", sanitize=False).classes("eyebrow")
            with ui.element("div").classes("top-meta"):
                self._label("session", "", "session")
                self._label("mode", "VIRTUAL TELEMETRY", "status-chip").classes("hidden")
                self._label("rate", "VIRTUAL / 10 HZ", "small-meta")
                ui.link("Telemetry", "#telemetry").classes("telemetry-mobile-link telemetry-open")
                ui.link("Operations", "#vision").classes("telemetry-mobile-link telemetry-back")
                self.pause_button = ui.button("Pause simulation", icon="pause", on_click=self.toggle_pause).props("flat dense")
                ui.button("Connections", icon="tune", on_click=self.open_settings).props("outline dense")
        with ui.element("div").classes("shell"):
            with ui.element("nav").classes("rail").props('aria-label="Dashboard sections"'):
                for name, target in (("camera", "vision"), ("rover", "attitude"), ("telemetry", "telemetry")):
                    with ui.element("a").props(f'href="#{target}" aria-label="{target.title()}"').classes("active" if name == "camera" else ""):
                        ui.html(_icon(name), sanitize=False)
                    ui.tooltip(target.title())
                ui.button(icon="tune", on_click=self.open_settings).props('flat round aria-label="Connection settings"').classes("rail-settings").tooltip("Connections")
            with ui.element("main").classes("workspace"):
                with ui.element("div").classes("layout"):
                    self._tools_sidebar()
                    with ui.element("div").classes("visuals"):
                        self._camera()
                        self._pose()
                    self._telemetry()
                self._telemetry_monitor()
                with ui.element("footer").classes("footer"):
                    with ui.element("div").classes("footer-status"):
                        ui.element("span").classes("signal-dot")
                        self._label("footer", "Waiting for telemetry")
                    self._label("footer_camera", "")

    def _camera(self) -> None:
        with ui.element("section").classes("panel").props('id="vision" aria-label="Camera view"'):
            with ui.element("div").classes("panel-head"):
                ui.html('<span class="section-index">01</span> FRONT CAMERA', sanitize=False).classes("panel-title")
                with ui.element("div").classes("head-actions"):
                    self._label("camera_resolution", "960 × 540", "small-meta")
                    self.rotation_button = ui.button("0°", icon="rotate_right", on_click=self.rotate_camera).props('flat dense no-caps aria-label="Rotate camera image clockwise"').tooltip("Rotate camera image 90°")
                    ui.button(icon="fullscreen").props('flat dense aria-label="Expand camera"').on("click", js_handler="() => { const el = document.getElementById('camera-stage'); if(document.fullscreenElement) document.exitFullscreen(); else el.requestFullscreen(); }").tooltip("Fullscreen")
            with ui.element("div").classes("camera-stage").props('id="camera-stage"'):
                self.camera_image = ui.element("img").classes("camera-image").props('alt="Rover front camera"')
                ui.element("div").classes("camera-vignette")
                with ui.element("div").classes("camera-top"):
                    with ui.element("div").classes("camera-label"):
                        ui.element("span").classes("signal-dot")
                        self._label("camera_mode", "SIMULATED CAMERA")
                    with ui.element("div").classes("camera-indicators"):
                        self.stabilization_marker = ui.button("STAB OFF · Z", on_click=self.toggle_stabilization).props('flat dense no-caps aria-label="Cycle camera stabilization mode"').classes("stabilization-marker")
                        self._label("camera_time", "", "camera-stamp")
                self.compass = ui.html(heading_tape(None), sanitize=False).classes("camera-compass")
                self.horizon = ui.html("", sanitize=False).classes("artificial-horizon")
                self.horizon.set_visibility(False)
                ui.html('<svg viewBox="0 0 110 83" aria-hidden="true"><path d="M55 15v23 M55 45v23 M28 41.5h23 M59 41.5h23" fill="none" stroke="white" stroke-width="1.5"/><circle cx="55" cy="41.5" r="2" fill="white"/></svg>', sanitize=False).classes("crosshair")
                with ui.element("div").classes("rangefinder-overlay").props('role="status" aria-label="Camera center rangefinder"'):
                    ui.label("RANGE:").classes("rangefinder-label")
                    self._label("overlay_range", "---- m", "rangefinder-value")
                with ui.element("div").classes("gimbal-tools") as self.gimbal_controls:
                    with ui.element("div").classes("gimbal-buttons"):
                        for icon, label, yaw, pitch, shortcut in (
                            ("keyboard_arrow_left", "Pan camera left", -1, 0, "J"),
                            ("keyboard_arrow_down", "Tilt camera down", 0, -1, "K"),
                            ("keyboard_arrow_up", "Tilt camera up", 0, 1, "I"),
                            ("keyboard_arrow_right", "Pan camera right", 1, 0, "L"),
                        ):
                            ui.button(icon=icon, on_click=lambda y=yaw, p=pitch: self.nudge_gimbal(yaw=y, pitch=p)).props(f'flat dense aria-label="{label}"').tooltip(f"{label} ({shortcut})")
                        ui.button(icon="restart_alt", on_click=self.reset_gimbal).props('flat dense aria-label="Home camera gimbal"').tooltip("Home gimbal (R)")
                    self._label("gimbal_angles", "PAN +0° / TILT +0°", "gimbal-readout")
                self.thermal_note = ui.label("THERMAL STYLE / BRIGHTNESS ONLY").classes("camera-style-note")
                self.thermal_note.set_visibility(False)
                with ui.element("div").classes("camera-bottom"):
                    with ui.element("div").classes("camera-telemetry"):
                        self._label("overlay_gps", "GPS —", "camera-gps")
                        with ui.element("div").classes("camera-readings"):
                            for key, name in (("overlay_speed", "SPEED / M·S⁻¹"), ("overlay_heading", "HEADING / DEG"), ("overlay_pitch", "PITCH / DEG")):
                                with ui.element("div"):
                                    ui.label(name).classes("eyebrow")
                                    self._label(key, "—", "overlay-value")
                    self.gimbal_view = ui.html(gimbal_indicator(self.station.gimbal.state), sanitize=False).classes("gimbal-indicator")
                    self._label("camera_zoom", "1× · ← / → ZOOM · Q CYCLE", "eyebrow")
                self.camera_empty = ui.label("Starting camera…").classes("camera-empty")
                self._expanded_map()
            with ui.element("div").classes("camera-footer"):
                self._label("camera_status", "VIRTUAL TERRAIN / TEST SOURCE")
                self._label("gimbal_hint", "RIGHT STICK / IJKL AIM · R / × HOME")

    def rotate_camera(self) -> None:
        self.cameraRotation = (self.cameraRotation + 90) % 360
        self.rotation_button.set_text(f"{self.cameraRotation}°")
        self._last_camera = -1
        self.refresh()

    def _tools_sidebar(self) -> None:
        with ui.element("aside").classes("panel tools-sidebar").props('id="camera-tools" aria-label="Camera tools"'):
            with ui.element("div").classes("panel-head"):
                ui.label("CAMERA TOOLS").classes("panel-title")
                self._label("filter_count", "0 ACTIVE", "small-meta")
            with ui.element("div").classes("tools-scroll"):
                with ui.element("div").classes("tool-section"):
                    ui.label("STABILIZATION").classes("eyebrow")
                    self.stabilization_button = ui.button("OFF · Z", on_click=self.toggle_stabilization).props('outline dense no-caps aria-label="Cycle camera stabilization mode"').classes("stabilization-toggle")
                    self._label("stabilization_detail", "Follows rover tilt and turns", "subtext")
                    self._label("stabilization_hint", STABILIZATION_HINT, "subtext")
                with ui.element("div").classes("tool-section"):
                    self._camera_filter_controls()
            with ui.element("div").classes("navigation-panel"):
                with ui.element("div").classes("navigation-head"):
                    ui.label("JUSSIEU / LOCAL MAP").classes("eyebrow")
                    ui.button("M", icon="open_in_full", on_click=self.toggle_map).props('flat dense no-caps aria-label="Expand map (M or DualShock touchpad)"')
                with ui.element("div").classes("map-viewport map-mini-viewport") as mini_viewport:
                    self.map_mini = ui.html(campus_map(None, None, None, None), sanitize=False).classes("map-mini").props('role="button" tabindex="0" aria-label="Open Jussieu map"').on("click", self.toggle_map).on("keydown.enter", self.toggle_map).on("keydown.space.prevent", self.toggle_map)
                    self._map_zoom_buttons()
                self._map_wheel_events(mini_viewport)
                self._label("map_gps", "GPS —", "navigation-coordinates")
                self._label("map_state", "SIMULATED GPS / WAITING", "navigation-state")

    def _expanded_map(self) -> None:
        # Keep the map under the fullscreen camera root so M works in fullscreen.
        with ui.element("div").classes("map-overlay").props('role="dialog" aria-modal="true" aria-label="Jussieu navigation map"') as self.map_overlay:
            with ui.element("section").classes("map-expanded-card"):
                with ui.element("div").classes("map-expanded-head"):
                    with ui.element("div"):
                        ui.label("JUSSIEU / PARIS").classes("panel-title")
                        ui.label("NORTH UP · SIMULATED GPS").classes("subtext")
                    ui.button("M / ESC", icon="close", on_click=self.close_map).props('flat dense no-caps aria-label="Close map (M, Escape or DualShock touchpad)"')
                with ui.element("div").classes("map-viewport map-large-viewport") as large_viewport:
                    self.map_large = ui.html(campus_map(None, None, None, None), sanitize=False).classes("map-large")
                    self._map_zoom_buttons()
                self._map_wheel_events(large_viewport)
                with ui.element("div").classes("map-expanded-footer"):
                    self._label("map_large_gps", "GPS —", "navigation-coordinates")
                    ui.label("WHITE · ROVER   AMBER · CAMERA").classes("subtext")
                    ui.link("© OpenStreetMap contributors", "https://www.openstreetmap.org/copyright", new_tab=True).classes("subtext")
        self.map_overlay.set_visibility(False)

    def _map_zoom_buttons(self) -> None:
        with ui.element("div").classes("map-zoom-controls").props('role="group" aria-label="Map zoom controls"'):
            zoom_out = ui.button(icon="remove", on_click=lambda: self.zoom_map(-1)).props('flat dense aria-label="Zoom map out"')
            reset = ui.button("1×", on_click=self.reset_map_zoom).props('flat dense no-caps aria-label="Reset map zoom to 1×"').tooltip("Reset map zoom")
            zoom_in = ui.button(icon="add", on_click=lambda: self.zoom_map(1)).props('flat dense aria-label="Zoom map in"')
        self.map_zoom_controls.append((zoom_out, reset, zoom_in))

    def _map_wheel_events(self, viewport) -> None:
        viewport.on("wheel", self._map_wheel, throttle=.12, trailing_events=False,
                    js_handler="event => { if(event.ctrlKey || event.metaKey) return; event.preventDefault(); event.stopPropagation(); if(event.deltaY) emit({deltaY:event.deltaY}); }")

    def _camera_filter_controls(self) -> None:
        with ui.element("div").classes("filter-controls").props('role="group" aria-label="Camera filter settings"'):
            with ui.element("div").classes("filter-panel-heading"):
                ui.label("FILTERS").classes("eyebrow")
                with ui.element("div").classes("filter-panel-actions"):
                    ui.button("Reset", on_click=self.reset_camera_filters).props('flat dense no-caps aria-label="Reset camera filters"')
            self._label("filter_summary", "Original image", "filter-summary")
            self.filter_switches = {}
            for title, names in (("ENHANCEMENTS", ("denoise", "contrast", "sharpen", "invert")),
                                 ("VISION EFFECTS", VISION_EFFECTS),
                                 ("OVERLAYS", ("edges", "scanlines"))):
                ui.label(title).classes("filter-group-title")
                with ui.element("div").classes("filter-switch-grid"):
                    for name in names:
                        self.filter_switches[name] = ui.checkbox(FILTER_LABELS[name], value=False, on_change=self._camera_filter_changed).props("dense")
                    if title == "OVERLAYS":
                        self.filter_horizon = ui.checkbox("Horizon overlay", value=False, on_change=self._camera_filter_changed).props("dense")
                if title == "VISION EFFECTS":
                    with ui.element("div").classes("vision-mix-controls") as self.vision_controls:
                        ui.label("Vision effect mix (%)").classes("filter-control-label")
                        self.vision_strength = ui.slider(min=0, max=100, step=1, value=75, on_change=self._camera_filter_changed).props('dense label-always aria-label="Vision effect mix"')
                    self.vision_controls.set_visibility(False)
            with ui.element("div").classes("edge-filter-controls") as self.edge_controls:
                ui.label("Edge sensitivity").classes("filter-control-label")
                self.edge_sensitivity = ui.slider(min=0, max=100, step=1, value=50, on_change=self._camera_filter_changed).props('dense label-always aria-label="Edge sensitivity"')
                ui.label("Overlay opacity (%)").classes("filter-control-label")
                self.edge_opacity = ui.slider(min=0, max=100, step=1, value=65, on_change=self._camera_filter_changed).props('dense label-always aria-label="Edge overlay opacity"')
            self.edge_controls.set_visibility(False)
            ui.label("Combine any effects. Thermal colors represent image brightness.").classes("filter-note")

    def _camera_filter_changed(self) -> None:
        if self._resetting_filters:
            return
        self.edge_controls.set_visibility(self.filter_switches["edges"].value)
        self.vision_controls.set_visibility(any(self.filter_switches[name].value for name in VISION_EFFECTS))
        active = sum(bool(control.value) for control in self.filter_switches.values()) + bool(self.filter_horizon.value)
        self._text("filter_count", f"{active} ACTIVE")
        names = [FILTER_LABELS[name] for name, control in self.filter_switches.items() if control.value]
        if self.filter_horizon.value:
            names.append("Horizon overlay")
        self._text("filter_summary", " · ".join(names) if names else "Original image")
        self.thermal_note.set_visibility(self.filter_switches["thermal"].value and self.vision_strength.value > 0)
        self._last_camera = -1
        self.refresh()

    def reset_camera_filters(self) -> None:
        self._resetting_filters = True
        try:
            for control in self.filter_switches.values():
                control.set_value(False)
            self.filter_horizon.set_value(False)
            self.edge_sensitivity.set_value(50)
            self.edge_opacity.set_value(65)
            self.vision_strength.set_value(75)
        finally:
            self._resetting_filters = False
        self._camera_filter_changed()

    def _pose(self) -> None:
        with ui.element("section").classes("panel").props('id="attitude" aria-label="Robot attitude"'):
            with ui.element("div").classes("panel-head"):
                ui.html('<span class="section-index">02</span> VEHICLE ATTITUDE', sanitize=False).classes("panel-title")
                with ui.element("div").classes("head-actions"):
                    self._label("pose_status", "TELEMETRY DRIVEN", "small-meta")
                    ui.button(icon="restart_alt", on_click=lambda: self.rover.reset_view()).props('flat dense aria-label="Reset 3D view"').tooltip("Reset 3D view")
            with ui.element("div").classes("pose-body"):
                self.rover = RoverView(background_color="#191a18", height=240)
                self.rover.scene.classes("rover-scene")
                with ui.element("div").classes("orientation-dial wheel-slip-panel").props('role="group" aria-label="Top-down wheel slip"'):
                    self._label("wheel_panel_title", "WHEEL SLIP / RPM", "eyebrow")
                    self.slip_view = ui.html(wheel_slip_indicator(None, 30), sanitize=False).classes("orientation-svg")
                    self.slip_threshold = ui.slider(min=0, max=100, step=1, value=30).props('dense aria-label="Red wheel slip threshold (%)"')
                    self._label("slip_threshold", classes="orientation-caption")
                with ui.element("div").classes("orientation-dial wheel-slip-panel target-panel").props('role="group" aria-label="Target speed and regime limits"'):
                    ui.label("TARGET SPEED / REGIME").classes("eyebrow")
                    self.target_view = ui.html(target_speed_indicator(None, None), sanitize=False).classes("target-svg")
                    self.navigation_mode_button = ui.button("REGIME —", on_click=self._cycle_navigation_mode)
                    self.navigation_mode_button.props('flat dense no-wrap aria-label="Cycle navigation mode"').classes("regime-name")
                    self.navigation_mode_button.disable()
                with ui.element("div").classes("orientation-dials").props('role="group" aria-label="Vehicle pitch, roll and north-up heading"'):
                    self.orientation_views = {}
                    for key, name, caption, render in (
                        ("pitch", "PITCH", "SIDE VIEW", pitch_indicator),
                        ("roll", "ROLL", "FRONT VIEW", roll_indicator),
                        ("heading", "NORTH UP · 0°", "", lambda _: heading_indicator(None, None)),
                    ):
                        with ui.element("div").classes("orientation-dial"):
                            ui.label(name).classes("eyebrow")
                            self.orientation_views[key] = ui.html(render(None), sanitize=False).classes("orientation-svg")
                            self._label(key, "—", "orientation-value")
                            if key == "heading":
                                self._label("orientation_camera", "CAM —", "orientation-camera")
                            else:
                                ui.label(caption).classes("orientation-caption")
                    with ui.element("div").classes("orientation-legend"):
                        ui.label("WHITE · ROVER").classes("orientation-rover-key")
                        ui.label("AMBER · CAMERA").classes("orientation-camera")
            with ui.element("div").classes("pose-foot"):
                ui.label("Drag to orbit · Scroll to zoom")
                self._label("regime_limits", "", "regime-limits")
                self._label("pose_position", "X +0.0 m / Y +0.0 m")

    def _cycle_navigation_mode(self) -> None:
        state = self.station.telemetry.state
        source = self.station.telemetry.source
        mode = getattr(state.sample, "regime_mode", None)
        if type(source) is not SerialTelemetrySource or not source.transport_connected or mode not in ("AWAIT", *NAVIGATION_MODES):
            return
        modes = tuple(NAVIGATION_MODES)
        nextMode = (modes.index(mode) + 1) % len(modes) if mode in NAVIGATION_MODES else 0
        if source.send_rover_command(f"NAV_MODE:{nextMode}"):
            self.navigation_mode_button.set_text(f"REQUESTED {NAVIGATION_MODES[modes[nextMode]]}")
            self.navigation_mode_button.disable()
            self._navigation_request = (mode, time.monotonic() + 3.0)

    def _metric(self, key: str, name: str, unit: str) -> None:
        with ui.element("div").classes("metric-row"):
            ui.label(name).classes("metric-name")
            with ui.element("div").classes("flex items-baseline"):
                self._label(key, "—", "value")
                ui.label(unit).classes("unit")

    def _telemetry(self) -> None:
        with ui.element("aside").classes("panel telemetry").props('aria-label="Robot telemetry summary"'):
            with ui.element("div").classes("panel-head"):
                ui.label("TELEMETRY").classes("panel-title")
                self._label("link", "WAITING", "small-meta")
            with ui.element("div").classes("telemetry-section"):
                with ui.element("div").classes("speed-header"):
                    ui.label("GROUND SPEED").classes("eyebrow")
                    ui.label("m/s").classes("small-meta")
                self._label("speed", "—", "speed-value")
                self._label("body_velocity", "", "subtext")
                self.graph = ui.html(sparkline((), False), sanitize=False).classes("sparkline")
                with ui.element("div").classes("graph-foot"):
                    self._label("history_label", "SPEED HISTORY")
                    ui.label("30 S BUFFER")
            with ui.element("div").classes("telemetry-section"):
                ui.label("POWER & THERMALS").classes("eyebrow")
                self._metric("battery", "Battery", "%")
                with ui.element("div").classes("battery-bar"):
                    self.battery_fill = ui.element("div").classes("battery-fill").style("width:0%")
                self._metric("voltage", "Bus voltage", "V")
                self._metric("temperature", "Motor temperature", "°C")
                self._metric("distance", "Distance travelled", "m")
            with ui.element("div").classes("telemetry-section"):
                with ui.element("div").classes("traction-head"):
                    ui.label("WHEEL SLIP").classes("eyebrow")
                    ui.label("FL / FR / RL / RR").classes("subtext")
                self.wheel_fills = []
                for i, label in enumerate(("FL", "FR", "RL", "RR")):
                    with ui.element("div").classes("wheel-row"):
                        ui.label(label).classes("wheel-label")
                        with ui.element("div").classes("wheel-track"):
                            self.wheel_fills.append(ui.element("div").classes("wheel-fill").style("width:0%"))
                        self._label(f"slip_{i}", "—", "wheel-value")
                ui.label("Slip ratio · lower means less wheel spin").classes("subtext mt-3")
            with ui.element("div").classes("telemetry-section"):
                ui.label("RADIO LINK").classes("eyebrow")
                self._metric("rssi", "Signal", "dBm")
                self._metric("latency", "Latency", "ms")
                self._metric("age", "Last packet", "ms")
                self._label("packet_count", "0 VALID PACKETS", "subtext mt-2")
                self._label("serial_link", "", "subtext mt-2")
                self._label("serial_preview", "", "subtext").style("overflow-wrap:anywhere")
                self._label("rover_groups", "", "subtext mt-2").style("white-space:pre-line;overflow-wrap:anywhere")
                self.radio_test_button = ui.button("Send TEST line", icon="send", on_click=self.send_radio_test).props("outline dense")
            with ui.element("div").classes("telemetry-section").style("border-bottom:0"):
                ui.label("DRIVE INPUT").classes("eyebrow")
                self.drive_toggle = ui.toggle({"keyboard": "Keyboard", "dualshock": "DualShock"},
                                              value=self.station.drive.mode,
                                              on_change=lambda e: self.station.set_drive_mode(e.value)).props('dense no-caps toggle-text-color=black aria-label="Virtual drive input"').classes("drive-mode")
                with ui.element("div").classes("controller-row"):
                    ui.label("DualShock 4")
                    self._label("controller", "DISABLED", "controller-state")
                with ui.element("div").classes("controller-axes"):
                    self._label("left_stick", "L  +0.00 / +0.00", "axis-readout")
                    self._label("right_stick", "R  +0.00 / +0.00", "axis-readout")
                self._label("drive_command", "Throttle +0.00 / Turn +0.00", "control-hint")
                self.brake_button = ui.button("BRAKE OFF", on_click=self.toggle_brake).props('outline dense no-caps aria-pressed="false"').classes("brake-toggle")
                self._label("drive_hint", "W/S or ↑/↓ drive · A/D steer · Space brake", "control-hint")
                ui.label("←/→ or R1/L1 camera zoom · M / Touchpad map · Enter / △ map zoom").classes("control-hint")
                ui.label("× / X / R camera reset · Share / Z stabilization").classes("control-hint")

    def _telemetry_monitor(self) -> None:
        self.group_tables: dict[str, ui.html] = {}
        self.legacy_group_cards = {}
        with ui.element("section").classes("telemetry-monitor").props('id="telemetry" aria-label="Telemetry monitor"'):
            with ui.element("div").classes("telemetry-group-columns"):
                for group, title in (GROUP_TITLES | LEGACY_GROUP_TITLES).items():
                    with ui.element("section").classes("panel telemetry-group-card") as card:
                        if group in LEGACY_GROUP_TITLES:
                            self.legacy_group_cards[group] = card
                            card.set_visibility(False)
                        with ui.element("div").classes("panel-head"):
                            ui.label(f"{group} / {title}").classes("panel-title")
                        self._label(f"group_status_{group}", "Waiting", "telemetry-group-status")
                        self.group_tables[group] = ui.html("", sanitize=False)
            with ui.element("section").classes("panel telemetry-terminal"):
                with ui.element("div").classes("panel-head"):
                    ui.label("Serial receive log").classes("panel-title")
                    self._label("terminal_status", "No serial source", "small-meta")
                self.terminal_log = ui.log(max_lines=RAW_LOG_LINES).classes("telemetry-terminal-log")

    def _refresh_telemetry_monitor(self, source: SerialTelemetrySource | None, now: float) -> None:
        frames = source.latest_group_frames if source is not None else {}
        for group, table in self.group_tables.items():
            frame = frames.get(group)
            if group in self.legacy_group_cards:
                self.legacy_group_cards[group].set_visibility(frame is not None)
            fields = frame[1] if frame is not None else None
            status = "Waiting"
            if frame is not None:
                status = "Stale" if now - frame[0] >= GROUP_EXPIRY[group] else "Received"
            self._text(f"group_status_{group}", status)
            if fields == self._group_fields.get(group):
                continue
            self._group_fields[group] = fields
            labels = GROUP_FIELDS.get((group, len(fields)), ()) if fields else ()
            rows = "".join(f"<dt>{escape(labels[i] if labels else f'Field {i + 1}')}</dt><dd>{escape(value)}</dd>"
                           for i, value in enumerate(fields or ()))
            table.set_content(f'<dl class="telemetry-group-fields">{rows}</dl>' if rows else "")

        if source is not self._log_source:
            self.terminal_log.clear()
            self._log_source = source
            self._log_cursor = 0
        if source is None:
            self._text("terminal_status", "No serial source")
            return
        self._log_cursor, lines = source.raw_lines_since(self._log_cursor)
        for timestamp, line in lines:
            self.terminal_log.push(f'{timestamp.time().isoformat(timespec="milliseconds")}  {line}')
        self._text("terminal_status", f"{source.port} / {source.baudrate} baud" if self._log_cursor
                   else f"{source.port} / waiting for lines")

    def _settings(self) -> None:
        with ui.dialog() as self.dialog, ui.card().classes("settings-card"):
            ui.label("CONNECTIONS").classes("eyebrow")
            ui.html("<h2>Camera source</h2>", sanitize=False)
            self.camera_select = ui.select({"simulation": "Virtual terrain", "network": "Pi / network camera", "usb": "USB camera"},
                                           value="simulation", label="Camera").props("outlined dense")
            self.camera_address = ui.input("Stream address", value="tcp://192.168.137.22:8888").props("outlined dense").classes("w-full")
            self.camera_address.bind_visibility_from(self.camera_select, "value", backward=lambda value: value == "network")
            self.camera_index = ui.number("USB camera index", value=0, min=0, precision=0).props("outlined dense")
            self.camera_index.bind_visibility_from(self.camera_select, "value", backward=lambda value: value == "usb")
            ui.label("Close VLC before connecting. If the Pi stream stops, restart it on the Pi and reconnect here. Camera selection is shared by all dashboard tabs.").classes("dialog-note")
            ui.button("Connect camera / Retry", icon="videocam", on_click=self.apply_camera).props("outline")
            ui.separator()
            ui.html("<h2>Telemetry source</h2>", sanitize=False)
            ui.label("Radio bench runs the virtual terrain and sends TEST, DRIVE, STATE and WHEELS lines through one USB radio. Open the other radio in your serial app.").classes("dialog-note")
            self.source_select = ui.select({"simulation": "Virtual robot", "serial": "USB / serial telemetry and gimbal", "radio_bench": "Radio bench · send and receive"}, value="simulation", label="Source").props("outlined dense")
            self.port_input = ui.input("Serial port", value=loadPort(), placeholder="COM7 or /dev/ttyUSB0").props("outlined dense")
            self.baud_input = ui.number("Baud rate", value=57600, min=1, precision=0).props("outlined dense")
            self.port_hint = ui.label("").classes("dialog-note")
            ui.button("Scan USB ports", icon="refresh", on_click=self.scan_ports).props("flat dense")
            ui.label("Select the receiver port at 57600 baud. Rover groups and raw lines appear under Radio Link.").classes("dialog-note")
            self.font_note = ui.label("Suisse Light + Medium / local fonts" if self.has_suisse else "Suisse not found / use --font-dir to select its folder").classes("subtext")
            with ui.element("div").classes("dialog-actions"):
                ui.button("Cancel", on_click=self.dialog.close).props("flat")
                ui.button("Apply source", on_click=self.apply_source).props("outline")

    def scan_ports(self) -> None:
        from serial.tools import list_ports
        ports = [f"{p.device} · {p.description}" for p in list_ports.comports()]
        self.port_hint.set_text("\n".join(ports) if ports else "No serial ports detected. You can enter a port manually.")

    def open_settings(self) -> None:
        self.station.stop_drive()
        camera = self.station.camera
        device = getattr(camera, "device", None)
        self.camera_select.set_value("simulation" if camera.simulated else "usb" if isinstance(device, int) else "network")
        if isinstance(device, str):
            self.camera_address.set_value(device)
        elif isinstance(device, int):
            self.camera_index.set_value(device)
        source = self.station.telemetry.source
        self.source_select.set_value("simulation" if isinstance(source, SimulatedTelemetrySource) else
                                     "radio_bench" if isinstance(source, RadioBenchSource) else "serial")
        if isinstance(source, SerialTelemetrySource):
            self.port_input.set_value(source.port)
            self.baud_input.set_value(source.baudrate)
        self.dialog.open()
        self.scan_ports()

    def apply_camera(self) -> None:
        kind = self.camera_select.value
        if kind == "network":
            address = (self.camera_address.value or "").strip()
            if not address.startswith(("tcp://", "rtsp://", "http://", "https://", "udp://")):
                ui.notify("Enter a stream address such as tcp://192.168.137.22:8888")
                return
            camera = FFmpegCameraSource(address, fps=20)
        elif kind == "usb":
            index = self.camera_index.value
            if index is None or not math.isfinite(index) or index < 0 or index != int(index):
                ui.notify("Enter a nonnegative whole-number camera index.")
                return
            camera = OpenCVCameraSource(int(index))
        else:
            camera = SimulatedCameraSource()
        self.station.replace_camera(camera)
        self._last_camera = -1
        self.dialog.close()
        self.refresh()

    def apply_source(self) -> None:
        if self.source_select.value in ("serial", "radio_bench"):
            port = (self.port_input.value or "").strip()
            baud = self.baud_input.value
            if not port or baud is None or baud <= 0 or baud != int(baud):
                ui.notify("Enter a serial port and a positive whole-number baud rate.")
                return
            source_type = RadioBenchSource if self.source_select.value == "radio_bench" else SerialTelemetrySource
            source = source_type(port, baudrate=int(baud))
        else:
            source = SimulatedTelemetrySource()
        self.station.replace_telemetry(source)
        if self.source_select.value in ("serial", "radio_bench"):
            try:
                savePort(port)
            except OSError:
                ui.notify("Could not save the serial port for next time.")
        self._last_history_count = -1
        self.dialog.close()
        self.refresh()

    def toggle_pause(self) -> None:
        source = self.station.telemetry.source
        if isinstance(source, SimulatedTelemetrySource):
            self.station.stop_drive()
            source.paused = not source.paused
            self.refresh()

    def send_radio_test(self) -> None:
        source = self.station.telemetry.source
        if not isinstance(source, RadioBenchSource):
            return
        sent = source.send_test(time.monotonic())
        ui.notify("TEST line sent to radio" if sent else "Radio port is not open; check Radio Link")
        self.refresh()

    def _drive_event(self, event) -> None:
        payload = event.args
        if not isinstance(payload, dict):
            return
        if payload.get("release") is True:
            self.station.drive.clear(self.client.id)
        elif self.station.drive_input_enabled:
            self.station.drive.keyboard(self.client.id, payload.get("throttle", 0),
                                        payload.get("steering", 0), payload.get("brake", False))

    def toggle_brake(self) -> None:
        self.station.toggle_brake()
        self.refresh()

    def cycle_camera_zoom(self) -> None:
        self._set_camera_zoom_index((self.camera_zoom_index + 1) % len(CAMERA_ZOOM_LEVELS))

    def step_camera_zoom(self, step: int) -> None:
        self._set_camera_zoom_index(max(0, min(len(CAMERA_ZOOM_LEVELS) - 1, self.camera_zoom_index + step)))

    def _set_camera_zoom_index(self, index: int) -> None:
        self.camera_zoom_index = index
        zoom = CAMERA_ZOOM_LEVELS[self.camera_zoom_index]
        self.camera_image.style(f"transform:scale({zoom})")
        self._text("camera_zoom", f"{zoom}× · ← / → ZOOM · Q CYCLE")

    @property
    def gimbal_available(self) -> bool:
        return hasattr(self.station.camera, "set_gimbal")

    def _update_rover_gimbal(self, sample: RoverTelemetrySample | None, *, simulated: bool) -> None:
        if simulated:
            pose = self.station.gimbal.state
        elif (isinstance(sample, RoverTelemetrySample) and sample.gimbal_pan_deg is not None
              and sample.gimbal_pitch_deg is not None):
            pose = GimbalPose(yaw_deg=sample.gimbal_pan_deg, pitch_deg=sample.gimbal_pitch_deg)
        else:
            pose = GimbalPose()
        self.rover.update_gimbal(pose)

    def _release_inputs(self) -> None:
        self.station.drive.clear(self.client.id)
        self.station.gimbal.release(self.client.id)

    def _gimbal_event(self, event) -> None:
        payload = event.args
        if not self.gimbal_available or not isinstance(payload, dict):
            return
        if payload.get("release") is True:
            self.station.gimbal.release(self.client.id)
        else:
            self.station.gimbal.set_input(self.client.id, payload.get("yaw", 0), payload.get("pitch", 0))

    def nudge_gimbal(self, *, yaw: float = 0, pitch: float = 0) -> None:
        source = self.station.telemetry.source
        if type(source) is SerialTelemetrySource:
            source.send_gimbal_command(f"GIMBAL_NUDGE:{yaw:+.1f},{pitch:+.1f}")
            self.refresh()
        elif self.gimbal_available:
            self.station.gimbal.nudge(yaw=yaw, pitch=pitch)
            self.refresh()

    def reset_gimbal(self) -> None:
        source = self.station.telemetry.source
        if type(source) is SerialTelemetrySource:
            source.send_gimbal_command("GIMBAL_HOME:")
            self.refresh()
        elif self.gimbal_available:
            self.station.gimbal.reset()
            self.refresh()

    def toggle_stabilization(self) -> None:
        self.station.toggle_stabilization()
        self.refresh()

    def _set_map_expanded(self, expanded: bool) -> None:
        self.map_expanded = expanded
        self.map_overlay.set_visibility(expanded)
        if expanded:
            self.map_large.set_content(self.map_mini.content)
            self._release_inputs()

    def toggle_map(self) -> None:
        self._set_map_expanded(not self.map_expanded)
        self.refresh()

    def close_map(self) -> None:
        self._set_map_expanded(False)
        self.refresh()

    def _set_map_zoom_index(self, index: int) -> None:
        index = max(0, min(len(MAP_ZOOM_LEVELS) - 1, index))
        if index == self.map_zoom_index:
            return
        self.map_zoom_index = index
        for zoom_out, reset, zoom_in in self.map_zoom_controls:
            zoom_out.set_enabled(index > 0)
            zoom_in.set_enabled(index < len(MAP_ZOOM_LEVELS) - 1)
            reset.set_text(f"{MAP_ZOOM_LEVELS[index]:g}×")
        self.refresh()

    def zoom_map(self, step: int) -> None:
        self._set_map_zoom_index(self.map_zoom_index + step)

    def reset_map_zoom(self) -> None:
        self._set_map_zoom_index(MAP_ZOOM_LEVELS.index(1))

    def cycle_map_zoom(self) -> None:
        self._set_map_zoom_index((self.map_zoom_index + 1) % len(MAP_ZOOM_LEVELS))

    def _map_wheel(self, event) -> None:
        delta = event.args.get("deltaY") if isinstance(event.args, dict) else None
        if isinstance(delta, (int, float)) and not isinstance(delta, bool) and math.isfinite(delta) and delta:
            self.zoom_map(1 if delta < 0 else -1)

    def _refresh_navigation(self, motion, *, available: bool, simulated: bool,
                            camera_heading: float | None) -> None:
        position = simulated_position(motion.x_m, motion.y_m) if available else None
        coordinates = (f"{abs(position.lat_deg):.6f}° {'N' if position.lat_deg >= 0 else 'S'}  "
                       f"{abs(position.lon_deg):.6f}° {'E' if position.lon_deg >= 0 else 'W'}") if position else "GPS —"
        self._text("overlay_gps", f"SIM GPS · {coordinates}" if position else "GPS —")
        self._text("map_gps", coordinates)
        self._text("map_large_gps", coordinates)
        self._text("map_state", "SIMULATED GPS · M / TOUCHPAD EXPAND" if available else
                   "SIMULATED GPS / NO FRESH FIX" if simulated else "GPS UNAVAILABLE / USB TELEMETRY")
        if available:
            point = (round(motion.x_m, 1), round(motion.y_m, 1))
            if not self._navigation_trail or math.dist(point, self._navigation_trail[-1]) >= 1:
                self._navigation_trail.append(point)
                self._navigation_trail = self._navigation_trail[-300:]
        values = (round(motion.x_m, 1), round(motion.y_m, 1), round(motion.heading_deg, 1),
                  round(camera_heading, 1) if camera_heading is not None else None) if available else (None,) * 4
        zoom = MAP_ZOOM_LEVELS[self.map_zoom_index]
        navigation = (*values, zoom, tuple(self._navigation_trail))
        if navigation != self._last_navigation:
            content = campus_map(*values, trail=tuple(self._navigation_trail), zoom=zoom)
            self.map_mini.set_content(content)
            if self.map_expanded:
                self.map_large.set_content(content)
            self._last_navigation = navigation

    def refresh(self) -> None:
        manager = self.station.telemetry
        state = manager.state
        sample = state.sample
        source = manager.source
        radio_bench = isinstance(source, RadioBenchSource)
        simulated = isinstance(source, (SimulatedTelemetrySource, RadioBenchSource))
        paused = isinstance(source, SimulatedTelemetrySource) and source.paused
        now = time.monotonic()
        actions = [(sequence, action) for sequence, action in self.station.controller_actions
                   if sequence > self._controller_action_sequence]
        self._controller_action_sequence = self.station.controller_action_sequence
        for _, action in actions:
            if action == "camera_zoom_in":
                self.step_camera_zoom(1)
            elif action == "camera_zoom_out":
                self.step_camera_zoom(-1)
            elif action == "map_zoom":
                self.cycle_map_zoom()
        sequence = self.station.map_toggle_sequence
        if sequence != self._map_toggle_sequence:
            if (sequence - self._map_toggle_sequence) % 2:
                self._set_map_expanded(not self.map_expanded)
            self._map_toggle_sequence = sequence
        remoteGimbal = type(source) is SerialTelemetrySource
        requestedMode = self.station.rover_gimbal_mode
        roverMode = getattr(sample, "gimbal_mode", None) if remoteGimbal and source.transport_connected else None
        stabilizationAvailable = roverMode is not None if remoteGimbal else self.gimbal_available
        self.input_guard.props(f'data-mode="{self.station.drive.mode}" data-enabled="{str(self.station.drive_input_enabled).lower()}" data-gimbal="{str(self.gimbal_available).lower()}" data-stabilization="{str(stabilizationAvailable).lower()}" data-map-open="{str(self.map_expanded).lower()}"')
        self.gimbal_controls.set_visibility(self.gimbal_available or (remoteGimbal and source.transport_connected))
        liveGimbal = (remoteGimbal and sample is not None and
                      sample.gimbal_pan_deg is not None and sample.gimbal_pitch_deg is not None)
        self.gimbal_view.set_visibility(self.gimbal_available or liveGimbal)
        self._text("gimbal_hint", "RIGHT STICK / IJKL AIM · R / × HOME" if self.gimbal_available else "FORWARD VIEW")
        gimbal = self.station.gimbal.state
        mode = self.station.gimbal.stabilization_mode if self.gimbal_available else StabilizationMode.OFF
        label, detail = STABILIZATION_LABELS[mode]
        enabled = mode is not StabilizationMode.OFF
        limited = enabled and self.station.gimbal.limited
        if remoteGimbal:
            label, detail = {
                0: ("HEADLESS", "World yaw and pitch locked"),
                1: ("FOLLOW YAW", "Follows rover yaw · Pitch locked"),
                2: ("FOLLOW BOTH", "Follows rover yaw and pitch"),
                None: ("WAITING", "Waiting for gimbal mode telemetry"),
            }[roverMode]
            if self.station._requested_gimbal_mode is not None and requestedMode is not None:
                detail += " · Command sent, awaiting telemetry"
            enabled = roverMode in (0, 1)
            limited = False
        hint = "Z: Headless / Follow Yaw / Follow Both" if remoteGimbal else STABILIZATION_HINT
        self._text("stabilization_hint", hint)
        self.stabilization_marker.set_text(f"STAB {label}" + (" · LIMIT" if limited else " · Z"))
        self.stabilization_button.set_text(f"{label} · Z")
        for control in (self.stabilization_marker, self.stabilization_button):
            control.set_enabled(stabilizationAvailable)
            control.props(f'aria-label="Camera stabilization: {label.title()}. Cycle mode (Z)" title="{detail}. {hint}"')
            control.classes(add="stabilization-on" if enabled else "stabilization-off", remove="stabilization-off" if enabled else "stabilization-on")
        self._text("stabilization_detail", detail if remoteGimbal else "Available with virtual camera" if not self.gimbal_available else
                   detail + (" · Compensation limit reached" if limited else ""))
        self._text("gimbal_angles", f"PAN {gimbal.yaw_deg:+.0f}° / TILT {gimbal.pitch_deg:+.0f}°")
        if liveGimbal:
            self.gimbal_view.set_content(gimbal_indicator(GimbalPose(yaw_deg=sample.gimbal_pan_deg,
                                                                    pitch_deg=sample.gimbal_pitch_deg)))
        elif self.gimbal_available:
            self.gimbal_view.set_content(gimbal_indicator(gimbal))
        if self.drive_toggle.value != self.station.drive.mode:
            self.drive_toggle.set_value(self.station.drive.mode)
        self.drive_toggle.set_enabled(self.station.drive_input_enabled)
        self._text("session", f"LOCAL STATION  /  {datetime.now():%H:%M:%S}")
        self._text("mode", "RADIO BENCH + TERRAIN" if radio_bench else "VIRTUAL TELEMETRY" if simulated else "USB TELEMETRY")
        self._text("rate", "RADIO / VIRTUAL 10 HZ" if radio_bench else "PAUSED / VIRTUAL" if paused else "VIRTUAL / 10 HZ" if simulated else "USB / TELEMETRY")
        self.pause_button.set_visibility(isinstance(source, SimulatedTelemetrySource))
        self.pause_button.set_text("Resume simulation" if paused else "Pause simulation")
        self.pause_button.props(f"icon={'play_arrow' if paused else 'pause'}")
        radio_open = radio_bench and source.radio_connected
        self._text("link", "SIM + RADIO" if radio_open else "SIM / RADIO OFF" if radio_bench else state.status.value.upper())
        self.values["link"].style(f"color:{'var(--accent)' if state.connected and (not radio_bench or radio_open) else 'var(--warn)'}")
        self._text("age", f"{state.age_seconds * 1000:.0f}" if state.age_seconds is not None else "—")
        self._text("packet_count", f"{state.received_count:,} VALID / {state.rejected_count:,} REJECTED")
        self.radio_test_button.set_visibility(radio_bench)
        serial_visible = isinstance(source, SerialTelemetrySource)
        self._refresh_telemetry_monitor(source if serial_visible else None, now)
        for key in ("serial_link", "serial_preview"):
            self.values[key].set_visibility(serial_visible)
        if serial_visible:
            if source.error:
                serial_status = f"{source.port} · {source.error}"
            elif source.radio_connected if radio_bench else source.transport_connected:
                serial_status = f"{source.port} OPEN · {source.bytes_received:,} BYTES RECEIVED"
                if radio_bench:
                    serial_status += f" · {source.bytes_sent:,} BYTES SENT"
                if source.bytes_received and not state.received_count:
                    serial_status += " · RAW TEXT RECEIVED" if radio_bench else " · NO VALID TELEMETRY"
            else:
                serial_status = f"{source.port} · CONNECTING"
            self._text("serial_link", serial_status)
            self._text("serial_preview", "Last received: " + (source.last_raw_line or
                       ("bytes arriving, waiting for newline" if source.bytes_received else "none yet")) +
                       (f" · Last sent: {source.last_sent_line or 'none yet'}" if radio_bench else ""))
        fields = {"speed": ("speed_mps", ".2f"), "battery": ("battery_percent", ".0f"),
                  "voltage": ("battery_voltage", ".1f"), "temperature": ("motor_temp_c", ".1f"),
                  "distance": ("distance_m", ".1f"), "rssi": ("signal_rssi_dbm", ".0f"), "latency": ("latency_ms", ".0f")}
        for key, (attr, fmt) in fields.items():
            value = getattr(sample, attr, None)
            self._text(key, format(value, fmt) if value is not None else "-")
        bodyVelocity = getattr(sample, "velocity_body_mps", None)
        self.values["body_velocity"].set_visibility(bodyVelocity is not None)
        self._text("body_velocity", f"Vx {bodyVelocity[0]:+.2f} / Vy {bodyVelocity[1]:+.2f} m/s"
                   if bodyVelocity is not None else "")
        groupDetails = rover_group_details(sample) if isinstance(sample, RoverTelemetrySample) else ""
        self.values["rover_groups"].set_visibility(bool(groupDetails))
        self._text("rover_groups", groupDetails)
        motion = self.station.virtual_rover.state
        vehicle_attitude = (motion if simulated else sample) if sample else None
        for key in ("pitch", "roll", "heading"):
            value = getattr(vehicle_attitude, key + "_deg") if vehicle_attitude else None
            text = f"{value:+.1f}°" if value is not None and key != "heading" else f"{round(value, 1) % 360:05.1f}°" if value is not None else "—"
            self._text(key, text)
        speed = getattr(sample, "speed_mps", None)
        self._text("overlay_speed", f"{speed:.2f}" if speed is not None else "—")
        camera_attitude = self.station.virtual_rover.state if self.gimbal_available else sample
        cameraYaw = getattr(camera_attitude, "heading_deg", None) if sample else None
        camera_pitch = getattr(camera_attitude, "pitch_deg", None) if sample else None
        cameraRoll = getattr(camera_attitude, "roll_deg", None) if sample else None
        if sample and self.gimbal_available:
            cameraYaw += gimbal.yaw_deg
            camera_pitch += gimbal.pitch_deg
            cameraRoll += gimbal.roll_deg
        if not simulated:
            yaw = getattr(sample, "heading_deg", None)
            pan = getattr(sample, "gimbal_pan_deg", None)
            cameraYaw = (yaw + pan) if yaw is not None and pan is not None else None
        camera_heading = cameraYaw % 360 if cameraYaw is not None else None
        heading = round(camera_heading, 1) % 360 if camera_heading is not None else None
        self._text("overlay_heading", f"{heading:05.1f}°" if heading is not None else "-")
        self._text("overlay_pitch", f"{camera_pitch:+.1f}°" if camera_pitch is not None else "-")
        if heading != self._last_heading:
            self.compass.set_content(heading_tape(heading))
            self._last_heading = heading
        # Live camera bearing uses rover yaw and body-relative gimbal pan.
        orientation_camera = camera_heading if sample and (not simulated or self.gimbal_available) else None
        angles = (getattr(vehicle_attitude, axis + "_deg", None) for axis in ("pitch", "roll", "heading"))
        orientation = tuple(round(value, 1) if value is not None else None for value in angles) + (
                                round(orientation_camera, 1) if orientation_camera is not None else None,)
        tiltLimit = getattr(sample, "regime_pitch_roll_limit_deg", None)
        orientation += (tiltLimit,)
        if orientation != self._last_orientation:
            pitch, roll, heading, bearing, tiltLimit = orientation
            self.orientation_views["pitch"].set_content(pitch_indicator(pitch, tiltLimit))
            self.orientation_views["roll"].set_content(roll_indicator(roll, tiltLimit))
            self.orientation_views["heading"].set_content(heading_indicator(heading, bearing))
            self._last_orientation = orientation
        regimeName = getattr(sample, "regime_mode", None)
        maxVelocity = getattr(sample, "regime_max_velocity_mps", None)
        command = self.station.drive_command
        requested = (0.0 if command.brake else command.throttle) if self.station.drive_input_enabled else None
        turning = 0.0 if command.brake else command.steering
        maxYawRate = getattr(sample, "regime_max_yaw_rate_dps", None)
        self.target_view.set_content(target_speed_indicator(requested, maxVelocity, turning, maxYawRate))
        canChangeMode = (type(source) is SerialTelemetrySource and source.transport_connected
                         and regimeName in ("AWAIT", *NAVIGATION_MODES))
        if self._navigation_request is not None:
            previousMode, expiresAt = self._navigation_request
            if not canChangeMode or regimeName != previousMode or now >= expiresAt:
                self._navigation_request = None
        if self._navigation_request is None:
            self.navigation_mode_button.set_text(NAVIGATION_MODES.get(regimeName, regimeName or "REGIME —"))
        self.navigation_mode_button.set_enabled(canChangeMode and self._navigation_request is None)
        def regimeValue(attribute, suffix):
            value = getattr(sample, attribute, None)
            return f"{value:g}{suffix}" if value is not None else "—"
        self.values["regime_limits"].set_visibility(maxVelocity is not None)
        self._text("regime_limits", " / ".join((
            "MAX " + regimeValue("regime_max_velocity_mps", " m/s"),
            "ACC " + regimeValue("regime_max_acceleration_mps2", " m/s²"),
            "YAW " + regimeValue("regime_max_yaw_rate_dps", "°/s"),
            "YAW ACC " + regimeValue("regime_max_yaw_acceleration_dps2", "°/s²"),
            "TILT ±" + regimeValue("regime_pitch_roll_limit_deg", "°"),
            "YAW LIMIT " + regimeValue("regime_yaw_limit_deg", "°"),
            "OUTPUT " + regimeValue("regime_min_output_percent", "%") + "–" + regimeValue("regime_max_output_percent", "%"))))
        self._text("orientation_camera", f"CAM {round(orientation_camera, 1) % 360:05.1f}°" if orientation_camera is not None else "CAM —")
        self._refresh_navigation(motion, available=sample is not None and simulated,
                                 simulated=simulated, camera_heading=orientation_camera)
        self.battery_fill.style(f"width:{getattr(sample, 'battery_percent', None) or 0:.1f}%")
        wheels = sample.wheel_slip if sample else None
        red_at = int(self.slip_threshold.value)
        thrust = self.station.virtual_rover.wheel_thrust if simulated else None
        rpms = sample.wheel_rpm if sample else None
        self._text("wheel_panel_title", "WHEEL SLIP / THRUST" if simulated else "WHEEL SLIP / RPM")
        self.slip_view.set_content(wheel_slip_indicator(wheels, red_at, thrust, rpm=None if simulated else rpms))
        self._text("slip_threshold", f"RED AT {red_at}%" if red_at else "RED ABOVE 0%")
        currents = sample.motor_current_a if sample else None
        for i, fill in enumerate(self.wheel_fills):
            value = wheels[i] if wheels else None
            fill.style(f"width:{value * 100 if value is not None else 0:.1f}%")
            self._text(f"slip_{i}", f"{value * 100:.1f}%" if value is not None else "—")
            details = f"{rpms[i]:.1f} RPM" if rpms else "RPM unavailable"
            if currents:
                details += f" / {currents[i]:.2f} A"
            self.values[f"slip_{i}"].props(f'title="{escape(details)}"')
        poseAvailable = speed is not None and all(value is not None for value in orientation[:3])
        if poseAvailable:
            self.rover.update(motion if simulated else sample)
        self._update_rover_gimbal(sample, simulated=simulated)
        if simulated:
            self.rover.update_motion(motion)
        self._text("pose_position", f"X {motion.x_m:+.1f} m / Y {motion.y_m:+.1f} m" if simulated else "4WD / TEST MODEL")
        self._text("pose_status", "VIRTUAL ATTITUDE" if simulated and poseAvailable else "TELEMETRY DRIVEN" if poseAvailable else "LAST POSE / NO FRESH DATA")
        if self._last_history_count != state.received_count or self.values["history_label"].text != ("SPEED HISTORY" if sample else "HISTORY / NO FRESH DATA"):
            self.graph.set_content(sparkline(manager.history, state.connected))
            self._last_history_count = state.received_count
        self._text("history_label", "SPEED HISTORY" if sample else "HISTORY / NO FRESH DATA")
        camera = self.station.camera
        networkCamera = isinstance(getattr(camera, "device", None), str) and not camera.simulated
        self.rotation_button.set_visibility(networkCamera)
        frame = camera.latest_frame()
        camera_fresh = frame is not None and not camera.error and now - frame.captured_at < 2.0
        if simulated:
            distance = getattr(frame, "range_m", None) if camera_fresh else None
            self._text("overlay_range", range_readout(distance))
        else:
            distance = getattr(sample, "gimbal_lidar_distance_m", None)
            self._text("overlay_range", range_readout(distance, max_distance=None))
        self.camera_empty.set_visibility(not camera_fresh)
        if not camera_fresh:
            self.camera_empty.set_text(camera.error or "Waiting for camera frames…")
        if frame and frame.sequence != self._last_camera:
            query = urlencode({"sequence": frame.sequence,
                               "sensitivity": int(self.edge_sensitivity.value), "opacity": int(self.edge_opacity.value),
                               "vision_strength": int(self.vision_strength.value), "rotation": self.cameraRotation if networkCamera else 0,
                               **{name: str(control.value).lower() for name, control in self.filter_switches.items()}})
            self.camera_image.props(f'src="/api/camera/frame?{query}"')
            self._last_camera = frame.sequence
            self._text("camera_resolution", f"{frame.width} × {frame.height}")
        show_horizon = self.filter_horizon.value and camera_fresh and camera_pitch is not None and cameraRoll is not None
        self.horizon.set_visibility(show_horizon)
        if show_horizon:
            attitude = (round(camera_pitch, 1), round(cameraRoll, 1))
            if attitude != self._last_horizon:
                self.horizon.set_content(horizon_overlay(*attitude))
                self._last_horizon = attitude
        self._text("camera_time", datetime.now().strftime("%H:%M:%S") if camera_fresh else "NO SIGNAL")
        self._text("camera_mode", "SIMULATED CAMERA" if camera.simulated else camera.name.upper() if camera_fresh else "CAMERA OFFLINE")
        self._text("camera_status", f"{camera.name.upper()} / {camera.status.upper()}")
        controller = self.station.controller
        control = controller.state
        self._text("controller", "CONNECTED" if control.connected else "DISABLED" if controller.__class__.__name__ == "NoController" else "WAITING")
        for key, stick in (("left_stick", control.left_stick), ("right_stick", control.right_stick)):
            self._text(key, f"{'L' if key == 'left_stick' else 'R'}  {stick.x:+.2f} / {stick.y:+.2f}")
        command = self.station.drive_command
        latched = self.station.brake_latched
        self.brake_button.set_enabled(self.station.drive_input_enabled)
        self.brake_button.set_text("BRAKE ON" if latched else "BRAKE OFF")
        self.brake_button.props(f'aria-pressed="{str(latched).lower()}"')
        self._text("drive_command", "BRAKE" if command.brake and self.station.drive_input_enabled else f"Throttle {command.throttle:+.2f} / Turn {command.steering:+.2f}")
        if paused:
            driveHint = "Simulation paused"
        elif self.station.drive.mode == "keyboard":
            driveHint = "W/S drive · A/D steer · Space hold / B toggle brake"
        elif self.station.reverse_trigger_enabled:
            driveHint = "R2 forward · L2 reverse · Left stick steer · Options brake"
        else:
            driveHint = "R2 forward · L2 brake · Left stick steer · Options brake"
        self._text("drive_hint", driveHint)
        self.values["controller"].props(f'title="{escape(controller.status)}"')
        age = "" if state.age_seconds is None else f" / age {state.age_seconds:.1f}s"
        link_status = "radio open" if radio_open else "radio offline" if radio_bench else state.status.value
        self._text("footer", f"{state.source_name} / {link_status}{age}" + (f" / {state.error}" if state.error else ""))
        self._text("footer_camera", f"Camera: {'virtual' if camera.simulated else camera.name}  ·  Drive: {'radio bench' if radio_bench else self.station.drive.mode if simulated else 'monitor only'}")


def configure_dashboard(station: BaseStation, *, font_dir: str | None = None) -> None:
    """Register routes and a single global service timer before ui.run."""
    app.add_static_file(local_file=PING_ICON_PATH, url_path=PING_ICON_URL)
    font_css, has_suisse = register_fonts(font_dir)
    processor = CameraFrameProcessor()

    @app.get("/api/camera/frame")
    def camera_frame(view: Literal["normal", "contrast", "edges"] = "normal",
                     sensitivity: int = Query(50, ge=0, le=100), opacity: int = Query(65, ge=0, le=100),
                     denoise: bool = False, sharpen: bool = False, contrast: bool = False, edges: bool = False,
                     invert: bool = False, night_vision: bool = False, amber: bool = False,
                     white_phosphor: bool = False, thermal: bool = False, scanlines: bool = False,
                     vision_strength: int = Query(75, ge=0, le=100),
                     rotation: int = Query(0, ge=0, le=270, multiple_of=90)):
        frame = station.camera.latest_frame()
        if frame is None or station.camera.error or time.monotonic() - frame.captured_at >= 2.0:
            return Response(status_code=503, headers={"Cache-Control": "no-store"})
        settings = CameraFilterSettings(view=view, sensitivity=sensitivity, opacity=opacity, denoise=denoise,
                                        sharpen=sharpen, contrast=contrast, edges=edges, invert=invert,
                                        night_vision=night_vision, amber=amber, white_phosphor=white_phosphor,
                                        thermal=thermal, scanlines=scanlines, vision_strength=vision_strength, rotation=rotation)
        jpeg = processor.process(frame, settings)
        return Response(jpeg, media_type="image/jpeg", headers={"Cache-Control": "no-store", "X-Frame-Sequence": str(frame.sequence)})

    @app.get("/healthz")
    def health():
        state = station.telemetry.state
        return {"running": station.started, "telemetry": state.status.value,
                "source": state.source_name, "camera": station.camera.status,
                "controller_connected": station.controller.state.connected,
                "drive_mode": station.drive.mode, "speed_mps": station.virtual_rover.state.speed_mps,
                "stabilization": station.gimbal.stabilized, "stabilization_limited": station.gimbal.limited,
                "stabilization_mode": station.gimbal.stabilization_mode.value,
                "camera_heading_deg": (station.virtual_rover.state.heading_deg + station.gimbal.state.yaw_deg) % 360,
                "rover_heading_deg": station.virtual_rover.state.heading_deg,
                "camera_pitch_deg": station.virtual_rover.state.pitch_deg + station.gimbal.state.pitch_deg,
                "camera_roll_deg": station.virtual_rover.state.roll_deg + station.gimbal.state.roll_deg,
                "x_m": station.virtual_rover.state.x_m, "y_m": station.virtual_rover.state.y_m}

    @ui.page("/")
    def index():
        Dashboard(station, font_css=font_css, has_suisse=has_suisse)

    app.on_startup(station.start)
    app.on_shutdown(station.close)
    app.timer(0.01, station.tick)
