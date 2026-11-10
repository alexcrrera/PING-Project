"""Independent, deterministic rover experiment model (SI units throughout).

This is a deliberately reduced planar dynamics model with a geometric terrain
contact approximation. It is not a rigid-body or suspension solver.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from math import atan2, cos, degrees, isfinite, pi, radians, sin


@dataclass(frozen=True)
class MotorPreset:
    label: str
    ratio: float
    free_rpm: float
    stall_torque_nm: float
    stall_current_a: float = 5.5
    free_current_a: float = .2


# Pololu 37D, 12 V, helical pinion, items 4743/4744/4745. Stall values
# are the manufacturer's extrapolations, not recommended continuous loads.
MOTORS = {
    "50:1": MotorPreset("50:1", 50.0, 200.0, 21 * .0980665),
    "70:1": MotorPreset("70:1", 70.0, 150.0, 27 * .0980665),
    "100:1": MotorPreset("100:1", 102.08, 100.0, 34 * .0980665),
}


@dataclass(frozen=True)
class TwinConfig:
    motor: str = "70:1"
    mass_kg: float = 12.0
    wheel_diameter_m: float = .28
    wheel_width_m: float = .08
    joint_offset_m: float = .06     # sideways distance from body side to arm pivot
    body_length_m: float = .94       # side-view l1
    body_width_m: float = .50        # side-view w1 interpreted as chassis width
    body_height_m: float = .18       # side-view h1
    front_arm_deg: float = 30.0      # alpha, from vertical
    rear_arm_deg: float = 30.0       # beta, from vertical
    arm_length_m: float = .40
    supply_v: float = 12.0
    drive_efficiency: float = .72
    wheel_inertia_kgm2: float = .008
    rolling_coefficient: float = .035
    viscous_drag_ns_m: float = .35
    high_mu: float = .95
    low_mu: float = .16
    rock_height_m: float = .13
    stair_height_m: float = .08
    stair_depth_m: float = .48

    @property
    def body_center_above_axle_m(self) -> float:
        """Place the box centre midway between the two arm-mount heights."""
        return self.arm_length_m * (cos(radians(self.front_arm_deg)) +
                                    cos(radians(self.rear_arm_deg))) / 2

    @property
    def wheelbase_m(self) -> float:
        """Front-to-rear axle spacing implied by the two side-view arms."""
        return self.arm_length_m * (sin(radians(self.front_arm_deg)) +
                                    sin(radians(self.rear_arm_deg)))

    @property
    def track_m(self) -> float:
        """Wheel-to-wheel spacing across the chassis, implied by the joints."""
        return self.body_width_m + 2 * self.joint_offset_m

    def wheel_offset(self, side: int, fore: int) -> tuple[float, float, float]:
        angle = self.front_arm_deg if fore > 0 else self.rear_arm_deg
        return (side * self.track_m / 2,
                fore * self.arm_length_m * sin(radians(angle)),
                self.wheel_diameter_m / 2)

    def arm_endpoints(self, side: int, fore: int) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
        """Offset body-side pivot to the matching wheel hub in one side plane."""
        pivot = (side * (self.body_width_m / 2 + self.joint_offset_m), 0.,
                 self.wheel_diameter_m / 2 + self.body_center_above_axle_m)
        return pivot, self.wheel_offset(side, fore)

    def joint_connection(self, side: int) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
        """Short lateral link from the body side to its offset arm pivot."""
        pivot, _ = self.arm_endpoints(side, 1)
        return (side * self.body_width_m / 2, 0., pivot[2]), pivot


@dataclass(frozen=True)
class TwinState:
    time_s: float = 0.0
    x_m: float = 0.0
    y_m: float = 0.0
    z_m: float = 0.0
    yaw_rad: float = 0.0
    pitch_deg: float = 0.0
    roll_deg: float = 0.0
    vx_mps: float = 0.0
    yaw_rate_rps: float = 0.0
    wheel_rad_s: tuple[float, float, float, float] = (0., 0., 0., 0.)
    wheel_angle_rad: tuple[float, float, float, float] = (0., 0., 0., 0.)
    motor_current_a: tuple[float, float, float, float] = (0., 0., 0., 0.)
    contact_force_n: tuple[float, float, float, float] = (0., 0., 0., 0.)
    traction_mu: tuple[float, float, float, float] = (0., 0., 0., 0.)
    slip_mps: tuple[float, float, float, float] = (0., 0., 0., 0.)
    blocked: bool = False


class DigitalTwin:
    def __init__(self, config: TwinConfig | None = None):
        self.config = config or TwinConfig()
        self.state = TwinState()

    def configure(self, **changes: float | str) -> None:
        candidate = replace(self.config, **changes)
        for key, value in candidate.__dict__.items():
            if key == "motor":
                if value not in MOTORS:
                    raise ValueError("Unknown motor preset")
            elif isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value):
                raise ValueError(f"{key} must be a finite number")
            elif key in {"front_arm_deg", "rear_arm_deg"}:
                if not 0 <= value <= 75:
                    raise ValueError(f"{key} must be between 0 and 75 degrees")
            elif key == "drive_efficiency":
                if not 0 < value <= 1:
                    raise ValueError("Drive efficiency must be in (0, 1]")
            elif key == "joint_offset_m":
                if value < 0:
                    raise ValueError("Joint offset must be nonnegative")
            elif value <= 0:
                raise ValueError(f"{key} must be positive")
        self.config = candidate

    def reset(self) -> None:
        self.state = TwinState()

    def terrain(self, x: float, y: float) -> tuple[float, float, str]:
        """Return height, coefficient of friction, and visible terrain class."""
        c = self.config
        if 1.1 <= y < 3.2 and -1.25 <= x <= 1.25:
            return 0., c.low_mu, "low traction"
        if 3.8 <= y < 5.9 and -1.25 <= x <= 1.25:
            return 0., c.high_mu, "high traction"
        if 6.6 <= y < 8.4 and abs(x) < .55:
            return c.rock_height_m, c.high_mu, "rock"
        if 9.0 <= y < 11.2 and abs(x) < 1.25:
            level = min(3, int((y - 9.0) / c.stair_depth_m) + 1)
            return level * c.stair_height_m, c.high_mu, "stairs"
        return 0., .65, "ordinary"

    def _wheel_places(self, x: float, y: float, yaw: float):
        c = self.config
        # FL / FR / RL / RR; +y is forward and +x is right in the scene.
        for lateral, fore in ((-1, 1), (1, 1), (-1, -1), (1, -1)):
            dx, dy, _ = c.wheel_offset(lateral, fore)
            yield (x + dx * cos(yaw) + dy * sin(yaw),
                   y - dx * sin(yaw) + dy * cos(yaw), lateral)

    def step(self, dt: float, throttle: float, steer: float) -> TwinState:
        if not 0 < dt <= .1:
            raise ValueError("step must be in (0, 0.1] seconds")
        c, s, motor = self.config, self.state, MOTORS[self.config.motor]
        throttle, steer = max(-1., min(1., throttle)), max(-1., min(1., steer))
        radius = c.wheel_diameter_m / 2
        wheel = list(s.wheel_rad_s)
        currents, forces, mus, slips = [], [], [], []
        positions = list(self._wheel_places(s.x_m, s.y_m, s.yaw_rad))
        heights = [self.terrain(x, y)[0] for x, y, _ in positions]
        for i, (x, y, lateral) in enumerate(positions):
            _, mu, _ = self.terrain(x, y)
            command = max(-1., min(1., throttle - lateral * steer))
            # Linear 12 V output torque/speed envelope. Gear losses are
            # represented by a separate configurable drivetrain efficiency.
            free_rad_s = motor.free_rpm * 2 * pi / 60 * c.supply_v / 12
            torque = command * motor.stall_torque_nm * c.drive_efficiency
            torque -= motor.stall_torque_nm * c.drive_efficiency * wheel[i] / max(free_rad_s, .01)
            torque = max(-motor.stall_torque_nm, min(motor.stall_torque_nm, torque))
            local_speed = s.vx_mps - lateral * s.yaw_rate_rps * c.track_m / 2
            slip = radius * wheel[i] - local_speed
            # Smooth longitudinal tire law, limited by mu*N. It allows spin
            # and locked-wheel sliding; no encoder-to-ground-speed shortcut.
            normal = c.mass_kg * 9.81 / 4
            force = mu * normal * slip / (abs(slip) + .12)
            wheel[i] += (torque - force * radius) / c.wheel_inertia_kgm2 * dt
            wheel[i] = max(-3 * free_rad_s, min(3 * free_rad_s, wheel[i]))
            current = motor.free_current_a + abs(torque) / max(motor.stall_torque_nm * c.drive_efficiency, .01) * (motor.stall_current_a - motor.free_current_a)
            currents.append(min(motor.stall_current_a, current))
            forces.append(force)
            mus.append(mu)
            slips.append(slip)
        front_h = (heights[0] + heights[1]) / 2
        rear_h = (heights[2] + heights[3]) / 2
        left_h = (heights[0] + heights[2]) / 2
        right_h = (heights[1] + heights[3]) / 2
        pitch = atan2(front_h - rear_h, c.wheelbase_m)
        roll = atan2(right_h - left_h, c.track_m)
        drag = c.viscous_drag_ns_m * s.vx_mps
        rolling = c.rolling_coefficient * c.mass_kg * 9.81 * s.vx_mps / (abs(s.vx_mps) + .04)
        accel = (sum(forces) - drag - rolling) / c.mass_kg - 9.81 * sin(pitch)
        speed = s.vx_mps + accel * dt
        if abs(speed) < .003 and abs(throttle) < .001:
            speed = 0.
        yaw_accel = ((forces[0] + forces[2] - forces[1] - forces[3]) * c.track_m / 2
                     - .6 * s.yaw_rate_rps) / max(c.mass_kg * (c.track_m**2 + c.wheelbase_m**2) / 12, .01)
        yaw_rate = s.yaw_rate_rps + yaw_accel * dt
        yaw = s.yaw_rad + yaw_rate * dt
        proposed_x = s.x_m + speed * sin(yaw) * dt
        proposed_y = s.y_m + speed * cos(yaw) * dt
        ahead = list(self._wheel_places(proposed_x, proposed_y, yaw))
        rises = [self.terrain(x, y)[0] - h for (x, y, _), h in zip(ahead, heights)]
        blocked = any(rise > radius * .55 for rise in rises)
        if blocked:
            speed = 0.
            new_x, new_y = s.x_m, s.y_m
        else:
            new_x, new_y = proposed_x, proposed_y
        next_h = [self.terrain(x, y)[0] for x, y, _ in self._wheel_places(new_x, new_y, yaw)]
        wheel_angles = tuple(angle + (old + new) * .5 * dt
                             for angle, old, new in zip(s.wheel_angle_rad, s.wheel_rad_s, wheel))
        self.state = TwinState(s.time_s + dt, new_x, new_y, sum(next_h) / 4,
                               yaw, degrees(pitch), degrees(roll), speed, yaw_rate,
                               tuple(wheel), wheel_angles, tuple(currents), tuple(forces), tuple(mus),
                               tuple(slips), blocked)
        return self.state
