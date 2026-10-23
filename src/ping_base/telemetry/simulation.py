"""A seeded, smooth 10 Hz rover telemetry source for UI development."""

from math import cos, floor, isfinite, pi, sin
from random import Random

from ..motion import VirtualRover
from .model import TelemetrySample


class SimulatedTelemetrySource:
    name = "SIMULATED TELEMETRY"
    error = None
    rejected_count = 0

    def __init__(self, *, seed: int = 7, rate_hz: float = 10.0,
                 rover: VirtualRover | None = None):
        if not isfinite(rate_hz) or rate_hz <= 0 or rate_hz > 100:
            raise ValueError("rate_hz must be in (0, 100]")
        self.transport_connected = True
        self.paused = False
        self.rover = rover
        self._random = Random(seed)
        self._interval = 1.0 / rate_hz
        self._start: float | None = None
        self._tick = 0

    def poll(self, now: float) -> tuple[TelemetrySample, ...]:
        if not self.transport_connected or self.paused:
            return ()
        if self._start is None:
            self._start = now
        elapsed = max(0.0, now - self._start)
        due_tick = floor((elapsed + 1e-9) / self._interval)
        # A delayed renderer must not cause an unbounded catch-up loop.
        self._tick = max(self._tick, due_tick - 9)
        samples = []
        while self._tick <= due_tick:
            t = self._tick * self._interval
            speed = max(0.0, 0.65 + 0.38 * sin(t * 0.16) + self._random.uniform(-0.025, 0.025))
            # Integral of the smooth commanded speed. Distance remains
            # continuous even if a paused/slow UI skips intermediate packets.
            distance = 0.65 * t + 0.38 * (1.0 - cos(t * 0.16)) / 0.16
            percent = max(0.0, 84.0 - t / 180.0)
            # 0.28 m test wheel diameter. Rear-right encounters a short patch
            # of looser ground every 24 s; wheels remain independent channels.
            patch = max(0.0, sin(t * pi / 12.0)) ** 12
            slips = tuple(0.015 + 0.005 * (1 + sin(t * 0.5 + i)) + patch * (0.035 if i < 3 else 0.16)
                          for i in range(4))
            wheel_rpm = tuple(speed / (pi * 0.28) * 60.0 / (1.0 - slip) for slip in slips)
            currents = tuple(2.0 + speed * 1.8 + slip * 6.0 for slip in slips)
            heading = (127.0 + t * 1.8 + 8.0 * sin(t * 0.09)) % 360.0
            pitch = 3.6 * sin(t * 0.32) + 0.7 * sin(t * 1.3)
            roll = 4.2 * sin(t * 0.24) + 0.5 * cos(t * 1.1)
            if self.rover is not None:
                # The station advances physics. Every consumer reads that same
                # immutable pose; polling telemetry must never move the rover.
                motion = self.rover.state
                speed, distance = motion.speed_mps, motion.distance_m
                heading, pitch, roll = motion.heading_deg, motion.pitch_deg, motion.roll_deg
                wheel_rpm = motion.wheel_rpm
                slips = tuple(0.0 if abs(rpm) < 1e-8 else max(0.0, slip + self._random.uniform(-0.003, 0.003))
                              for rpm, slip in zip(wheel_rpm, motion.wheel_slip))
                currents = tuple(0.0 if abs(rpm) < 1e-8 else max(0.0, current + self._random.uniform(-0.08, 0.08))
                                 for rpm, current in zip(wheel_rpm, motion.motor_current_a))
            samples.append(TelemetrySample(
                received_at=min(now, self._start + t),
                battery_voltage=22.0 + 3.1 * percent / 100 - abs(speed) * 0.12 + self._random.uniform(-0.02, 0.02),
                battery_percent=percent,
                speed_mps=speed,
                heading_deg=heading,
                pitch_deg=pitch,
                roll_deg=roll,
                motor_temp_c=35.0 + 5.0 * (1 - cos(t * 0.025)) + abs(speed) * 2.0,
                signal_rssi_dbm=-63.0 - 4.0 * sin(t * 0.07) + self._random.uniform(-0.8, 0.8),
                latency_ms=28.0 + 6.0 * sin(t * 0.2) + self._random.uniform(-1.5, 1.5),
                distance_m=distance,
                wheel_rpm=wheel_rpm,
                wheel_slip=slips,
                motor_current_a=currents,
            ))
            self._tick += 1
        return tuple(samples)

    def close(self) -> None:
        self.transport_connected = False
