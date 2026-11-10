"""UI-independent telemetry snapshots and freshness management."""

from collections import deque
from dataclasses import dataclass
from enum import Enum
from math import isfinite
from time import monotonic
from typing import Callable, Protocol


@dataclass(frozen=True)
class TelemetrySample:
    """One complete reading; ``received_at`` uses the host's monotonic clock.

    Values are SI units unless their suffix says otherwise. Heading is clockwise
    from north, pitch is nose up, and roll is right side down, in degrees.
    """

    received_at: float
    battery_voltage: float
    battery_percent: float
    speed_mps: float
    heading_deg: float
    pitch_deg: float
    roll_deg: float
    motor_temp_c: float
    signal_rssi_dbm: float
    latency_ms: float
    distance_m: float
    # Wheel order: front-left, front-right, rear-left, rear-right. Missing
    # channels are unknown, never fabricated zero readings.
    wheel_rpm: tuple[float, float, float, float] | None = None
    wheel_slip: tuple[float, float, float, float] | None = None
    motor_current_a: tuple[float, float, float, float] | None = None


# Shared by the sample validator and the example JSON protocol decoder.
FIELD_RANGES = {
    "battery_voltage": (0.0, 60.0),
    "battery_percent": (0.0, 100.0),
    "speed_mps": (-20.0, 20.0),
    "heading_deg": (0.0, 360.0),
    "pitch_deg": (-90.0, 90.0),
    "roll_deg": (-180.0, 180.0),
    "motor_temp_c": (-40.0, 150.0),
    "signal_rssi_dbm": (-150.0, 0.0),
    "latency_ms": (0.0, 60000.0),
    "distance_m": (0.0, 100000000.0),
}

WHEEL_FIELD_RANGES = {
    "wheel_rpm": (-1000.0, 1000.0),
    "wheel_slip": (0.0, 1.0),
    "motor_current_a": (0.0, 100.0),
}


def validate_sample(sample: TelemetrySample) -> None:
    """Reject nonfinite, boolean, out-of-range, and malformed adapter values."""
    if not isinstance(sample, TelemetrySample):
        raise ValueError("Expected TelemetrySample")
    for name, (low, high) in FIELD_RANGES.items():
        value = getattr(sample, name)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"{name} must be a number")
        if not low <= value <= high or not isfinite(value):
            raise ValueError(f"{name} outside [{low}, {high}]")
    if sample.heading_deg == 360.0:
        raise ValueError("heading_deg must be less than 360")
    for name, (low, high) in WHEEL_FIELD_RANGES.items():
        values = getattr(sample, name)
        if values is None:
            continue
        if not isinstance(values, tuple) or len(values) != 4:
            raise ValueError(f"{name} must contain four immutable wheel readings")
        for value in values:
            if (isinstance(value, bool) or not isinstance(value, (int, float))
                    or not low <= value <= high or not isfinite(value)):
                raise ValueError(f"{name} outside [{low}, {high}]")
    if (isinstance(sample.received_at, bool)
            or not isinstance(sample.received_at, (int, float))
            or not isfinite(sample.received_at)):
        raise ValueError("received_at must be finite")


class TelemetrySource(Protocol):
    """Adapters perform bounded work and return complete samples without waiting.

    A transport being open does not mean that fresh telemetry has arrived.
    Sources must stamp samples with the supplied ``now`` clock domain, never a
    robot clock or wall time. The ordinary telemetry adapter is receive-only;
    explicit radio bench mode sends provisional text commands for link testing.
    """

    name: str
    transport_connected: bool
    error: str | None

    def poll(self, now: float) -> tuple[TelemetrySample, ...]: ...

    def close(self) -> None: ...


class TelemetryStatus(str, Enum):
    WAITING = "waiting"
    CONNECTED = "connected"
    STALE = "stale"
    DISCONNECTED = "disconnected"


@dataclass(frozen=True)
class TelemetryState:
    status: TelemetryStatus = TelemetryStatus.WAITING
    sample: TelemetrySample | None = None
    age_seconds: float | None = None
    source_name: str = "Telemetry"
    error: str | None = None
    received_count: int = 0
    rejected_count: int = 0

    @property
    def connected(self) -> bool:
        """True only while a validated reading is fresh and transport is live."""
        return self.status is TelemetryStatus.CONNECTED


class TelemetryManager:
    """Own source lifecycle, freshness, immutable state, and a bounded history.

    Call ``update`` from the application loop. ``state.sample`` is deliberately
    None for stale/disconnected links. ``history`` retains historical readings
    for plots; callers must label them as history rather than live values.
    """

    def __init__(self, source: TelemetrySource, *, stale_after: float = 1.0,
                 history_size: int = 300, clock: Callable[[], float] = monotonic):
        if not isfinite(stale_after) or stale_after <= 0:
            raise ValueError("stale_after must be positive and finite")
        if isinstance(history_size, bool) or not isinstance(history_size, int) or history_size < 1:
            raise ValueError("history_size must be a positive integer")
        self.source = source
        self.stale_after = stale_after
        self._clock = clock
        self._history: deque[TelemetrySample] = deque(maxlen=history_size)
        self._latest: TelemetrySample | None = None
        self._received_count = 0
        self._rejected_count = 0
        self._closed = False
        self.state = TelemetryState(source_name=source.name)

    @property
    def history(self) -> tuple[TelemetrySample, ...]:
        return tuple(self._history)

    def update(self, now: float | None = None) -> TelemetryState:
        now = self._clock() if now is None else now
        if not isfinite(now):
            raise ValueError("now must be finite")
        if self._closed:
            return self.state
        # Source poll errors are an adapter responsibility; this final boundary
        # still ensures a hardware exception cannot leave an apparently live UI.
        poll_error = None
        try:
            packets = self.source.poll(now)
        except (OSError, ValueError, RuntimeError) as exc:
            packets = ()
            poll_error = str(exc)
        if not self.source.transport_connected or poll_error is not None:
            self._latest = None
            status = TelemetryStatus.DISCONNECTED
            sample = None
            age = None
        else:
            for packet in packets:
                try:
                    validate_sample(packet)
                    if packet.received_at > now:
                        raise ValueError("Sample timestamp is in the future")
                    if self._latest and packet.received_at < self._latest.received_at:
                        raise ValueError("Sample timestamp went backwards")
                except ValueError:
                    self._rejected_count += 1
                    continue
                self._latest = packet
                self._history.append(packet)
                self._received_count += 1
            age = None if self._latest is None else max(0.0, now - self._latest.received_at)
            if age is None:
                status = TelemetryStatus.WAITING
            elif age >= self.stale_after:
                status = TelemetryStatus.STALE
            else:
                status = TelemetryStatus.CONNECTED
            sample = self._latest if status is TelemetryStatus.CONNECTED else None
        self.state = TelemetryState(
            status=status, sample=sample, age_seconds=age,
            source_name=self.source.name, error=poll_error or self.source.error,
            received_count=self._received_count,
            rejected_count=self._rejected_count + getattr(self.source, "rejected_count", 0),
        )
        return self.state

    def replace_source(self, source: TelemetrySource) -> None:
        """Swap simulation for USB without changing the GUI or its consumers."""
        self.source.close()
        self.source = source
        self._latest = None
        self._history.clear()
        self._received_count = 0
        self._rejected_count = 0
        self._closed = False
        self.state = TelemetryState(source_name=source.name)

    set_source = replace_source

    def close(self) -> None:
        if not self._closed:
            self.source.close()
            self._closed = True
            self._latest = None
            self.state = TelemetryState(
                status=TelemetryStatus.DISCONNECTED, source_name=self.source.name,
                received_count=self._received_count,
                rejected_count=self.state.rejected_count,
            )
