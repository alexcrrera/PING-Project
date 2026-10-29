"""Application services. Hardware ownership is independent of browser pages."""

from __future__ import annotations

import os
import time
from typing import Protocol

from .controller import Button, ControllerState, PS4Controller
from .drive import DriveCommand, DriveInputRouter
from .gimbal import VirtualGimbal
from .motion import VirtualRover
from .telemetry import SimulatedTelemetrySource, TelemetryManager


class ControllerService(Protocol):
    state: ControllerState
    status: str

    def start(self) -> None: ...
    def update(self) -> ControllerState: ...
    def close(self) -> None: ...


class NoController:
    """Explicitly disabled input, rather than a simulated hardware connection."""

    state = ControllerState()
    status = "Input disabled / start with --controller"

    def start(self) -> None:
        pass

    def update(self) -> ControllerState:
        return self.state

    def close(self) -> None:
        pass


class PS4ControllerService:
    """Own SDL on the server main thread, including startup and shutdown.

    The hidden SDL window allows the existing adapter to pump device events
    while the browser has focus. Snapshots may drive the virtual rover; this
    service has no physical command transport.
    """

    def __init__(self, device_index: int | None = None, deadzone: float = 0.10):
        self.model = PS4Controller(deadzone)
        self.device_index = device_index
        self.state = self.model.state
        self.status = "Waiting for PS4 controller"
        self.source = None
        self._pygame = None

    def start(self) -> None:
        if self._pygame is not None:
            return
        os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
        os.environ.setdefault("SDL_JOYSTICK_ALLOW_BACKGROUND_EVENTS", "1")
        import pygame
        from .inputs import PygamePS4Input

        self._pygame = pygame
        try:
            pygame.display.init()
            pygame.display.set_mode((1, 1), pygame.HIDDEN)
            pygame.joystick.init()
            self.source = PygamePS4Input(self.device_index)
            self.update()
        except pygame.error as exc:
            self.status = f"Controller unavailable: {exc}"
            self.close()

    def update(self) -> ControllerState:
        if self.source is not None:
            self.state = self.model.update(self.source.read(self._pygame.event.get()))
            self.status = self.source.status
        return self.state

    def close(self) -> None:
        if self.source is not None:
            self.source.close()
            self.source = None
        if self._pygame is not None:
            from pygame._sdl2 import controller as sdl
            sdl.quit()
            self._pygame.quit()
            self._pygame = None
        from .controller import RawInput
        self.state = self.model.update(RawInput())


class BaseStation:
    """One receiver and one camera shared by all dashboard clients.

    Call tick on the main thread. Rendering never polls devices, and opening
    another browser tab never opens a second serial/controller connection.
    """

    def __init__(self, telemetry: TelemetryManager, camera, controller: ControllerService | None = None,
                 *, virtual_rover: VirtualRover | None = None):
        self.telemetry = telemetry
        self.camera = camera
        self.controller = controller or NoController()
        self.virtual_rover = virtual_rover or VirtualRover()
        self.drive = DriveInputRouter()
        self.drive_command = DriveCommand()
        self.gimbal = VirtualGimbal()
        self.map_toggle_sequence = 0
        self._last_map_controller_update: tuple[str, int] | None = None
        self.started_at = time.monotonic()
        self.started = False
        self._closed = False
        self._bind_simulation()

    def _bind_simulation(self) -> None:
        source = getattr(self.telemetry, "source", None)
        if isinstance(source, SimulatedTelemetrySource):
            source.rover = self.virtual_rover

    @property
    def virtual_driving(self) -> bool:
        source = getattr(self.telemetry, "source", None)
        return isinstance(source, SimulatedTelemetrySource) and not source.paused

    def set_drive_mode(self, mode: str) -> None:
        self.stop_drive()
        self.drive.set_mode(mode)
        if mode == "dualshock" and isinstance(self.controller, NoController):
            self.controller = PS4ControllerService()
            if self.started:
                self.controller.start()

    def stop_drive(self) -> None:
        self.drive.clear()
        self.drive_command = DriveCommand(source=self.drive.mode)
        self.virtual_rover.stop()

    def toggle_stabilization(self) -> None:
        if hasattr(self.camera, "set_gimbal"):
            self.gimbal.cycle_stabilization()

    def replace_telemetry(self, source) -> None:
        self.stop_drive()
        self.telemetry.replace_source(source)
        self._bind_simulation()

    def start(self) -> None:
        if self._closed:
            raise RuntimeError("A closed BaseStation cannot restart; compose a new station")
        if self.started:
            return
        self.started = True
        self.started_at = time.monotonic()
        try:
            self.camera.start()
            self.controller.start()
        except Exception:
            self.close()
            raise

    def tick(self) -> None:
        if self.started:
            self.controller.update()
            control = self.controller.state
            controller_update = (control.device_id, control.sequence)
            if controller_update != self._last_map_controller_update:
                self._last_map_controller_update = controller_update
                if self.drive.mode == "dualshock" and control.connected and control.buttons[Button.TOUCHPAD].pressed:
                    self.map_toggle_sequence += 1
            self._bind_simulation()
            now = time.monotonic()
            self.drive_command = self.drive.command(self.controller.state, now=now) if self.virtual_driving else DriveCommand(source=self.drive.mode)
            self.virtual_rover.set_command(self.drive_command.throttle, self.drive_command.steering, self.drive_command.brake)
            motion = self.virtual_rover.advance(now)
            self.gimbal.update_attitude(motion.heading_deg, motion.pitch_deg, motion.roll_deg)
            gimbal_pose = self.gimbal.advance(now)
            if hasattr(self.camera, "set_view"):
                self.camera.set_view(motion, gimbal_pose)
            else:
                if hasattr(self.camera, "set_motion"):
                    self.camera.set_motion(motion)
                if hasattr(self.camera, "set_gimbal"):
                    self.camera.set_gimbal(gimbal_pose)
            self.telemetry.update()

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self.started = False
        self.stop_drive()
        self.gimbal.release()
        try:
            self.controller.close()
        finally:
            try:
                self.camera.close()
            finally:
                self.telemetry.close()
