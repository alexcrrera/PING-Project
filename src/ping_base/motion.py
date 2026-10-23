"""Small hardware-independent skid-steer rover model for operator practice."""

from dataclasses import dataclass
from math import cos, degrees, isfinite, pi, radians, sin


WheelValues = tuple[float, float, float, float]


@dataclass(frozen=True)
class RoverMotion:
    """Immutable local pose and four-wheel readings (FL, FR, RL, RR).

    Heading is clockwise from north: zero points along +y and 90 along +x.
    Speed and wheel RPM are signed, while distance accumulates both directions.
    """

    x_m: float = 0.0
    y_m: float = 0.0
    speed_mps: float = 0.0
    heading_deg: float = 0.0
    pitch_deg: float = 0.0
    roll_deg: float = 0.0
    distance_m: float = 0.0
    wheel_rpm: WheelValues = (0.0, 0.0, 0.0, 0.0)
    wheel_slip: WheelValues = (0.0, 0.0, 0.0, 0.0)
    motor_current_a: WheelValues = (0.0, 0.0, 0.0, 0.0)
    yaw_rate_dps: float = 0.0


class VirtualRover:
    """Accelerate a four-wheel rover from normalized throttle/steering input.

    The station owns the clock and calls ``advance`` once per update. Telemetry,
    camera, and model views consume the same snapshot. Large clock gaps are
    capped so a suspended browser cannot teleport the rover when it resumes.
    This model never imports hardware libraries or transmits drive commands.
    """

    MAX_SPEED_MPS = 1.2
    TRACK_WIDTH_M = 0.72
    WHEEL_DIAMETER_M = 0.28
    MAX_STEP_S = 0.1
    ACCELERATION_MPS2 = 1.6
    COAST_DECELERATION_MPS2 = 3.5
    BRAKE_DECELERATION_MPS2 = 7.0
    TURN_SPEED_MPS = 0.65

    def __init__(self) -> None:
        self.reset()

    @property
    def state(self) -> RoverMotion:
        return self._state

    def reset(self) -> None:
        self._state = RoverMotion()
        self._last_update: float | None = None
        self._throttle = 0.0
        self._steering = 0.0
        self._brake = False
        self._left_mps = 0.0
        self._right_mps = 0.0

    def set_command(self, throttle: float, steering: float, brake: bool = False) -> None:
        """Set desired motion; positive steering turns clockwise (right)."""
        if not isfinite(throttle) or not isfinite(steering):
            raise ValueError("Drive commands must be finite")
        self._throttle = max(-1.0, min(1.0, float(throttle)))
        self._steering = max(-1.0, min(1.0, float(steering)))
        self._brake = bool(brake)

    def stop(self) -> None:
        """Clear pending input and apply the virtual brake."""
        self.set_command(0.0, 0.0, brake=True)

    @staticmethod
    def _approach(current: float, target: float, delta: float) -> float:
        if current < target:
            return min(target, current + delta)
        return max(target, current - delta)

    def _wheel_target(self) -> tuple[float, float]:
        if self._brake:
            return 0.0, 0.0
        linear = self._throttle * self.MAX_SPEED_MPS
        turn = self._steering * self.TURN_SPEED_MPS
        left, right = linear + turn, linear - turn
        scale = max(1.0, abs(left) / self.MAX_SPEED_MPS,
                    abs(right) / self.MAX_SPEED_MPS)
        return left / scale, right / scale

    def advance(self, now: float) -> RoverMotion:
        if not isfinite(now):
            raise ValueError("Motion clock must be finite")
        if self._last_update is None:
            self._last_update = now
            return self._state
        if now <= self._last_update:
            return self._state
        dt = min(self.MAX_STEP_S, now - self._last_update)
        self._last_update = now
        targets = self._wheel_target()
        old_left, old_right = self._left_mps, self._right_mps
        new_speeds = []
        for current, target in zip((old_left, old_right), targets):
            if self._brake:
                acceleration = self.BRAKE_DECELERATION_MPS2
            elif target == 0.0 or current * target < 0.0 or abs(target) < abs(current):
                acceleration = self.COAST_DECELERATION_MPS2
            else:
                acceleration = self.ACCELERATION_MPS2
            new_speeds.append(self._approach(current, target, acceleration * dt))
        self._left_mps, self._right_mps = new_speeds
        speed = (self._left_mps + self._right_mps) / 2.0
        yaw = (self._left_mps - self._right_mps) / self.TRACK_WIDTH_M
        # Integrate with average wheel velocity during this frame, so braking
        # and reversing do not move by a full frame at the final wheel speed.
        travel = (old_left + old_right + self._left_mps + self._right_mps) / 4.0 * dt
        yaw_step = ((old_left - old_right) / self.TRACK_WIDTH_M + yaw) / 2.0 * dt
        heading_mid = radians(self._state.heading_deg) + yaw_step / 2.0
        x = self._state.x_m + travel * sin(heading_mid)
        y = self._state.y_m + travel * cos(heading_mid)
        distance = self._state.distance_m + abs(travel)
        heading = (self._state.heading_deg + degrees(yaw_step)) % 360.0
        # Terrain attitude depends on travel, never an independent animation
        # clock. At rest the body holds the terrain angle it actually reached.
        pitch = 3.2 * sin(distance * 0.9 + x * 0.2)
        roll = 2.6 * sin(distance * 0.65 + x * 0.4)
        wheel_speeds = (self._left_mps, self._right_mps,
                        self._left_mps, self._right_mps)
        rpm = tuple(value * 60.0 / (pi * self.WHEEL_DIAMETER_M) for value in wheel_speeds)
        turning = abs(self._left_mps - self._right_mps) / (2.0 * self.MAX_SPEED_MPS)
        slips = tuple(0.0 if abs(value) < 1e-8 else 0.015 + turning * 0.035
                      for value in wheel_speeds)
        currents = tuple(0.0 if abs(value) < 1e-8 else 1.2 + abs(value) * 2.1 + turning
                         for value in wheel_speeds)
        self._state = RoverMotion(
            x_m=x, y_m=y, speed_mps=speed, heading_deg=heading,
            pitch_deg=pitch, roll_deg=roll, distance_m=distance,
            wheel_rpm=rpm, wheel_slip=slips, motor_current_a=currents,
            yaw_rate_dps=degrees(yaw),
        )
        return self._state
