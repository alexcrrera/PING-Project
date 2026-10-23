"""NiceGUI presentation. Receives services; never owns device connections."""

from __future__ import annotations

from datetime import datetime
from html import escape
import time

from fastapi import Response
from nicegui import app, context, ui

from .fonts import register_fonts
from .keyboard import KEYBOARD_SCRIPT
from .rover import RoverView
from .station import BaseStation
from .telemetry import SerialTelemetrySource, SimulatedTelemetrySource
from .theme import CSS


RETICLE = '''<svg viewBox="0 0 64 64" fill="none" aria-hidden="true">
<path d="M32 3v17M32 44v17M3 32h17M44 32h17" stroke="#eeeee4" stroke-width="1"/>
<circle cx="32" cy="32" r="2" stroke="#eeeee4" stroke-width="1"/>
</svg>'''
COMPASS = '''<svg viewBox="0 0 260 34" fill="none" aria-hidden="true">
<path d="M0 12h260M0 12v7m26-7v5m26-5v5m26-5v5m26-5v7m26-7v9m26-9v7m26-7v5m26-5v5m26-5v5m26-5v7" stroke="#e2e4d6" stroke-width=".65"/>
<path d="m127 4 3 4 3-4" stroke="#e2e4d6"/>
<text x="130" y="33" fill="#e2e4d6" font-size="8" text-anchor="middle" font-family="Suisse,Arial" letter-spacing="2">HEADING</text>
</svg>'''
ICONS = {
    "camera": '<rect x="3" y="5" width="18" height="14" rx="1"/><circle cx="12" cy="12" r="4"/>',
    "rover": '<path d="m3 8 9-5 9 5v9l-9 5-9-5zM3 8l9 5 9-5M12 13v9"/>',
    "telemetry": '<path d="M3 13h4l3-8 4 15 3-9h4"/>',
}


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


class Dashboard:
    def __init__(self, station: BaseStation, *, font_css: str = "", has_suisse: bool = True):
        self.station = station
        self.client = context.client
        self.has_suisse = has_suisse
        self.values = {}
        self._last_camera = -1
        self._last_history_count = -1
        self.reticle_visible = True
        ui.colors(primary="#d2d6b9", secondary="#999b91", accent="#d2d6b9")
        ui.add_css(font_css + "\n" + CSS)
        self._settings()
        self._build()
        self.input_guard = ui.element("div").props('id="virtual-drive-input" data-mode="keyboard" data-enabled="false"').style("display:none")
        ui.on("virtual_drive", self._drive_event)
        self.client.on_disconnect(lambda: self.station.drive.clear(self.client.id))
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
                    self._label("camera_time", "", "camera-stamp")
                ui.html(COMPASS, sanitize=False).classes("camera-compass")
                self.crosshair = ui.html(RETICLE, sanitize=False).classes("crosshair")
                with ui.element("div").classes("camera-bottom"):
                    with ui.element("div").classes("camera-readings"):
                        for key, name in (("overlay_speed", "SPEED / M·S⁻¹"), ("overlay_heading", "HEADING / DEG"), ("overlay_pitch", "PITCH / DEG")):
                            with ui.element("div"):
                                ui.label(name).classes("eyebrow")
                                self._label(key, "—", "overlay-value")
                    ui.label("CAM / 01").classes("eyebrow")
                self.camera_empty = ui.label("Starting camera…").classes("camera-empty")
            with ui.element("div").classes("camera-footer"):
                self._label("camera_status", "VIRTUAL TERRAIN / TEST SOURCE")
                ui.label("FORWARD VIEW")

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
                with ui.element("div").classes("pose-values"):
                    for key, name in (("pitch", "PITCH"), ("roll", "ROLL"), ("heading", "HEADING")):
                        with ui.element("div"):
                            ui.label(name).classes("eyebrow")
                            self._label(key, "—", "pose-number")
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

    def refresh(self) -> None:
        manager = self.station.telemetry
        state = manager.state
        sample = state.sample
        source = manager.source
        simulated = isinstance(source, SimulatedTelemetrySource)
        paused = simulated and source.paused
        now = time.monotonic()
        self.input_guard.props(f'data-mode="{self.station.drive.mode}" data-enabled="{str(self.station.virtual_driving).lower()}"')
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
        for key in ("pitch", "roll", "heading"):
            value = getattr(sample, key + "_deg") if sample else None
            text = f"{value:+.1f}°" if value is not None and key != "heading" else f"{value:05.1f}°" if value is not None else "—"
            self._text(key, text)
        self._text("overlay_speed", f"{sample.speed_mps:.2f}" if sample else "—")
        self._text("overlay_heading", f"{sample.heading_deg:05.1f}°" if sample else "—")
        self._text("overlay_pitch", f"{sample.pitch_deg:+.1f}°" if sample else "—")
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
        motion = self.station.virtual_rover.state
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
        self.camera_empty.set_visibility(not camera_fresh)
        if not camera_fresh:
            self.camera_empty.set_text(camera.error or "Waiting for camera frames…")
        if frame and frame.sequence != self._last_camera:
            self.camera_image.props(f'src="/api/camera/frame?sequence={frame.sequence}"')
            self._last_camera = frame.sequence
            self._text("camera_resolution", f"{frame.width} × {frame.height}")
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

    @app.get("/api/camera/frame")
    def camera_frame():
        frame = station.camera.latest_frame()
        if frame is None or station.camera.error or time.monotonic() - frame.captured_at >= 2.0:
            return Response(status_code=503, headers={"Cache-Control": "no-store"})
        return Response(frame.jpeg, media_type="image/jpeg", headers={"Cache-Control": "no-store", "X-Frame-Sequence": str(frame.sequence)})

    @app.get("/healthz")
    def health():
        state = station.telemetry.state
        return {"running": station.started, "telemetry": state.status.value,
                "source": state.source_name, "camera": station.camera.status,
                "controller_connected": station.controller.state.connected,
                "drive_mode": station.drive.mode, "speed_mps": station.virtual_rover.state.speed_mps,
                "x_m": station.virtual_rover.state.x_m, "y_m": station.virtual_rover.state.y_m}

    @ui.page("/")
    def index():
        Dashboard(station, font_css=font_css, has_suisse=has_suisse)

    app.on_startup(station.start)
    app.on_shutdown(station.close)
    app.timer(1 / 30, station.tick)
