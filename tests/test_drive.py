"""Browser input leases, controller routing, and shared station motion."""

from dataclasses import asdict
import json
import unittest
from unittest.mock import patch

from ping_base.controller import Button, ControllerState, PS4Controller, RawInput, Stick
from ping_base.drive import DriveCommand, DriveInputRouter
from ping_base.motion import RoverMotion
from ping_base.station import BaseStation
from ping_base.telemetry import SerialTelemetrySource, SimulatedTelemetrySource, TelemetryManager, TelemetrySample


class Clock:
    now = 0.0

    def __call__(self):
        return self.now


class DriveRouterTests(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()
        self.router = DriveInputRouter(clock=self.clock)
        self.disconnected = ControllerState()

    def test_held_key_heartbeat_extends_lease_then_missing_heartbeat_brakes(self):
        self.assertEqual(self.router.command(self.disconnected), DriveCommand())
        self.assertTrue(self.router.keyboard("page-a", 1, -.3))
        self.clock.now = .3
        self.assertEqual(self.router.command(self.disconnected).throttle, 1)
        self.assertTrue(self.router.keyboard("page-a", 1, -.3))
        self.clock.now = .69
        self.assertEqual(self.router.command(self.disconnected).steering, -.3)
        self.clock.now = .71
        self.assertEqual(self.router.command(self.disconnected), DriveCommand())

    def test_a_second_page_cannot_replace_or_blur_release_the_active_owner(self):
        self.router.keyboard("page-a", 1, 0, now=0)
        self.assertFalse(self.router.keyboard("page-b", -1, 1, now=.1))
        self.router.clear("page-b")
        self.assertEqual(self.router.command(self.disconnected, now=.2).throttle, 1)
        self.router.clear("page-a")
        self.assertEqual(self.router.command(self.disconnected, now=.2), DriveCommand())
        self.assertTrue(self.router.keyboard("page-b", -1, 1, now=.2))
        self.assertEqual(self.router.command(self.disconnected, now=.2).throttle, -1)

    def test_expired_owner_can_be_taken_over_without_an_intermediate_render(self):
        self.router.keyboard("page-a", 1, 0, now=0)
        self.assertTrue(self.router.keyboard("page-b", -1, 0, now=.4))
        self.router.clear("page-a")
        self.assertEqual(self.router.command(self.disconnected, now=.5).throttle, -1)

    def test_neutral_release_and_explicit_brake_have_distinct_commands(self):
        self.router.keyboard("page-a", 1, 0)
        self.router.keyboard("page-a", 0, 0)
        self.assertEqual(self.router.command(self.disconnected), DriveCommand(0, 0, False))
        self.router.keyboard("page-a", 1, .4, True)
        self.assertTrue(self.router.command(self.disconnected).brake)
        self.router.clear()
        self.assertEqual(self.router.command(self.disconnected), DriveCommand())

    def test_mode_switch_clears_old_keys_and_ignores_inactive_source(self):
        model = PS4Controller(deadzone=0)
        state = model.update(RawInput(connected=True, left_stick=Stick(.2, -.8)))
        self.router.keyboard("page-a", -1, -.5)
        # Selecting the already-selected source should not interrupt a hold.
        self.router.set_mode("keyboard")
        self.assertEqual(self.router.command(state).throttle, -1)
        self.router.set_mode("dualshock")
        self.assertFalse(self.router.keyboard("page-a", 1, 0))
        self.assertEqual(self.router.command(state), DriveCommand(.8, .2, False, "dualshock"))
        self.router.set_mode("keyboard")
        self.assertEqual(self.router.command(state), DriveCommand())
        with self.assertRaises(ValueError):
            self.router.set_mode("unknown")

    def test_dualshock_stick_cross_l2_and_disconnect(self):
        self.router.set_mode("dualshock")
        model = PS4Controller(deadzone=0)
        for reading, throttle, steering, brake in (
            (RawInput(connected=True, left_stick=Stick(-.6, .7)), -.7, -.6, False),
            (RawInput(connected=True, held=frozenset({Button.CROSS})), 0, 0, True),
            (RawInput(connected=True, l2=.5), 0, 0, True),
            (RawInput(connected=True, l2=.1), 0, 0, False),
            (RawInput(connected=False, left_stick=Stick(1, -1)), 0, 0, True),
        ):
            with self.subTest(reading=reading):
                command = self.router.command(model.update(reading))
                self.assertAlmostEqual(command.throttle, throttle)
                self.assertAlmostEqual(command.steering, steering)
                self.assertEqual(command.brake, brake)
                self.assertEqual(command.source, "dualshock")

    def test_keyboard_axis_validation_rejects_bad_payload_without_replacing_hold(self):
        self.router.keyboard("page-a", .5, -.25, now=0)
        for invalid in (True, None, "1", float("nan"), float("inf"), -float("inf")):
            with self.subTest(value=invalid):
                self.assertFalse(self.router.keyboard("page-a", invalid, 0, now=.1))
                self.assertFalse(self.router.keyboard("page-a", 0, invalid, now=.1))
        self.assertFalse(self.router.keyboard("page-a", 0, 0, "false", now=.1))
        self.assertFalse(self.router.keyboard("", 1, 0, now=.1))
        self.assertFalse(self.router.keyboard("page-a", 1, 0, now=float("nan")))
        self.assertEqual(self.router.command(self.disconnected, now=.2), DriveCommand(.5, -.25, False))
        self.assertTrue(self.router.keyboard("page-a", 5, -6, now=.2))
        self.assertEqual(self.router.command(self.disconnected, now=.2), DriveCommand(1, -1, False))

    def test_controller_model_sanitizes_invalid_hardware_axes_before_routing(self):
        self.router.set_mode("dualshock")
        model = PS4Controller(deadzone=0)
        state = model.update(RawInput(connected=True,
                                      left_stick=Stick(float("nan"), float("inf")),
                                      l2=float("nan")))
        self.assertEqual(self.router.command(state), DriveCommand(0, 0, False, "dualshock"))

    def test_invalid_timeout_and_nonfinite_read_clock_cannot_keep_input_live(self):
        for timeout in (0, -1, float("nan"), float("inf")):
            with self.assertRaises(ValueError):
                DriveInputRouter(timeout=timeout)
        self.router.keyboard("page-a", 1, 0, now=0)
        self.assertEqual(self.router.command(self.disconnected, now=float("inf")), DriveCommand())


class Camera:
    def __init__(self):
        self.motion = None

    def start(self):
        pass

    def close(self):
        pass

    def set_motion(self, motion):
        self.motion = motion


class Controller:
    def __init__(self):
        self.state = ControllerState()
        self.model = PS4Controller(deadzone=0)

    def start(self):
        pass

    def update(self):
        return self.state

    def close(self):
        pass


class ReceivingOnlyPort:
    def __init__(self):
        sample = TelemetrySample(0, 24, 80, .7, 234, 2, -3, 36, -64, 20, 12)
        wire = asdict(sample)
        wire.pop("received_at")
        wire["schema"] = "ping.telemetry.v1"
        self.data = (json.dumps(wire) + "\n").encode()
        self.writes = 0

    @property
    def in_waiting(self):
        return len(self.data)

    def read(self, size):
        data, self.data = self.data[:size], self.data[size:]
        return data

    def write(self, data):
        self.writes += 1
        raise AssertionError("Telemetry receiver must not transmit drive commands")

    def close(self):
        pass


class StationDrivingTests(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()
        self.camera = Camera()
        self.controller = Controller()
        self.manager = TelemetryManager(SimulatedTelemetrySource(), clock=self.clock)
        self.station = BaseStation(self.manager, self.camera, self.controller)
        self.patch = patch("ping_base.station.time.monotonic", self.clock)
        self.patch.start()
        self.station.start()

    def tearDown(self):
        self.station.close()
        self.patch.stop()

    def frames(self, seconds, *, keyboard=None):
        start = self.clock.now
        for frame in range(round(seconds * 60) + 1):
            self.clock.now = start + frame / 60
            if keyboard is not None:
                self.station.drive.keyboard("page-a", *keyboard, now=self.clock.now)
            self.station.tick()

    def test_keyboard_motion_camera_and_telemetry_share_the_same_pose(self):
        self.frames(1, keyboard=(1, .25))
        motion = self.station.virtual_rover.state
        self.assertGreater(motion.speed_mps, 0)
        self.assertGreater(motion.x_m, 0)
        self.assertGreater(motion.y_m, 0)
        self.assertIs(self.camera.motion, motion)
        self.assertEqual(self.manager.state.sample.speed_mps, motion.speed_mps)
        self.assertEqual(self.manager.state.sample.heading_deg, motion.heading_deg)
        self.assertEqual(self.manager.state.sample.wheel_rpm, motion.wheel_rpm)
        # A vanished page stops renewing input; station physics brakes itself.
        self.frames(1)
        self.assertEqual(self.station.virtual_rover.state.speed_mps, 0)
        self.assertTrue(self.station.drive_command.brake)

    def test_dualshock_drives_then_disconnect_brakes_and_clears_command(self):
        self.station.set_drive_mode("dualshock")
        self.controller.state = self.controller.model.update(
            RawInput(connected=True, left_stick=Stick(0, -1)))
        self.frames(1)
        self.assertGreater(self.station.virtual_rover.state.speed_mps, .9)
        self.controller.state = self.controller.model.update(RawInput())
        self.frames(.3)
        self.assertEqual(self.station.virtual_rover.state.speed_mps, 0)
        self.assertEqual(self.station.drive_command, DriveCommand(source="dualshock"))

    def test_serial_telemetry_remains_receiving_only_and_blocks_virtual_input(self):
        port = ReceivingOnlyPort()
        serial = SerialTelemetrySource("COM7", serial_factory=lambda **kwargs: port)
        self.station.replace_telemetry(serial)
        self.frames(.5, keyboard=(1, 1))
        self.assertFalse(self.station.virtual_driving)
        self.assertEqual(self.station.virtual_rover.state, RoverMotion())
        self.assertEqual(self.manager.state.sample.speed_mps, .7)
        self.assertEqual(self.manager.state.sample.heading_deg, 234)
        self.assertEqual(port.writes, 0)
        self.station.replace_telemetry(SimulatedTelemetrySource())
        self.frames(.3)
        self.assertTrue(self.station.virtual_driving)
        self.assertEqual(self.station.virtual_rover.state.speed_mps, 0)
        self.frames(.5, keyboard=(1, 0))
        self.assertGreater(self.station.virtual_rover.state.speed_mps, .5)

    def test_pausing_simulation_brakes_motion_and_retains_telemetry_stale_path(self):
        self.frames(1, keyboard=(1, 0))
        self.manager.source.paused = True
        self.frames(1.2, keyboard=(1, 0))
        self.assertFalse(self.station.virtual_driving)
        self.assertEqual(self.station.virtual_rover.state.speed_mps, 0)
        self.assertIsNone(self.manager.state.sample)


if __name__ == "__main__":
    unittest.main()
