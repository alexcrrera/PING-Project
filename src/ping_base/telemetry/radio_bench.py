"""Explicit text-radio bench mode for two USB radios, without rover firmware."""

from math import isfinite

from .serial import SerialTelemetrySource
from .simulation import SimulatedTelemetrySource
from .model import TelemetrySample


class RadioBenchSource(SerialTelemetrySource):
    """Send readable test/drive lines while retaining raw receive diagnostics.

    The rover protocol is still provisional. This mode never sends ARM or any
    other state-changing command. The real rover must enforce its own arming
    and command timeout before accepting DRIVE lines.
    """

    DRIVE_PERIOD = 0.1

    def __init__(self, port: str, *, baudrate: int = 57600, **kwargs):
        super().__init__(port, baudrate=baudrate, **kwargs)
        self.name = f"Radio bench · {self.port} · {baudrate}"
        self.bytes_sent = 0
        self.last_sent_line: str | None = None
        self._sequence = 0
        self._last_drive_at = float("-inf")
        self.simulation = SimulatedTelemetrySource()
        self.transport_connected = True

    @property
    def radio_connected(self) -> bool:
        return self._serial is not None

    def poll(self, now: float) -> tuple[TelemetrySample, ...]:
        # The virtual rover stays live even while the USB radio is unplugged.
        super().poll(now)
        self.transport_connected = True
        samples = self.simulation.poll(now)
        if samples and self.radio_connected:
            self.send_telemetry(samples[-1], now)
        return samples

    def _send_line(self, line: str, now: float) -> bool:
        if not isfinite(now) or not self.radio_connected:
            return False
        if not line.isascii() or "\n" in line or "\r" in line or len(line) > 240:
            raise ValueError("Radio test line must be short, printable ASCII")
        payload = (line + "\n").encode("ascii")
        try:
            written = self._serial.write(payload)
            if written != len(payload):
                raise OSError("Incomplete radio write")
        except (OSError, ValueError) as exc:
            self.error = f"Radio send failed: {exc}"
            self._drop_connection()
            self._next_open = now + self._reconnect_interval
            return False
        self.bytes_sent += written
        self.last_sent_line = line
        return True

    def send_test(self, now: float) -> bool:
        self._sequence += 1
        return self._send_line(f"TEST:HELLO,{self._sequence}", now)

    def send_telemetry(self, sample: TelemetrySample, now: float) -> None:
        stamp = int(now * 1000)
        self._send_line(
            f"$PING,1,STATE,{stamp},{sample.speed_mps:+.3f},{sample.heading_deg:.1f},"
            f"{sample.pitch_deg:+.1f},{sample.roll_deg:+.1f},"
            f"{sample.battery_voltage:.2f},{sample.battery_percent:.1f},"
            f"{sample.distance_m:.2f},*", now)
        if not self.radio_connected:
            return
        wheels = sample.wheel_rpm, sample.motor_current_a, sample.wheel_slip
        if any(group is None for group in wheels):
            return
        fields = [*(f"{value:+.1f}" for value in sample.wheel_rpm),
                  *(f"{value:.2f}" for value in sample.motor_current_a),
                  *(f"{value:.3f}" for value in sample.wheel_slip)]
        self._send_line(f"$PING,1,WHEELS,{stamp}," + ",".join(fields) + ",*", now)

    def send_drive(self, throttle: float, steering: float, brake: bool, now: float,
                   *, force: bool = False) -> bool:
        if not all(isfinite(value) and -1 <= value <= 1 for value in (throttle, steering)):
            raise ValueError("Drive values must be finite and within [-1, 1]")
        if not isinstance(brake, bool):
            raise ValueError("Brake must be true or false")
        if not force and now - self._last_drive_at < self.DRIVE_PERIOD:
            return False
        self._sequence += 1
        line = f"DRIVE:{self._sequence},{throttle:+.2f},{steering:+.2f},{int(brake)}"
        if self._send_line(line, now):
            self._last_drive_at = now
            return True
        return False

    def close(self) -> None:
        self.simulation.close()
        super().close()
