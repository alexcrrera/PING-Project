"""USB serial telemetry and explicit gimbal commands."""

import json
from collections import deque
from datetime import datetime
from math import isfinite
from typing import Callable, Protocol

from .model import FIELD_RANGES, WHEEL_FIELD_RANGES, TelemetrySample, validate_sample
from .rvr import RoverGroups


RAW_LOG_LINES = 300
RAW_LINE_BYTES = 4096


class TelemetryDecoder(Protocol):
    rejected_count: int

    def feed(self, data: bytes, now: float) -> tuple[TelemetrySample, ...]: ...

    def reset(self) -> None: ...


class JsonLineTelemetryDecoder:
    """Bounded UTF-8 newline JSON decoder that resynchronizes after corruption.

    A bad/oversized line never updates freshness. Unknown fields are ignored to
    permit extensions. Every core channel is required; wheel arrays may be
    omitted or null, which means unavailable.
    """

    schema = "ping.telemetry.v1"

    def __init__(self, *, max_line_bytes: int = 4096):
        if isinstance(max_line_bytes, bool) or not isinstance(max_line_bytes, int) or max_line_bytes < 1:
            raise ValueError("max_line_bytes must be a positive integer")
        self.max_line_bytes = max_line_bytes
        self.rejected_count = 0
        self._buffer = bytearray()
        self._discarding = False

    def reset(self) -> None:
        """Discard partial frames at a connection boundary; retain diagnostics."""
        self._buffer.clear()
        self._discarding = False

    def feed(self, data: bytes, now: float) -> tuple[TelemetrySample, ...]:
        samples = []
        for byte in data:
            if byte == 10:
                if self._discarding:
                    self._discarding = False
                elif self._buffer:
                    try:
                        samples.append(self._decode(bytes(self._buffer), now))
                    except (ValueError, UnicodeError, TypeError, RecursionError, OverflowError):
                        self.rejected_count += 1
                self._buffer.clear()
            elif not self._discarding:
                if len(self._buffer) >= self.max_line_bytes:
                    self._buffer.clear()
                    self._discarding = True
                    self.rejected_count += 1
                else:
                    self._buffer.append(byte)
        return tuple(samples)

    def _decode(self, line: bytes, now: float) -> TelemetrySample:
        packet = json.loads(line.decode("utf-8"))
        if not isinstance(packet, dict) or packet.get("schema") != self.schema:
            raise ValueError("Expected ping.telemetry.v1 object")
        values = {}
        for name in FIELD_RANGES:
            if name not in packet:
                raise ValueError(f"Missing {name}")
            values[name] = packet[name]
        for name in WHEEL_FIELD_RANGES:
            value = packet.get(name)
            if value is not None:
                if not isinstance(value, list):
                    raise ValueError(f"{name} must be a JSON array")
                value = tuple(value)
            values[name] = value
        sample = TelemetrySample(received_at=now, **values)
        validate_sample(sample)
        return sample


class SerialTelemetryDecoder(JsonLineTelemetryDecoder):
    """Use the same bounded newline framing for rover and legacy JSON packets."""

    def __init__(self, *, max_line_bytes: int = 4096):
        super().__init__(max_line_bytes=max_line_bytes)
        self._rover = RoverGroups()

    def reset(self) -> None:
        super().reset()
        self._rover.reset()

    @property
    def latest_group_frames(self) -> dict[str, tuple[float, tuple[str, ...]]]:
        return self._rover.latest_frames

    def _decode(self, line: bytes, now: float) -> TelemetrySample:
        if line.startswith(b"$RVR,"):
            return self._rover.decode(line, now)
        sample = super()._decode(line, now)
        self._rover.reset()
        return sample


def _open_serial(**kwargs):
    # Import only when USB is selected; simulation works without pyserial.
    import serial
    return serial.Serial(**kwargs)


class SerialTelemetrySource:
    """Nonblocking reads, bounded buffering, and timed reconnects at 57600 baud.

    ``serial_factory`` is injectable for hardware-free tests. Opening a port is
    delegated to the OS/driver; read/write timeouts are zero. Gimbal commands
    are sent only through an explicit user action.
    """

    def __init__(self, port: str, *, baudrate: int = 57600,
                 decoder: TelemetryDecoder | None = None,
                 reconnect_interval: float = 2.0, max_read_bytes: int = 8192,
                 serial_factory: Callable | None = None):
        if not isinstance(port, str) or not port.strip():
            raise ValueError("A serial port is required")
        if isinstance(baudrate, bool) or not isinstance(baudrate, int) or baudrate <= 0:
            raise ValueError("baudrate must be a positive integer")
        if not isfinite(reconnect_interval) or reconnect_interval <= 0:
            raise ValueError("reconnect_interval must be positive and finite")
        if isinstance(max_read_bytes, bool) or not isinstance(max_read_bytes, int) or max_read_bytes < 1:
            raise ValueError("max_read_bytes must be a positive integer")
        self.port = port.strip()
        self.baudrate = baudrate
        self.name = f"USB · {self.port} · {baudrate}"
        self.transport_connected = False
        self.error: str | None = None
        self.decoder = decoder if decoder is not None else SerialTelemetryDecoder()
        self._reconnect_interval = reconnect_interval
        self._max_read_bytes = max_read_bytes
        self._serial_factory = serial_factory or _open_serial
        self._serial = None
        self._next_open = float("-inf")
        self._closed = False
        self.bytes_received = 0
        self.last_byte_at: float | None = None
        self.last_raw_line: str | None = None
        self._raw_line = bytearray()
        self._raw_line_truncated = False
        self._raw_line_count = 0
        self._raw_log: deque[tuple[datetime, str]] = deque(maxlen=RAW_LOG_LINES)

    @property
    def rejected_count(self) -> int:
        return self.decoder.rejected_count

    @property
    def latest_group_frames(self) -> dict[str, tuple[float, tuple[str, ...]]]:
        return getattr(self.decoder, "latest_group_frames", {})

    def raw_lines_since(self, cursor: int) -> tuple[int, tuple[tuple[datetime, str], ...]]:
        """Read recent completed lines using a cursor local to each dashboard."""
        count = min(self._raw_line_count - cursor, len(self._raw_log))
        return self._raw_line_count, tuple(self._raw_log)[-count:] if count > 0 else ()

    def send_gimbal_command(self, command: str) -> bool:
        """Send one explicit gimbal command over the open rover link."""
        if self._closed or self._serial is None:
            self.error = "Command failed: serial port is not connected"
            return False
        if not command.isascii() or "\n" in command or "\r" in command or len(command) > 29:
            raise ValueError("Invalid gimbal command")
        payload = (command + "\n").encode("ascii")
        try:
            if self._serial.write(payload) != len(payload):
                raise OSError("Incomplete serial write")
        except (OSError, ValueError) as exc:
            self.error = f"Command failed: {exc}"
            self._drop_connection()
            return False
        self.error = None
        return True

    def send_rover_command(self, command: str) -> bool:
        """Send one rover control frame on the current rover connection."""
        if not (command.startswith("DRIVE:") or command.startswith("STICK:")
                or command.startswith("BUTTON:") or command.startswith("LEFT:")
                or command.startswith("TRIG:") or command in ("NAV_MODE:0", "NAV_MODE:1", "NAV_MODE:2")):
            raise ValueError("Unknown rover command")
        return self.send_gimbal_command(command)

    def poll(self, now: float) -> tuple[TelemetrySample, ...]:
        if self._closed:
            return ()
        if self._serial is None:
            if now < self._next_open:
                return ()
            self._next_open = now + self._reconnect_interval
            try:
                self._serial = self._serial_factory(
                    port=self.port, baudrate=self.baudrate, timeout=0, write_timeout=0)
                self.transport_connected = True
                self.error = None
                self.decoder.reset()
                self.bytes_received = 0
                self.last_byte_at = None
                self.last_raw_line = None
                self._raw_line.clear()
                self._raw_line_truncated = False
            except (OSError, ValueError, ImportError) as exc:
                self.error = f"Cannot open {self.port}: {exc}"
                self.transport_connected = False
                return ()
        try:
            waiting = self._serial.in_waiting
            if not waiting:
                return ()
            data = self._serial.read(min(waiting, self._max_read_bytes))
            self._observe_raw(data, now)
            return self.decoder.feed(data, now)
        except (OSError, ValueError) as exc:
            self.error = f"Telemetry link lost: {exc}"
            self._drop_connection()
            self._next_open = now + self._reconnect_interval
            return ()

    def _observe_raw(self, data: bytes, now: float) -> None:
        if not data:
            return
        self.bytes_received += len(data)
        self.last_byte_at = now
        timestamp = datetime.now()
        for byte in data:
            if byte == 10:
                line = self._raw_line.decode("ascii", errors="replace").rstrip("\r")
                if self._raw_line_truncated:
                    line += "…"
                if line:
                    self.last_raw_line = line if len(line) <= 160 else line[:159] + "…"
                self._raw_log.append((timestamp, line))
                self._raw_line_count += 1
                self._raw_line.clear()
                self._raw_line_truncated = False
            elif len(self._raw_line) < RAW_LINE_BYTES:
                self._raw_line.append(byte)
            else:
                self._raw_line_truncated = True

    def _drop_connection(self) -> None:
        if self._serial is not None:
            try:
                self._serial.close()
            except (OSError, ValueError):
                pass
        self._serial = None
        self.transport_connected = False
        self.decoder.reset()
        self._raw_line.clear()
        self._raw_line_truncated = False

    def close(self) -> None:
        self._closed = True
        self._drop_connection()
