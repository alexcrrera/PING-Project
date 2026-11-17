"""Dashboard composition root; diagnostic viewer remains a separate entrypoint."""

from __future__ import annotations

import argparse
import base64
from io import BytesIO
import math


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="PINGUIN rover ground station")
    result.add_argument("--host", default="127.0.0.1", help="listen address, default local computer only")
    result.add_argument("--port", type=int, default=8080, help="dashboard port (default 8080)")
    result.add_argument("--no-browser", action="store_true", help="do not open the dashboard automatically")
    result.add_argument("--simulation", action="store_true", help="start with simulated telemetry")
    result.add_argument("--serial-port", help="receive real USB telemetry instead of simulation, e.g. COM3")
    result.add_argument("--baud", type=int, default=57600, help="USB telemetry baud rate (default 57600)")
    result.add_argument("--camera", help="OpenCV camera index or stream URL; default virtual terrain camera")
    result.add_argument("--controller", action="store_true", help="monitor a real PS4 controller with the existing SDL adapter")
    result.add_argument("--device-index", type=int, help="explicit SDL gamepad index when monitoring a controller")
    result.add_argument("--deadzone", type=float, default=.10, help="radial controller deadzone")
    result.add_argument("--font-dir", help="folder containing local Suisse Intl Light and Medium font files")
    result.add_argument("--seed", type=int, default=7, help="repeatable simulated telemetry seed")
    return result


def faviconDataUrl(path) -> str:
    """Embed the current icon so browsers do not reuse an outdated favicon."""
    from PIL import Image

    with Image.open(path) as icon:
        icon.thumbnail((64, 64), Image.Resampling.LANCZOS)
        buffer = BytesIO()
        icon.save(buffer, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")


def main(argv: list[str] | None = None) -> int:
    import sys
    arguments = list(sys.argv[1:] if argv is None else argv)
    # Preserve the original hardware diagnostics, including its keyboard demo.
    if "--controller-viewer" in arguments or "--list-devices" in arguments:
        from .app import main as diagnostics
        return diagnostics([arg for arg in arguments if arg != "--controller-viewer"])
    command = parser()
    args = command.parse_args(arguments)
    if not 1 <= args.port <= 65535:
        command.error("--port must be between 1 and 65535")
    if args.baud <= 0:
        command.error("--baud must be positive")
    if args.serial_port is not None and not args.serial_port.strip():
        command.error("--serial-port must name a port, e.g. COM3")
    if not math.isfinite(args.deadzone) or not 0 <= args.deadzone < 1:
        command.error("--deadzone must be in [0, 1)")
    if args.device_index is not None and args.device_index < 0:
        command.error("--device-index must be nonnegative")
    if args.device_index is not None and not args.controller:
        command.error("--device-index requires --controller")

    from nicegui import ui
    from .camera import OpenCVCameraSource, SimulatedCameraSource
    from .dashboard import PING_ICON_PATH, configure_dashboard
    from .preferences import loadPort
    from .station import BaseStation, PS4ControllerService
    from .telemetry import SerialTelemetrySource, SimulatedTelemetrySource, TelemetryManager

    source = SimulatedTelemetrySource(seed=args.seed) if args.simulation and not args.serial_port else SerialTelemetrySource(args.serial_port or loadPort(), baudrate=args.baud)
    camera_device = int(args.camera) if args.camera and args.camera.isdecimal() else args.camera
    camera = OpenCVCameraSource(camera_device) if args.camera is not None else SimulatedCameraSource()
    controller = PS4ControllerService(args.device_index, args.deadzone) if args.controller else None
    station = BaseStation(TelemetryManager(source), camera, controller)
    configure_dashboard(station, font_dir=args.font_dir)
    # SDL and service lifecycles remain on one process's main event-loop thread.
    ui.run(host=args.host, port=args.port, reload=False, native=False, show=not args.no_browser,
           title="PINGUIN | Rover operations", dark=True, favicon=faviconDataUrl(PING_ICON_PATH), show_welcome_message=False,
           binding_refresh_interval=.1, reconnect_timeout=5.0)
    return 0
