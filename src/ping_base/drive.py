"""Input arbitration for the virtual rover, independent of UI and transports."""

from dataclasses import dataclass
from math import isfinite
from time import monotonic
from typing import Callable

from .controller import ControllerState


@dataclass(frozen=True)
class DriveCommand:
    throttle: float = 0.0
    steering: float = 0.0
    brake: bool = True
    source: str = "keyboard"


class DriveInputRouter:
    """Select one input source and expire missing browser heartbeats.

    A keyboard lease belongs to a browser client, so an idle second tab cannot
    cancel held controls in the first.
    """

    MODES = ("keyboard", "dualshock")

    def __init__(self, *, timeout: float = .4, clock: Callable[[], float] = monotonic):
        if not isfinite(timeout) or timeout <= 0:
            raise ValueError("Input timeout must be positive and finite")
        self.mode = "keyboard"
        self.timeout = timeout
        self._clock = clock
        self._owner: str | None = None
        self._received_at = float("-inf")
        self._keyboard = DriveCommand()

    def set_mode(self, mode: str) -> None:
        if mode not in self.MODES:
            raise ValueError("Select keyboard or dualshock input")
        if mode != self.mode:
            self.clear()
            self.mode = mode

    def clear(self, owner: str | None = None) -> None:
        if owner is None or owner == self._owner:
            self._owner = None
            self._received_at = float("-inf")
            self._keyboard = DriveCommand(source=self.mode)

    def keyboard(self, owner: str, throttle: float, steering: float, brake: bool = False,
                 *, now: float | None = None) -> bool:
        now = self._clock() if now is None else now
        if self.mode != "keyboard" or not owner or not isfinite(now):
            return False
        if (isinstance(throttle, bool) or isinstance(steering, bool)
                or not isinstance(throttle, (int, float)) or not isinstance(steering, (int, float))
                or not isfinite(throttle) or not isfinite(steering) or not isinstance(brake, bool)):
            return False
        if self._owner not in (None, owner) and now - self._received_at < self.timeout:
            return False
        self._owner = owner
        self._received_at = now
        self._keyboard = DriveCommand(max(-1.0, min(1.0, throttle)),
                                      max(-1.0, min(1.0, steering)), brake)
        return True

    def command(self, controller: ControllerState, *, now: float | None = None) -> DriveCommand:
        now = self._clock() if now is None else now
        if self.mode == "dualshock":
            if not controller.connected:
                return DriveCommand(source="dualshock")
            return DriveCommand(controller.r2, controller.left_stick.x,
                                controller.l2 > .1,
                                "dualshock")
        if not isfinite(now) or now - self._received_at >= self.timeout:
            self.clear()
            return DriveCommand()
        return self._keyboard
