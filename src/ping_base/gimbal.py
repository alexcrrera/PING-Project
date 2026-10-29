"""Virtual camera mount with bounded aiming, attitude stabilization and input expiry."""

from dataclasses import dataclass
from math import isfinite
from time import monotonic


@dataclass(frozen=True, slots=True)
class GimbalPose:
    """Angles relative to the rover: positive yaw right, positive pitch up."""

    yaw_deg: float = 0.0
    pitch_deg: float = 0.0
    roll_deg: float = 0.0


class VirtualGimbal:
    SPEED_DPS = 15.0
    YAW_LIMIT = 180.0
    PITCH_LIMIT = 60.0
    ROLL_LIMIT = 45.0
    INPUT_TIMEOUT = .4

    def __init__(self, *, clock=monotonic):
        self._clock = clock
        self.stabilized = False
        self.limited = False
        self._heading = self._body_pitch = self._body_roll = 0.0
        self.reset()

    @property
    def state(self) -> GimbalPose:
        return self._state

    def reset(self) -> None:
        self._world_heading, self._world_pitch = self._heading, self._body_pitch
        self._state = GimbalPose()
        self.limited = False
        self._owner: str | None = None
        self._received_at = float("-inf")
        self._last_update: float | None = None
        self._yaw = self._pitch = 0.0
        self._resolve_stabilization()

    def set_stabilized(self, enabled: bool) -> None:
        if type(enabled) is not bool:
            raise ValueError("Stabilization must be on or off")
        if enabled == self.stabilized:
            return
        self._world_heading = (self._heading + self._state.yaw_deg) % 360
        self._world_pitch = self._body_pitch + self._state.pitch_deg
        self.stabilized = enabled
        self._state = GimbalPose(self._state.yaw_deg, self._state.pitch_deg)
        self.limited = False
        self._resolve_stabilization()

    def update_attitude(self, heading: float, pitch: float, roll: float) -> None:
        if not all(self._valid(value) for value in (heading, pitch, roll)):
            raise ValueError("Rover attitude must be finite")
        self._heading, self._body_pitch, self._body_roll = heading, pitch, roll
        self._resolve_stabilization()

    def _resolve_stabilization(self) -> None:
        if not self.stabilized:
            return
        yaw = (self._world_heading - self._heading + 180) % 360 - 180
        pitch, roll = self._world_pitch - self._body_pitch, -self._body_roll
        self.limited = abs(pitch) > self.PITCH_LIMIT or abs(roll) > self.ROLL_LIMIT
        self._state = GimbalPose(yaw, max(-self.PITCH_LIMIT, min(self.PITCH_LIMIT, pitch)),
                                max(-self.ROLL_LIMIT, min(self.ROLL_LIMIT, roll)))

    @staticmethod
    def _valid(value) -> bool:
        return isinstance(value, (int, float)) and not isinstance(value, bool) and isfinite(value)

    def _move(self, yaw: float, pitch: float) -> None:
        self._state = GimbalPose(
            max(-self.YAW_LIMIT, min(self.YAW_LIMIT, self._state.yaw_deg + yaw)),
            max(-self.PITCH_LIMIT, min(self.PITCH_LIMIT, self._state.pitch_deg + pitch)),
            self._state.roll_deg,
        )
        if self.stabilized and (yaw or pitch):
            self._world_heading = (self._heading + self._state.yaw_deg) % 360
            self._world_pitch = self._body_pitch + self._state.pitch_deg
            self._resolve_stabilization()

    def nudge(self, *, yaw: float = 0, pitch: float = 0) -> None:
        if not self._valid(yaw) or not self._valid(pitch):
            raise ValueError("Gimbal angles must be finite numbers")
        self._move(yaw, pitch)

    def set_input(self, owner: str, yaw: float, pitch: float, *, now: float | None = None) -> bool:
        now = self._clock() if now is None else now
        if not owner or not all(self._valid(value) for value in (yaw, pitch, now)):
            return False
        if self._owner not in (None, owner) and now - self._received_at < self.INPUT_TIMEOUT:
            return False
        self.advance(now)
        self._owner = owner
        self._received_at = now
        self._yaw, self._pitch = max(-1, min(1, yaw)), max(-1, min(1, pitch))
        return True

    def release(self, owner: str | None = None, *, now: float | None = None) -> None:
        if owner is None or owner == self._owner:
            self.advance(self._clock() if now is None else now)
            self._owner = None
            self._yaw = self._pitch = 0.0

    def advance(self, now: float) -> GimbalPose:
        if not self._valid(now):
            raise ValueError("Gimbal clock must be finite")
        if self._last_update is not None and now > self._last_update:
            # A stalled browser cannot leave the mount rotating or make it jump.
            end = min(now, self._received_at + self.INPUT_TIMEOUT)
            dt = min(.1, max(0.0, end - self._last_update))
            self._move(self._yaw * self.SPEED_DPS * dt, self._pitch * self.SPEED_DPS * dt)
        if self._last_update is None or now > self._last_update:
            self._last_update = now
        return self._state
