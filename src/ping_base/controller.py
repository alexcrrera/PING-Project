"""Pure controller model. No pygame, GUI, serial port, or background thread."""

from dataclasses import dataclass, field
from enum import Enum
from math import hypot, isfinite
from types import MappingProxyType
from typing import Mapping


class Button(str, Enum):
    CROSS = "Cross"
    CIRCLE = "Circle"
    SQUARE = "Square"
    TRIANGLE = "Triangle"
    UP = "Up"
    DOWN = "Down"
    LEFT = "Left"
    RIGHT = "Right"
    L1 = "L1"
    R1 = "R1"
    L2 = "L2"
    R2 = "R2"
    L3 = "L3"
    R3 = "R3"
    SHARE = "Share"
    OPTIONS = "Options"
    PS = "PS"
    TOUCHPAD = "Touchpad"


@dataclass(frozen=True)
class Stick:
    x: float = 0.0  # Positive right.
    y: float = 0.0  # Positive down.


@dataclass(frozen=True)
class ButtonState:
    held: bool = False
    pressed: bool = False   # At least one down edge in this update.
    released: bool = False  # At least one up edge in this update.
    toggled: bool = False   # Flips on every down edge; resets on disconnect.


@dataclass(frozen=True)
class RawInput:
    """Adapter output: normalized axes plus ordered button transitions.

    `held` is the final hardware state; `changes` preserves taps occurring
    entirely between updates. Change tuples contain (button, is_down).
    `device_id` must change when a different physical connection is selected.
    """

    connected: bool = False
    device_id: str = ""
    name: str = "No controller"
    held: frozenset[Button] = frozenset()
    changes: tuple[tuple[Button, bool], ...] = ()
    left_stick: Stick = Stick()
    right_stick: Stick = Stick()
    l2: float = 0.0
    r2: float = 0.0
    touchpad_available: bool = False


def _empty_buttons() -> Mapping[Button, ButtonState]:
    return MappingProxyType({button: ButtonState() for button in Button})


@dataclass(frozen=True)
class ControllerState:
    connected: bool = False
    device_id: str = ""
    name: str = "No controller"
    buttons: Mapping[Button, ButtonState] = field(default_factory=_empty_buttons)
    left_stick: Stick = Stick()
    right_stick: Stick = Stick()
    l2: float = 0.0
    r2: float = 0.0
    touchpad_available: bool = False
    sequence: int = 0


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value)) if isfinite(value) else 0.0


def apply_deadzone(stick: Stick, deadzone: float) -> Stick:
    """Radial deadzone, rescaled continuously to a unit circle."""
    x, y = _clamp(stick.x, -1.0, 1.0), _clamp(stick.y, -1.0, 1.0)
    magnitude = hypot(x, y)
    if magnitude <= deadzone:
        return Stick()
    scale = (min(magnitude, 1.0) - deadzone) / ((1.0 - deadzone) * magnitude)
    return Stick(x * scale, y * scale)


class PS4Controller:
    """Owns immutable snapshots shared by the UI and future command handling."""

    def __init__(self, deadzone: float = 0.10):
        if not 0.0 <= deadzone < 1.0:
            raise ValueError("deadzone must be between 0 (inclusive) and 1 (exclusive)")
        self.deadzone = deadzone
        self.state = ControllerState()

    def update(self, reading: RawInput) -> ControllerState:
        previous = self.state
        fresh_connection = reading.connected and (
            not previous.connected or reading.device_id != previous.device_id
        )
        buttons = {}
        for button in Button:
            old = previous.buttons[button]
            if not reading.connected:
                buttons[button] = ButtonState(released=old.held)
                continue
            if fresh_connection:
                # An already-held button on attachment is not a new press.
                buttons[button] = ButtonState(held=button in reading.held)
                continue
            held, toggled = old.held, old.toggled
            pressed = released = False
            transitions = [down for key, down in reading.changes if key == button]
            transitions.append(button in reading.held)
            for down in transitions:
                if down and not held:
                    pressed = True
                    toggled = not toggled
                elif held and not down:
                    released = True
                held = down
            buttons[button] = ButtonState(held, pressed, released, toggled)

        self.state = ControllerState(
            connected=reading.connected,
            device_id=reading.device_id if reading.connected else "",
            name=reading.name,
            buttons=MappingProxyType(buttons),
            left_stick=apply_deadzone(reading.left_stick, self.deadzone) if reading.connected else Stick(),
            right_stick=apply_deadzone(reading.right_stick, self.deadzone) if reading.connected else Stick(),
            l2=_clamp(reading.l2, 0.0, 1.0) if reading.connected else 0.0,
            r2=_clamp(reading.r2, 0.0, 1.0) if reading.connected else 0.0,
            touchpad_available=reading.connected and reading.touchpad_available,
            sequence=previous.sequence + 1,
        )
        return self.state
