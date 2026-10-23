import json
import unittest
from dataclasses import FrozenInstanceError, asdict

from ping_base.telemetry import (
    JsonLineTelemetryDecoder,
    SerialTelemetrySource,
    SimulatedTelemetrySource,
    TelemetryManager,
    TelemetrySample,
    TelemetryStatus,
)


def sample(now=0.0, **overrides):
    values = dict(
        received_at=now, battery_voltage=24.4, battery_percent=84.0,
        speed_mps=0.65, heading_deg=127.0, pitch_deg=1.2, roll_deg=-0.6,
        motor_temp_c=36.2, signal_rssi_dbm=-63.0, latency_ms=28.0,
        distance_m=12.4,
    )
    values.update(overrides)
    return TelemetrySample(**values)


def wire(**overrides):
    packet = asdict(sample())
    del packet["received_at"]
    packet["schema"] = "ping.telemetry.v1"
    packet.update(overrides)
    return json.dumps(packet).encode("utf-8") + b"\n"


class FakeSource:
    name = "Fake telemetry"
    transport_connected = True
    error = None

    def __init__(self):
        self.packets = ()
        self.closed = False

    def poll(self, now):
        packets, self.packets = self.packets, ()
        return packets

    def close(self):
        self.closed = True
        self.transport_connected = False


class FakePort:
    def __init__(self, data=b""):
        self.data = data
        self.fail = False
        self.closed = False
        self.read_sizes = []

    @property
    def in_waiting(self):
        if self.fail:
            raise OSError("USB unplugged")
        return len(self.data)

    def read(self, size):
        self.read_sizes.append(size)
        data, self.data = self.data[:size], self.data[size:]
        return data

    def close(self):
        self.closed = True


class TelemetryManagerTests(unittest.TestCase):
    def test_open_transport_waits_for_first_valid_packet(self):
        source = FakeSource()
        manager = TelemetryManager(source)
        state = manager.update(0)
        self.assertEqual(state.status, TelemetryStatus.WAITING)
        self.assertFalse(state.connected)
        self.assertIsNone(state.sample)
        source.packets = (sample(0.1),)
        state = manager.update(0.1)
        self.assertTrue(state.connected)
        self.assertEqual(state.sample.speed_mps, 0.65)

    def test_stale_values_disappear_and_resume_requires_new_packet(self):
        source = FakeSource()
        manager = TelemetryManager(source, stale_after=1.0)
        source.packets = (sample(0),)
        original = manager.update(0)
        stale = manager.update(1.0)
        self.assertEqual(stale.status, TelemetryStatus.STALE)
        self.assertIsNone(stale.sample)
        self.assertEqual(stale.age_seconds, 1.0)
        self.assertTrue(original.connected)
        self.assertEqual(len(manager.history), 1)
        source.packets = (sample(1.1),)
        self.assertTrue(manager.update(1.1).connected)

    def test_disconnect_and_reconnect_do_not_reuse_last_packet(self):
        source = FakeSource()
        manager = TelemetryManager(source)
        source.packets = (sample(0),)
        manager.update(0)
        source.transport_connected = False
        self.assertEqual(manager.update(0.1).status, TelemetryStatus.DISCONNECTED)
        self.assertIsNone(manager.state.sample)
        source.transport_connected = True
        self.assertEqual(manager.update(0.2).status, TelemetryStatus.WAITING)
        source.packets = (sample(0.3),)
        self.assertTrue(manager.update(0.3).connected)

    def test_invalid_and_out_of_order_samples_cannot_extend_freshness(self):
        source = FakeSource()
        manager = TelemetryManager(source)
        source.packets = (sample(0.2),)
        manager.update(0.2)
        source.packets = (
            sample(0.5, speed_mps=float("nan")), sample(0.6, battery_percent=True),
            sample(0.1), sample(2.0), sample(0.8, wheel_slip=(0.1, 0.1, 1.2, 0.1)),
        )
        state = manager.update(1.3)
        self.assertEqual(state.rejected_count, 5)
        self.assertEqual(state.status, TelemetryStatus.STALE)
        self.assertEqual(state.received_count, 1)

    def test_history_and_snapshots_are_immutable_and_bounded(self):
        source = FakeSource()
        manager = TelemetryManager(source, history_size=3)
        for tick in range(6):
            source.packets = (sample(tick),)
            manager.update(tick)
        history = manager.history
        self.assertEqual([p.received_at for p in history], [3, 4, 5])
        with self.assertRaises(FrozenInstanceError):
            manager.state.sample.speed_mps = 9
        with self.assertRaises(FrozenInstanceError):
            manager.state.status = TelemetryStatus.STALE
        source.packets = (sample(6),)
        manager.update(6)
        self.assertEqual(history[-1].received_at, 5)

    def test_injected_clock_and_source_replacement(self):
        source = FakeSource()
        manager = TelemetryManager(source, clock=lambda: 10.0)
        source.packets = (sample(10.0),)
        self.assertTrue(manager.update().connected)
        replacement = FakeSource()
        manager.replace_source(replacement)
        self.assertTrue(source.closed)
        self.assertEqual(manager.history, ())
        self.assertIsNone(manager.state.sample)
        self.assertEqual(manager.update().status, TelemetryStatus.WAITING)
        manager.close()
        self.assertTrue(replacement.closed)
        self.assertEqual(manager.update().status, TelemetryStatus.DISCONNECTED)

    def test_adapter_exception_cannot_leave_old_values_live(self):
        source = FakeSource()
        manager = TelemetryManager(source)
        source.packets = (sample(0),)
        manager.update(0)
        source.poll = lambda now: (_ for _ in ()).throw(OSError("lost"))
        state = manager.update(0.1)
        self.assertEqual(state.status, TelemetryStatus.DISCONNECTED)
        self.assertIsNone(state.sample)
        self.assertEqual(state.error, "lost")


class SimulationTests(unittest.TestCase):
    def test_seeded_stream_runs_at_ten_hz_with_four_independent_wheels(self):
        first = SimulatedTelemetrySource(seed=14)
        second = SimulatedTelemetrySource(seed=14)
        self.assertEqual(first.poll(100), second.poll(100))
        self.assertEqual(first.poll(100.05), ())
        packets = first.poll(100.3)
        self.assertEqual(len(packets), 3)
        self.assertEqual(packets[-1].received_at, 100.3)
        self.assertEqual(len(packets[-1].wheel_rpm), 4)
        self.assertEqual(len(packets[-1].wheel_slip), 4)
        self.assertGreater(len(set(packets[-1].wheel_rpm)), 1)
        self.assertGreaterEqual(packets[-1].distance_m, packets[0].distance_m)

    def test_pause_exercises_stale_path_and_resume_recovers(self):
        source = SimulatedTelemetrySource()
        manager = TelemetryManager(source)
        self.assertTrue(manager.update(0).connected)
        source.paused = True
        self.assertEqual(manager.update(1.1).status, TelemetryStatus.STALE)
        source.paused = False
        self.assertTrue(manager.update(1.2).connected)
        self.assertLessEqual(len(source.poll(10000)), 10)

    def test_simulation_samples_pass_same_validation_as_usb(self):
        manager = TelemetryManager(SimulatedTelemetrySource(seed=2))
        for tick in range(1000):
            state = manager.update(tick / 10)
            self.assertTrue(state.connected)
        self.assertEqual(state.rejected_count, 0)
        self.assertEqual(len(manager.history), 300)


class DecoderTests(unittest.TestCase):
    def test_fragmented_packets_coalesced_packets_and_host_timestamps(self):
        decoder = JsonLineTelemetryDecoder()
        packet = wire()
        self.assertEqual(decoder.feed(packet[:40], 1), ())
        result = decoder.feed(packet[40:] + wire(), 2)
        self.assertEqual(len(result), 2)
        self.assertTrue(all(p.received_at == 2 for p in result))
        self.assertIsNone(result[0].wheel_rpm)

    def test_optional_arrays_are_immutable_and_unknown_is_not_zero(self):
        decoder = JsonLineTelemetryDecoder()
        result = decoder.feed(wire(wheel_rpm=[1, 2, 3, 4], wheel_slip=[0.1] * 4), 0)[0]
        self.assertEqual(result.wheel_rpm, (1, 2, 3, 4))
        self.assertIsNone(result.motor_current_a)

    def test_invalid_values_and_missing_fields_reject_whole_frame(self):
        decoder = JsonLineTelemetryDecoder()
        malformed = [
            b"{broken}\n", b"[]\n", b"\xff\n", b'{"schema":"ping.telemetry.v1"}\n',
            wire(speed_mps="0.2"), wire(battery_percent=True), wire(heading_deg=360),
            wire(speed_mps=float("nan")), wire(latency_ms=float("inf")),
            wire(wheel_rpm=[1, 2, 3]), wire(wheel_slip=[-0.1] * 4),
            wire(motor_current_a=[True] * 4), wire(schema="unrecognized"),
        ]
        self.assertEqual(decoder.feed(b"".join(malformed), 0), ())
        self.assertEqual(decoder.rejected_count, len(malformed))
        self.assertEqual(len(decoder.feed(wire(), 0.1)), 1)

    def test_oversized_fragment_discards_until_newline_then_recovers(self):
        decoder = JsonLineTelemetryDecoder(max_line_bytes=512)
        decoder.feed(b"x" * 100000, 0)
        self.assertLessEqual(len(decoder._buffer), 512)
        self.assertEqual(decoder.rejected_count, 1)
        self.assertEqual(decoder.feed(wire(), 0), ())
        self.assertEqual(len(decoder.feed(wire(), 0.1)), 1)
        decoder.feed(b"partial", 0.2)
        decoder.reset()
        self.assertEqual(len(decoder.feed(wire(), 0.3)), 1)


class SerialSourceTests(unittest.TestCase):
    def test_reads_are_bounded_nonblocking_and_never_transmit(self):
        port = FakePort(wire() * 4)
        opened = []

        def factory(**kwargs):
            opened.append(kwargs)
            return port

        source = SerialTelemetrySource("COM7", serial_factory=factory, max_read_bytes=128)
        manager = TelemetryManager(source)
        self.assertEqual(manager.update(0).status, TelemetryStatus.WAITING)
        for tick in range(1, 8):
            manager.update(tick / 10)
        self.assertTrue(manager.state.connected)
        self.assertEqual(opened[0], {"port": "COM7", "baudrate": 57600, "timeout": 0, "write_timeout": 0})
        self.assertTrue(all(size <= 128 for size in port.read_sizes))
        manager.close()
        self.assertTrue(port.closed)

    def test_usb_reconnect_requires_new_valid_frame_and_clears_partial_bytes(self):
        first, second = FakePort(wire()), FakePort()
        ports = iter((first, second))
        source = SerialTelemetrySource("COM4", serial_factory=lambda **kw: next(ports))
        manager = TelemetryManager(source)
        self.assertTrue(manager.update(0).connected)
        first.data = b"partial old packet"
        manager.update(0.1)
        first.fail = True
        self.assertEqual(manager.update(0.2).status, TelemetryStatus.DISCONNECTED)
        self.assertTrue(first.closed)
        self.assertFalse(manager.update(2.1).connected)
        self.assertEqual(manager.update(2.2).status, TelemetryStatus.WAITING)
        second.data = wire()
        self.assertTrue(manager.update(2.3).connected)
        self.assertEqual(source.rejected_count, 0)

    def test_failed_open_retries_at_interval_instead_of_every_frame(self):
        calls = []

        def factory(**kwargs):
            calls.append(kwargs)
            raise OSError("port absent")

        source = SerialTelemetrySource("COM9", serial_factory=factory)
        manager = TelemetryManager(source)
        for now in (0, 0.1, 0.5, 1, 1.9):
            state = manager.update(now)
            self.assertEqual(state.status, TelemetryStatus.DISCONNECTED)
            self.assertIsNone(state.sample)
        self.assertEqual(len(calls), 1)
        manager.update(2)
        self.assertEqual(len(calls), 2)
        self.assertIn("port absent", manager.state.error)

    def test_invalid_usb_data_does_not_keep_link_current(self):
        port = FakePort(wire())
        manager = TelemetryManager(SerialTelemetrySource("COM2", serial_factory=lambda **kw: port))
        manager.update(0)
        port.data = wire(speed_mps=float("nan"))
        state = manager.update(1.1)
        self.assertEqual(state.status, TelemetryStatus.STALE)
        self.assertIsNone(state.sample)
        self.assertEqual(state.rejected_count, 1)


if __name__ == "__main__":
    unittest.main()
