"""Application services. Hardware ownership is independent of browser pages."""

from __future__ import annotations

import os
import time
from collections import deque
from typing import Protocol

from .controller import Button, ControllerState, PS4Controller
from .drive import DriveCommand, DriveInputRouter
from .gimbal import VirtualGimbal
from .motion import VirtualRover
from .telemetry import RadioBenchSource, SerialTelemetrySource, SimulatedTelemetrySource, TelemetryManager


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
    while the browser has focus. The station routes snapshots to the selected source.
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
        self._next_drive_send = 0.0
        self.brake_latched = False
        self.gimbal = VirtualGimbal()
        self._requested_gimbal_mode = None
        self._requested_gimbal_at = 0.0
        self.map_toggle_sequence = 0
        self.controller_actions = deque(maxlen=128)
        self.controller_action_sequence = 0
        self._last_map_controller_update: tuple[str, int] | None = None
        self.started_at = time.monotonic()
        self.started = False
        self._closed = False
        self._bind_simulation()

    def _bind_simulation(self) -> None:
        source = getattr(self.telemetry, "source", None)
        if isinstance(source, SimulatedTelemetrySource):
            source.rover = self.virtual_rover
        elif isinstance(source, RadioBenchSource):
            source.simulation.rover = self.virtual_rover

    @property
    def virtual_driving(self) -> bool:
        source = getattr(self.telemetry, "source", None)
        return ((isinstance(source, SimulatedTelemetrySource) and not source.paused)
                or isinstance(source, RadioBenchSource))

    @property
    def drive_input_enabled(self) -> bool:
        return self.virtual_driving or type(getattr(self.telemetry, "source", None)) is SerialTelemetrySource

    def set_drive_mode(self, mode: str) -> None:
        self.stop_drive()
        self.gimbal.release("dualshock")
        self.drive.set_mode(mode)
        if mode == "dualshock" and isinstance(self.controller, NoController):
            self.controller = PS4ControllerService()
            if self.started:
                self.controller.start()

    def stop_drive(self) -> None:
        self.drive.clear()
        self.drive_command = DriveCommand(source=self.drive.mode)
        self.virtual_rover.stop()
        source = getattr(self.telemetry, "source", None)
        if isinstance(source, RadioBenchSource):
            source.send_drive(0.0, 0.0, True, time.monotonic(), force=True)
        elif type(source) is SerialTelemetrySource and source.transport_connected:
            source.send_rover_command("DRIVE:+0.00,+0.00,1")
            source.send_rover_command("STICK:+0.00,+0.00")

    def toggle_brake(self) -> None:
        if self.drive_input_enabled:
            self.brake_latched = not self.brake_latched
            source = getattr(self.telemetry, "source", None)
            if type(source) is SerialTelemetrySource:
                source.send_rover_command("BUTTON:BRAKE")
            if self.brake_latched:
                self.drive_command = DriveCommand(source=self.drive.mode)
                self.virtual_rover.stop()

    @property
    def rover_gimbal_mode(self) -> int | None:
        source = getattr(self.telemetry, "source", None)
        if type(source) is not SerialTelemetrySource or not source.transport_connected:
            self._requested_gimbal_mode = None
            return None
        sample = self.telemetry.state.sample
        reported = getattr(sample, "gimbal_mode", None)
        if self._requested_gimbal_mode is not None:
            if reported == self._requested_gimbal_mode or time.monotonic() - self._requested_gimbal_at > 2.0:
                self._requested_gimbal_mode = None
            else:
                return self._requested_gimbal_mode
        return reported

    def set_rover_gimbal_mode(self, mode: int) -> bool:
        source = getattr(self.telemetry, "source", None)
        if type(source) is not SerialTelemetrySource or mode not in (0, 1, 2):
            return False
        if not source.send_gimbal_command(f"GIMBAL_MODE:{mode}"):
            return False
        self._requested_gimbal_mode = mode
        self._requested_gimbal_at = time.monotonic()
        return True

    def toggle_stabilization(self) -> None:
        source = getattr(self.telemetry, "source", None)
        if type(source) is SerialTelemetrySource:
            mode = self.rover_gimbal_mode
            if mode is not None:
                self.set_rover_gimbal_mode((mode + 1) % 3)
        elif hasattr(self.camera, "set_gimbal"):
            self.gimbal.cycle_stabilization()

    def replace_telemetry(self, source) -> None:
        self.stop_drive()
        self._requested_gimbal_mode = None
        self.telemetry.replace_source(source)
        self._bind_simulation()

    def replace_camera(self, camera) -> None:
        """Release the previous reader before opening the shared replacement."""
        if self._closed:
            raise RuntimeError("A closed BaseStation cannot change cameras")
        self.camera.close()
        self.camera = camera
        if self.started:
            self.camera.start()

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
                if self.drive.mode == "dualshock" and control.connected:
                    source = getattr(self.telemetry, "source", None)
                    if type(source) is SerialTelemetrySource:
                        for button in Button:
                            if button not in (Button.OPTIONS, Button.L2, Button.R2, Button.SHARE) and control.buttons[button].pressed:
                                source.send_rover_command(f"BUTTON:{button.name}")
                    if control.buttons[Button.TOUCHPAD].pressed:
                        self.map_toggle_sequence += 1
                    if control.buttons[Button.OPTIONS].pressed:
                        self.toggle_brake()
                    for button, action in ((Button.RIGHT, "camera_zoom_in"),
                                           (Button.R1, "camera_zoom_in"),
                                           (Button.LEFT, "camera_zoom_out"),
                                           (Button.L1, "camera_zoom_out"),
                                           (Button.TRIANGLE, "map_zoom")):
                        if control.buttons[button].pressed:
                            self.controller_action_sequence += 1
                            self.controller_actions.append((self.controller_action_sequence, action))
                    if control.buttons[Button.SHARE].pressed:
                        self.toggle_stabilization()
                    if hasattr(self.camera, "set_gimbal"):
                        if control.buttons[Button.CROSS].pressed:
                            self.gimbal.reset()
            self._bind_simulation()
            now = time.monotonic()
            self.drive_command = (self.drive.command(control, now=now)
                                  if self.drive_input_enabled and not self.brake_latched
                                  else DriveCommand(source=self.drive.mode))
            if self.virtual_driving:
                self.virtual_rover.set_command(self.drive_command.throttle, self.drive_command.steering, self.drive_command.brake)
            else:
                self.virtual_rover.stop()
            motion = self.virtual_rover.advance(now)
            self.gimbal.update_attitude(motion.heading_deg, motion.pitch_deg, motion.roll_deg)
            if self.drive.mode == "dualshock" and control.connected and hasattr(self.camera, "set_gimbal"):
                if control.right_stick.x or control.right_stick.y:
                    self.gimbal.set_input("dualshock", control.right_stick.x, -control.right_stick.y, now=now)
                else:
                    self.gimbal.release("dualshock", now=now)
            else:
                self.gimbal.release("dualshock", now=now)
            gimbal_pose = self.gimbal.advance(now)
            if hasattr(self.camera, "set_view"):
                self.camera.set_view(motion, gimbal_pose)
            else:
                if hasattr(self.camera, "set_motion"):
                    self.camera.set_motion(motion)
                if hasattr(self.camera, "set_gimbal"):
                    self.camera.set_gimbal(gimbal_pose)
            self.telemetry.update()
            source = getattr(self.telemetry, "source", None)
            if isinstance(source, RadioBenchSource):
                source.send_drive(self.drive_command.throttle, self.drive_command.steering,
                                  self.drive_command.brake, now)
            elif type(source) is SerialTelemetrySource and now >= self._next_drive_send:
                self._next_drive_send = max(self._next_drive_send + 0.04, now + 0.001)
                command = self.drive_command
                source.send_rover_command(
                    f"DRIVE:{command.throttle:+.2f},{command.steering:+.2f},{int(command.brake)}")
                rightStick = control.right_stick if self.drive.mode == "dualshock" and control.connected else None
                pan = rightStick.x if rightStick else 0.0
                tilt = -rightStick.y if rightStick else 0.0
                source.send_rover_command(f"STICK:{pan:+.2f},{tilt:+.2f}")
                leftStick = control.left_stick if self.drive.mode == "dualshock" and control.connected else None
                leftX = leftStick.x if leftStick else command.steering
                leftY = leftStick.y if leftStick else -command.throttle
                leftTrigger = control.l2 if leftStick else float(command.brake)
                rightTrigger = control.r2 if leftStick else max(0.0, command.throttle)
                source.send_rover_command(f"LEFT:{leftX:+.2f},{leftY:+.2f}")
                source.send_rover_command(f"TRIG:{leftTrigger:.2f},{rightTrigger:.2f}")

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
