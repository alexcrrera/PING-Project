"""NiceGUI presentation. Receives services; never owns device connections."""

from __future__ import annotations

from datetime import datetime
from html import escape
import math
import time
from typing import Literal
from urllib.parse import urlencode

from fastapi import Query, Response
from nicegui import app, context, ui

from .fonts import register_fonts
from .camera_filters import CameraFilterSettings, CameraFrameProcessor, FILTER_LABELS, VISION_EFFECTS
from .gimbal import StabilizationMode
from .hud import TACTICAL_RETICLE, heading_tape, range_readout
from .keyboard import KEYBOARD_SCRIPT
from .navigation import MAP_ZOOM_LEVELS, campus_map, simulated_position
from .orientation import heading_indicator, pitch_indicator, roll_indicator
from .rover import RoverView
from .station import BaseStation
from .telemetry import SerialTelemetrySource, SimulatedTelemetrySource
from .theme import CSS


ICONS = {
    "camera": '<rect x="3" y="5" width="18" height="14" rx="1"/><circle cx="12" cy="12" r="4"/>',
    "rover": '<path d="m3 8 9-5 9 5v9l-9 5-9-5zM3 8l9 5 9-5M12 13v9"/>',
    "telemetry": '<path d="M3 13h4l3-8 4 15 3-9h4"/>',
}
CAMERA_ZOOM_LEVELS = (1, 2, 4)
STABILIZATION_LABELS = {
    StabilizationMode.OFF: ("OFF", "Follows rover tilt and turns"),
    StabilizationMode.LOCK: ("LOCK", "Heading + pitch locked · Roll level"),
    StabilizationMode.FOLLOW: ("FOLLOW", "Pitch locked · Roll level · Turns with rover"),
}
STABILIZATION_HINT = "Z: Off → Lock → Follow"


def _icon(name: str) -> str:
    return f'<svg width="20" height="20" viewBox="0 0 24 26" fill="none" stroke="currentColor" stroke-width="1.1">{ICONS[name]}</svg>'


def sparkline(history, fresh: bool) -> str:
    """Only validated numbers enter this SVG; values are historical by design."""
    values = [sample.speed_mps for sample in history][-300:]
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
        self.reticle_visible = True
        self._resetting_filters = False
        self._last_horizon: tuple[float, float] | None = None
        self._last_orientation: tuple | None = None
        self._last_heading: float | None = None
        self._last_navigation: tuple | None = None
        self._navigation_trail: list[tuple[float, float]] = []
        self.map_expanded = False
        self.map_zoom_index = MAP_ZOOM_LEVELS.index(1)
        self.map_zoom_controls = []
        self._map_toggle_sequence = station.map_toggle_sequence
        self.camera_zoom_index = 0
        ui.colors(primary="#d2d6b9", secondary="#999b91", accent="#d2d6b9")
        ui.add_css(font_css + "\n" + CSS)
        self._settings()
        self._build()
        self.input_guard = ui.element("div").props('id="virtual-drive-input" data-mode="keyboard" data-enabled="false"').style("display:none")
        ui.on("virtual_drive", self._drive_event)
        ui.on("camera_zoom", self.cycle_camera_zoom)
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
                ui.label("PING").classes("brand-word")
                ui.element("div").classes("brand-divider")
                ui.html("GROUND SYSTEMS<br>ROVER / 01", sanitize=False).classes("eyebrow")
            with ui.element("div").classes("top-meta"):
                self._label("session", "", "session")
                self._label("mode", "VIRTUAL TELEMETRY", "status-chip")
        with ui.element("div").classes("shell"):
            with ui.element("nav").classes("rail").props('aria-label="Dashboard sections"'):
                for name, target in (("camera", "vision"), ("rover", "attitude"), ("telemetry", "telemetry")):
                    with ui.element("a").props(f'href="#{target}" aria-label="{target.title()}"').classes("active" if name == "camera" else ""):
                        ui.html(_icon(name), sanitize=False)
                    ui.tooltip(target.title())
                ui.button(icon="tune", on_click=self.open_settings).props('flat round aria-label="Connection settings"').classes("rail-settings").tooltip("Connections")
            with ui.element("main").classes("workspace"):
                with ui.element("div").classes("intro"):
                    with ui.element("div"):
                        ui.html("<h1>Rover operations</h1><p>Traction, stability &amp; terrain observation.</p>", sanitize=False)
                    with ui.element("div").classes("intro-right"):
                        self._label("rate", "VIRTUAL / 10 HZ", "small-meta")
                        self.pause_button = ui.button("Pause simulation", icon="pause", on_click=self.toggle_pause).props("flat dense")
                        ui.button("Connections", icon="tune", on_click=self.open_settings).props("outline dense")
                with ui.element("div").classes("layout"):
                    self._tools_sidebar()
                    with ui.element("div").classes("visuals"):
                        self._camera()
                        self._pose()
                    self._telemetry()
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
                    self.reticle_button = ui.button(icon="my_location", on_click=self.toggle_reticle).props('flat dense aria-label="Toggle crosshair"').tooltip("Crosshair")
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
                self.crosshair = ui.html(TACTICAL_RETICLE, sanitize=False).classes("crosshair")
                with ui.element("div").classes("rangefinder-overlay").props('role="status" aria-label="Camera center rangefinder"'):
                    self._label("rangefinder_mode", "LRF / SIM · 10 M", "rangefinder-label")
                    self._label("overlay_range", "---- m", "rangefinder-value")
                self.horizon = ui.html("", sanitize=False).classes("artificial-horizon")
                self.horizon.set_visibility(False)
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
                    self._label("camera_zoom", "1× · Q ZOOM", "eyebrow")
                self.camera_empty = ui.label("Starting camera…").classes("camera-empty")
                self._expanded_map()
            with ui.element("div").classes("camera-footer"):
                self._label("camera_status", "VIRTUAL TERRAIN / TEST SOURCE")
                self._label("gimbal_hint", "I/K TILT · J/L PAN · R HOME")

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
                    ui.label(STABILIZATION_HINT).classes("subtext")
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
                self._label("pose_position", "X +0.0 m / Y +0.0 m")

    def _metric(self, key: str, name: str, unit: str) -> None:
        with ui.element("div").classes("metric-row"):
            ui.label(name).classes("metric-name")
            with ui.element("div").classes("flex items-baseline"):
                self._label(key, "—", "value")
                ui.label(unit).classes("unit")

    def _telemetry(self) -> None:
        with ui.element("aside").classes("panel telemetry").props('id="telemetry" aria-label="Robot telemetry"'):
            with ui.element("div").classes("panel-head"):
                ui.label("TELEMETRY").classes("panel-title")
                self._label("link", "WAITING", "small-meta")
            with ui.element("div").classes("telemetry-section"):
                with ui.element("div").classes("speed-header"):
                    ui.label("GROUND SPEED").classes("eyebrow")
                    ui.label("m/s").classes("small-meta")
                self._label("speed", "—", "speed-value")
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
            with ui.element("div").classes("telemetry-section").style("border-bottom:0"):
                ui.label("VIRTUAL DRIVE").classes("eyebrow")
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
                self._label("drive_hint", "WASD / arrows · Space brake", "control-hint")

    def _settings(self) -> None:
        with ui.dialog() as self.dialog, ui.card().classes("settings-card"):
            ui.label("CONNECTIONS").classes("eyebrow")
            ui.html("<h2>Telemetry source</h2>", sanitize=False)
            ui.label("Switch receivers while keeping the same dashboard. USB mode starts waiting for a valid packet.").classes("dialog-note")
            self.source_select = ui.select({"simulation": "Virtual robot", "serial": "USB / serial"}, value="simulation", label="Source").props("outlined dense")
            self.port_input = ui.input("Serial port", placeholder="COM3 or /dev/ttyUSB0").props("outlined dense")
            self.baud_input = ui.number("Baud rate", value=57600, min=1, precision=0).props("outlined dense")
            self.port_hint = ui.label("").classes("dialog-note")
            ui.button("Scan USB ports", icon="refresh", on_click=self.scan_ports).props("flat dense")
            ui.label("Serial input uses the provisional JSON-lines contract in the project documentation. Camera selection and PS4 input are configured at startup.").classes("dialog-note")
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
        source = self.station.telemetry.source
        self.source_select.set_value("simulation" if isinstance(source, SimulatedTelemetrySource) else "serial")
        if isinstance(source, SerialTelemetrySource):
            self.port_input.set_value(source.port)
            self.baud_input.set_value(source.baudrate)
        self.dialog.open()
        self.scan_ports()

    def apply_source(self) -> None:
        if self.source_select.value == "serial":
            port = (self.port_input.value or "").strip()
            baud = self.baud_input.value
            if not port or baud is None or baud <= 0 or baud != int(baud):
                ui.notify("Enter a serial port and a positive whole-number baud rate.")
                return
            source = SerialTelemetrySource(port, baudrate=int(baud))
        else:
            source = SimulatedTelemetrySource()
        self.station.replace_telemetry(source)
        self._last_history_count = -1
        self.dialog.close()
        self.refresh()

    def toggle_pause(self) -> None:
        source = self.station.telemetry.source
        if isinstance(source, SimulatedTelemetrySource):
            self.station.stop_drive()
            source.paused = not source.paused
            self.refresh()

    def _drive_event(self, event) -> None:
        payload = event.args
        if not isinstance(payload, dict):
            return
        if payload.get("release") is True:
            self.station.drive.clear(self.client.id)
        elif self.station.virtual_driving:
            self.station.drive.keyboard(self.client.id, payload.get("throttle", 0),
                                        payload.get("steering", 0), payload.get("brake", False))

    def toggle_reticle(self) -> None:
        self.reticle_visible = not self.reticle_visible
        self.crosshair.set_visibility(self.reticle_visible)

    def cycle_camera_zoom(self) -> None:
        self.camera_zoom_index = (self.camera_zoom_index + 1) % len(CAMERA_ZOOM_LEVELS)
        zoom = CAMERA_ZOOM_LEVELS[self.camera_zoom_index]
        self.camera_image.style(f"transform:scale({zoom})")
        self._text("camera_zoom", f"{zoom}× · Q ZOOM")

    @property
    def gimbal_available(self) -> bool:
        return hasattr(self.station.camera, "set_gimbal")

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
        if self.gimbal_available:
            self.station.gimbal.nudge(yaw=yaw, pitch=pitch)
            self.refresh()

    def reset_gimbal(self) -> None:
        if self.gimbal_available:
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
        simulated = isinstance(source, SimulatedTelemetrySource)
        paused = simulated and source.paused
        now = time.monotonic()
        sequence = self.station.map_toggle_sequence
        if sequence != self._map_toggle_sequence:
            if (sequence - self._map_toggle_sequence) % 2:
                self._set_map_expanded(not self.map_expanded)
            self._map_toggle_sequence = sequence
        self.input_guard.props(f'data-mode="{self.station.drive.mode}" data-enabled="{str(self.station.virtual_driving).lower()}" data-gimbal="{str(self.gimbal_available).lower()}" data-map-open="{str(self.map_expanded).lower()}"')
        self.gimbal_controls.set_visibility(self.gimbal_available)
        self._text("gimbal_hint", "I/K TILT · J/L PAN · R HOME" if self.gimbal_available else "FORWARD VIEW")
        gimbal = self.station.gimbal.state
        mode = self.station.gimbal.stabilization_mode if self.gimbal_available else StabilizationMode.OFF
        label, detail = STABILIZATION_LABELS[mode]
        enabled = mode is not StabilizationMode.OFF
        limited = enabled and self.station.gimbal.limited
        self.stabilization_marker.set_text(f"STAB {label}" + (" · LIMIT" if limited else " · Z"))
        self.stabilization_button.set_text(f"{label} · Z")
        for control in (self.stabilization_marker, self.stabilization_button):
            control.set_enabled(self.gimbal_available)
            control.props(f'aria-label="Camera stabilization: {label.title()}. Cycle mode (Z)" title="{detail}. {STABILIZATION_HINT}"')
            control.classes(add="stabilization-on" if enabled else "stabilization-off", remove="stabilization-off" if enabled else "stabilization-on")
        self._text("stabilization_detail", "Available with virtual camera" if not self.gimbal_available else
                   detail + (" · Compensation limit reached" if limited else ""))
        self._text("gimbal_angles", f"PAN {gimbal.yaw_deg:+.0f}° / TILT {gimbal.pitch_deg:+.0f}°")
        self.rover.update_gimbal(gimbal)
        if self.drive_toggle.value != self.station.drive.mode:
            self.drive_toggle.set_value(self.station.drive.mode)
        self.drive_toggle.set_enabled(simulated and not paused)
        self._text("session", f"LOCAL STATION  /  {datetime.now():%H:%M:%S}")
        self._text("mode", "VIRTUAL TELEMETRY" if simulated else "USB TELEMETRY")
        self._text("rate", "PAUSED / VIRTUAL" if paused else "VIRTUAL / 10 HZ" if simulated else "USB / RECEIVE ONLY")
        self.pause_button.set_visibility(simulated)
        self.pause_button.set_text("Resume simulation" if paused else "Pause simulation")
        self.pause_button.props(f"icon={'play_arrow' if paused else 'pause'}")
        self._text("link", state.status.value.upper())
        self.values["link"].style(f"color:{'var(--accent)' if state.connected else 'var(--warn)'}")
        self._text("age", f"{state.age_seconds * 1000:.0f}" if state.age_seconds is not None else "—")
        self._text("packet_count", f"{state.received_count:,} VALID / {state.rejected_count:,} REJECTED")
        fields = {"speed": ("speed_mps", ".2f"), "battery": ("battery_percent", ".0f"),
                  "voltage": ("battery_voltage", ".1f"), "temperature": ("motor_temp_c", ".1f"),
                  "distance": ("distance_m", ".1f"), "rssi": ("signal_rssi_dbm", ".0f"), "latency": ("latency_ms", ".0f")}
        for key, (attr, fmt) in fields.items():
            self._text(key, format(getattr(sample, attr), fmt) if sample else "—")
        motion = self.station.virtual_rover.state
        vehicle_attitude = (motion if simulated else sample) if sample else None
        for key in ("pitch", "roll", "heading"):
            value = getattr(vehicle_attitude, key + "_deg") if vehicle_attitude else None
            text = f"{value:+.1f}°" if value is not None and key != "heading" else f"{round(value, 1) % 360:05.1f}°" if value is not None else "—"
            self._text(key, text)
        self._text("overlay_speed", f"{sample.speed_mps:.2f}" if sample else "—")
        camera_attitude = self.station.virtual_rover.state if self.gimbal_available else sample
        camera_heading = (camera_attitude.heading_deg + (gimbal.yaw_deg if self.gimbal_available else 0)) % 360 if sample else 0
        camera_pitch = camera_attitude.pitch_deg + (gimbal.pitch_deg if self.gimbal_available else 0) if sample else 0
        self._text("overlay_heading", f"{round(camera_heading, 1) % 360:05.1f}°" if sample else "—")
        self._text("overlay_pitch", f"{camera_pitch:+.1f}°" if sample else "—")
        heading = round(camera_heading, 1) % 360 if sample else None
        if heading != self._last_heading:
            self.compass.set_content(heading_tape(heading))
            self._last_heading = heading
        # A USB rover and the virtual camera have independent poses. Only show
        # their bearings together when both belong to the shared simulation.
        orientation_camera = camera_heading if sample and simulated and self.gimbal_available else None
        orientation = tuple(round(getattr(vehicle_attitude, axis + "_deg"), 1) if vehicle_attitude else None
                            for axis in ("pitch", "roll", "heading")) + (
                                round(orientation_camera, 1) if orientation_camera is not None else None,)
        if orientation != self._last_orientation:
            pitch, roll, heading, bearing = orientation
            self.orientation_views["pitch"].set_content(pitch_indicator(pitch))
            self.orientation_views["roll"].set_content(roll_indicator(roll))
            self.orientation_views["heading"].set_content(heading_indicator(heading, bearing))
            self._last_orientation = orientation
        self._text("orientation_camera", f"CAM {round(orientation_camera, 1) % 360:05.1f}°" if orientation_camera is not None else "CAM —")
        self._refresh_navigation(motion, available=sample is not None and simulated,
                                 simulated=simulated, camera_heading=orientation_camera)
        self.battery_fill.style(f"width:{sample.battery_percent if sample else 0:.1f}%")
        wheels = sample.wheel_slip if sample else None
        rpms = sample.wheel_rpm if sample else None
        currents = sample.motor_current_a if sample else None
        for i, fill in enumerate(self.wheel_fills):
            value = wheels[i] if wheels else None
            fill.style(f"width:{value * 100 if value is not None else 0:.1f}%")
            self._text(f"slip_{i}", f"{value * 100:.1f}%" if value is not None else "—")
            details = f"{rpms[i]:.1f} RPM" if rpms else "RPM unavailable"
            if currents:
                details += f" / {currents[i]:.2f} A"
            self.values[f"slip_{i}"].props(f'title="{escape(details)}"')
        if sample:
            self.rover.update(motion if simulated else sample)
        if simulated:
            self.rover.update_motion(motion)
        self._text("pose_position", f"X {motion.x_m:+.1f} m / Y {motion.y_m:+.1f} m" if simulated else "4WD / TEST MODEL")
        self._text("pose_status", "VIRTUAL ATTITUDE" if simulated and sample else "TELEMETRY DRIVEN" if sample else "LAST POSE / NO FRESH DATA")
        if self._last_history_count != state.received_count or self.values["history_label"].text != ("SPEED HISTORY" if sample else "HISTORY / NO FRESH DATA"):
            self.graph.set_content(sparkline(manager.history, state.connected))
            self._last_history_count = state.received_count
        self._text("history_label", "SPEED HISTORY" if sample else "HISTORY / NO FRESH DATA")
        camera = self.station.camera
        frame = camera.latest_frame()
        camera_fresh = frame is not None and not camera.error and now - frame.captured_at < 2.0
        self._text("overlay_range", range_readout(getattr(frame, "range_m", None) if camera_fresh else None))
        self._text("rangefinder_mode", "LRF / SIM · 10 M" if camera.simulated else "LRF · 10 M")
        self.camera_empty.set_visibility(not camera_fresh)
        if not camera_fresh:
            self.camera_empty.set_text(camera.error or "Waiting for camera frames…")
        if frame and frame.sequence != self._last_camera:
            query = urlencode({"sequence": frame.sequence,
                               "sensitivity": int(self.edge_sensitivity.value), "opacity": int(self.edge_opacity.value),
                               "vision_strength": int(self.vision_strength.value),
                               **{name: str(control.value).lower() for name, control in self.filter_switches.items()}})
            self.camera_image.props(f'src="/api/camera/frame?{query}"')
            self._last_camera = frame.sequence
            self._text("camera_resolution", f"{frame.width} × {frame.height}")
        show_horizon = self.filter_horizon.value and sample is not None and camera_fresh
        self.horizon.set_visibility(show_horizon)
        if show_horizon:
            roll = camera_attitude.roll_deg + (gimbal.roll_deg if self.gimbal_available else 0)
            attitude = (round(camera_pitch, 1), round(roll, 1))
            if attitude != self._last_horizon:
                self.horizon.set_content(horizon_overlay(*attitude))
                self._last_horizon = attitude
        self._text("camera_time", datetime.now().strftime("%H:%M:%S") if camera_fresh else "NO SIGNAL")
        self._text("camera_mode", "SIMULATED CAMERA" if camera.simulated else "USB CAMERA" if camera_fresh else "CAMERA OFFLINE")
        self._text("camera_status", f"{camera.name.upper()} / {camera.status.upper()}")
        controller = self.station.controller
        control = controller.state
        self._text("controller", "CONNECTED" if control.connected else "DISABLED" if controller.__class__.__name__ == "NoController" else "WAITING")
        for key, stick in (("left_stick", control.left_stick), ("right_stick", control.right_stick)):
            self._text(key, f"{'L' if key == 'left_stick' else 'R'}  {stick.x:+.2f} / {stick.y:+.2f}")
        command = self.station.drive_command
        self._text("drive_command", "BRAKE" if command.brake and self.station.virtual_driving else f"Throttle {command.throttle:+.2f} / Turn {command.steering:+.2f}")
        self._text("drive_hint", "USB telemetry / virtual drive unavailable" if not simulated else "Simulation paused" if paused else "WASD / arrows · Space brake" if self.station.drive.mode == "keyboard" else "Left stick: drive / steer · × or L2: brake")
        self.values["controller"].props(f'title="{escape(controller.status)}"')
        age = "" if state.age_seconds is None else f" / age {state.age_seconds:.1f}s"
        self._text("footer", f"{state.source_name} / {state.status.value}{age}" + (f" / {state.error}" if state.error else ""))
        self._text("footer_camera", f"Camera: {'virtual' if camera.simulated else 'USB'}  ·  Drive: {self.station.drive.mode if simulated else 'monitor only'}")


def configure_dashboard(station: BaseStation, *, font_dir: str | None = None) -> None:
    """Register routes and a single global service timer before ui.run."""
    font_css, has_suisse = register_fonts(font_dir)
    processor = CameraFrameProcessor()

    @app.get("/api/camera/frame")
    def camera_frame(view: Literal["normal", "contrast", "edges"] = "normal",
                     sensitivity: int = Query(50, ge=0, le=100), opacity: int = Query(65, ge=0, le=100),
                     denoise: bool = False, sharpen: bool = False, contrast: bool = False, edges: bool = False,
                     invert: bool = False, night_vision: bool = False, amber: bool = False,
                     white_phosphor: bool = False, thermal: bool = False, scanlines: bool = False,
                     vision_strength: int = Query(75, ge=0, le=100)):
        frame = station.camera.latest_frame()
        if frame is None or station.camera.error or time.monotonic() - frame.captured_at >= 2.0:
            return Response(status_code=503, headers={"Cache-Control": "no-store"})
        settings = CameraFilterSettings(view=view, sensitivity=sensitivity, opacity=opacity, denoise=denoise,
                                        sharpen=sharpen, contrast=contrast, edges=edges, invert=invert,
                                        night_vision=night_vision, amber=amber, white_phosphor=white_phosphor,
                                        thermal=thermal, scanlines=scanlines, vision_strength=vision_strength)
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
    app.timer(1 / 30, station.tick)
