"""Hardware and keyboard adapters. The model and viewer never query devices."""

import time
from typing import Protocol, Sequence

import pygame
from pygame._sdl2 import controller as sdl

from .controller import Button, RawInput, Stick


class InputSource(Protocol):
    status: str

    def read(self, events: Sequence[pygame.event.Event]) -> RawInput: ...
    def close(self) -> None: ...


# SDL standardizes physical positions across USB/Bluetooth and driver mappings.
BUTTON_MAP = {
    pygame.CONTROLLER_BUTTON_A: Button.CROSS,
    pygame.CONTROLLER_BUTTON_B: Button.CIRCLE,
    pygame.CONTROLLER_BUTTON_X: Button.SQUARE,
    pygame.CONTROLLER_BUTTON_Y: Button.TRIANGLE,
    pygame.CONTROLLER_BUTTON_BACK: Button.SHARE,
    pygame.CONTROLLER_BUTTON_GUIDE: Button.PS,
    pygame.CONTROLLER_BUTTON_START: Button.OPTIONS,
    pygame.CONTROLLER_BUTTON_LEFTSTICK: Button.L3,
    pygame.CONTROLLER_BUTTON_RIGHTSTICK: Button.R3,
    pygame.CONTROLLER_BUTTON_LEFTSHOULDER: Button.L1,
    pygame.CONTROLLER_BUTTON_RIGHTSHOULDER: Button.R1,
    pygame.CONTROLLER_BUTTON_DPAD_UP: Button.UP,
    pygame.CONTROLLER_BUTTON_DPAD_DOWN: Button.DOWN,
    pygame.CONTROLLER_BUTTON_DPAD_LEFT: Button.LEFT,
    pygame.CONTROLLER_BUTTON_DPAD_RIGHT: Button.RIGHT,
    20: Button.TOUCHPAD,  # SDL_CONTROLLER_BUTTON_TOUCHPAD (SDL >= 2.0.14).
}
TRIGGER_BUTTON_THRESHOLD = 0.5


def normalize_axis(value: int) -> float:
    return max(-1.0, min(1.0, value / (32768.0 if value < 0 else 32767.0)))


def normalize_trigger(value: int) -> float:
    return max(0.0, min(1.0, value / 32767.0))


def is_ps4_name(name: str) -> bool:
    name = name.casefold()
    return "dualshock" in name or "ps4" in name or name == "wireless controller"


class PygamePS4Input:
    """Poll on the main thread, after the application drains pygame events.

    Auto-select a PS4 by name; an explicit device index can select any mapped
    gamepad. Once attached, track the SDL instance ID rather than its index.
    """

    def __init__(self, device_index: int | None = None):
        sdl.init()
        self.device_index = device_index
        self.device = None
        self.instance_id = None
        self.touchpad_available = False
        self.next_scan = 0.0
        self.status = "Waiting for a PS4 controller. Connect USB or pair Bluetooth."

    def _connect(self) -> None:
        count = sdl.get_count()
        indices = range(count) if self.device_index is None else [self.device_index]
        for index in indices:
            if not 0 <= index < count or not sdl.is_controller(index):
                continue
            name = sdl.name_forindex(index) or "Unknown controller"
            if self.device_index is None and not is_ps4_name(name):
                continue
            self.device = sdl.Controller(index)
            self.instance_id = self.device.as_joystick().get_instance_id()
            self.touchpad_available = "touchpad" in self.device.get_mapping()
            self.status = "Live input | USB / Bluetooth via SDL"
            return
        self.status = (
            "No matching PS4. Use --list-devices; select a mapped device with --device-index N."
            if count else "Waiting for a PS4 controller. Connect USB or pair Bluetooth."
        )

    def read(self, events: Sequence[pygame.event.Event]) -> RawInput:
        try:
            if self.device is not None and not self.device.attached():
                self.close()
                self.next_scan = 0.0
                self.status = "Controller disconnected. Inputs reset; waiting to reconnect."
                return RawInput()
            if self.device is None:
                now = time.monotonic()
                if now >= self.next_scan:
                    self.next_scan = now + 0.5
                    self._connect()
                if self.device is None:
                    return RawInput()
            device = self.device
            held = {
                button for code, button in BUTTON_MAP.items()
                if (button != Button.TOUCHPAD or self.touchpad_available)
                and device.get_button(code)
            }
            l2 = normalize_trigger(device.get_axis(pygame.CONTROLLER_AXIS_TRIGGERLEFT))
            r2 = normalize_trigger(device.get_axis(pygame.CONTROLLER_AXIS_TRIGGERRIGHT))
            if l2 >= TRIGGER_BUTTON_THRESHOLD:
                held.add(Button.L2)
            if r2 >= TRIGGER_BUTTON_THRESHOLD:
                held.add(Button.R2)
            changes = []
            for event in events:
                if getattr(event, "instance_id", None) != self.instance_id:
                    continue
                if event.type in (pygame.CONTROLLERBUTTONDOWN, pygame.CONTROLLERBUTTONUP):
                    button = BUTTON_MAP.get(event.button)
                    if button is not None and (button != Button.TOUCHPAD or self.touchpad_available):
                        changes.append((button, event.type == pygame.CONTROLLERBUTTONDOWN))
                elif event.type == pygame.CONTROLLERAXISMOTION:
                    button = {
                        pygame.CONTROLLER_AXIS_TRIGGERLEFT: Button.L2,
                        pygame.CONTROLLER_AXIS_TRIGGERRIGHT: Button.R2,
                    }.get(event.axis)
                    if button is not None:
                        changes.append((button, normalize_trigger(event.value) >= TRIGGER_BUTTON_THRESHOLD))
            return RawInput(
                connected=True, device_id=str(self.instance_id), name=device.name,
                held=frozenset(held), changes=tuple(changes),
                left_stick=Stick(normalize_axis(device.get_axis(pygame.CONTROLLER_AXIS_LEFTX)),
                                 normalize_axis(device.get_axis(pygame.CONTROLLER_AXIS_LEFTY))),
                right_stick=Stick(normalize_axis(device.get_axis(pygame.CONTROLLER_AXIS_RIGHTX)),
                                  normalize_axis(device.get_axis(pygame.CONTROLLER_AXIS_RIGHTY))),
                l2=l2, r2=r2, touchpad_available=self.touchpad_available,
            )
        except pygame.error as exc:
            self.close()
            self.status = f"Input unavailable: {exc}. Retrying automatically."
            return RawInput()

    def close(self) -> None:
        if self.device is not None:
            self.device.quit()
        self.device = None
        self.instance_id = None


KEY_BUTTONS = {
    pygame.K_j: Button.CROSS, pygame.K_k: Button.CIRCLE,
    pygame.K_h: Button.SQUARE, pygame.K_u: Button.TRIANGLE,
    pygame.K_UP: Button.UP, pygame.K_DOWN: Button.DOWN,
    pygame.K_LEFT: Button.LEFT, pygame.K_RIGHT: Button.RIGHT,
    pygame.K_q: Button.L1, pygame.K_e: Button.R1,
    pygame.K_z: Button.L2, pygame.K_c: Button.R2,
    pygame.K_1: Button.L3, pygame.K_2: Button.R3,
    pygame.K_TAB: Button.SHARE, pygame.K_RETURN: Button.OPTIONS,
    pygame.K_p: Button.PS, pygame.K_SPACE: Button.TOUCHPAD,
}


class KeyboardInput:
    status = "DEMO | Keyboard input only | No radio connection"

    def __init__(self):
        self.keys: set[int] = set()

    def read(self, events: Sequence[pygame.event.Event]) -> RawInput:
        changes = []
        for event in events:
            if event.type == pygame.WINDOWFOCUSLOST:
                changes.extend((KEY_BUTTONS[key], False) for key in self.keys if key in KEY_BUTTONS)
                self.keys.clear()
            elif event.type in (pygame.KEYDOWN, pygame.KEYUP):
                down = event.type == pygame.KEYDOWN
                was_down = event.key in self.keys
                if down:
                    self.keys.add(event.key)
                else:
                    self.keys.discard(event.key)
                if down != was_down and event.key in KEY_BUTTONS:
                    changes.append((KEY_BUTTONS[event.key], down))
        return RawInput(
            connected=True, device_id="keyboard-demo", name="Keyboard demo",
            held=frozenset(KEY_BUTTONS[key] for key in self.keys if key in KEY_BUTTONS),
            changes=tuple(changes),
            left_stick=Stick(float((pygame.K_d in self.keys) - (pygame.K_a in self.keys)),
                             float((pygame.K_s in self.keys) - (pygame.K_w in self.keys))),
            right_stick=Stick(float((pygame.K_l in self.keys) - (pygame.K_f in self.keys)),
                              float((pygame.K_g in self.keys) - (pygame.K_t in self.keys))),
            l2=float(pygame.K_z in self.keys), r2=float(pygame.K_c in self.keys),
            touchpad_available=True,
        )

    def close(self) -> None:
        self.keys.clear()
