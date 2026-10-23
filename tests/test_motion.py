"""Deterministic driving physics and the simulated telemetry integration."""

from dataclasses import FrozenInstanceError, asdict
from math import isfinite
import unittest

from ping_base.motion import RoverMotion, VirtualRover
from ping_base.telemetry import SimulatedTelemetrySource
from ping_base.telemetry.model import validate_sample


def drive(rover, throttle, steering, *, start=0.0, seconds=2.0, brake=False):
    rover.set_command(throttle, steering, brake)
    rover.advance(start)
    for frame in range(1, round(seconds * 60) + 1):
        rover.advance(start + frame / 60)
    return rover.state


class VirtualRoverTests(unittest.TestCase):
    def test_initial_rest_and_snapshots_are_immutable(self):
        rover = VirtualRover()
        original = rover.state
        drive(rover, 0.0, 0.0)
        self.assertEqual(rover.state, RoverMotion())
        with self.assertRaises(FrozenInstanceError):
            original.speed_mps = 4
        drive(rover, 1, 0, start=2.0)
        self.assertEqual(original.speed_mps, 0)

    def test_forward_and_reverse_follow_heading_and_accumulate_distance(self):
        forward = drive(VirtualRover(), 1, 0)
        reverse = drive(VirtualRover(), -1, 0)
        self.assertAlmostEqual(forward.speed_mps, 1.2)
        self.assertAlmostEqual(reverse.speed_mps, -1.2)
        self.assertAlmostEqual(forward.x_m, 0)
        self.assertAlmostEqual(reverse.x_m, 0)
        self.assertGreater(forward.y_m, 1)
        self.assertLess(reverse.y_m, -1)
        self.assertGreater(reverse.distance_m, 1)
        self.assertAlmostEqual(forward.distance_m, reverse.distance_m)
        self.assertTrue(all(value < 0 for value in reverse.wheel_rpm))

    def test_turn_in_place_changes_heading_and_differential_wheels(self):
        state = drive(VirtualRover(), 0, 1, seconds=1)
        self.assertGreater(state.heading_deg, 30)
        self.assertGreater(state.yaw_rate_dps, 0)
        self.assertEqual(state.speed_mps, 0)
        self.assertEqual(state.distance_m, 0)
        self.assertEqual(state.pitch_deg, 0)
        self.assertEqual(state.roll_deg, 0)
        self.assertGreater(state.wheel_rpm[0], 0)
        self.assertLess(state.wheel_rpm[1], 0)
        self.assertEqual(state.wheel_rpm[0], state.wheel_rpm[2])
        left = drive(VirtualRover(), 0, -1, seconds=1)
        self.assertLess(left.yaw_rate_dps, 0)
        self.assertAlmostEqual(left.heading_deg, 360 - state.heading_deg)

    def test_forward_turn_moves_toward_positive_x(self):
        state = drive(VirtualRover(), .7, .4)
        self.assertGreater(state.x_m, .1)
        self.assertGreater(state.y_m, .1)
        self.assertGreater(state.wheel_rpm[0], state.wheel_rpm[1])
        self.assertNotEqual(state.pitch_deg, 0)

    def test_neutral_and_brake_stop_without_drifting_forever(self):
        coasting = VirtualRover()
        braking = VirtualRover()
        for rover in (coasting, braking):
            drive(rover, 1, 0)
        coast_initial = coasting.state.distance_m
        brake_initial = braking.state.distance_m
        coasting.set_command(0, 0)
        braking.stop()
        for frame in range(1, 61):
            coasting.advance(2 + frame / 60)
            braking.advance(2 + frame / 60)
        self.assertEqual(coasting.state.speed_mps, 0)
        self.assertEqual(braking.state.speed_mps, 0)
        self.assertLess(braking.state.distance_m - brake_initial,
                        coasting.state.distance_m - coast_initial)
        stopped = braking.state
        braking.advance(3.1)
        self.assertEqual(braking.state, stopped)

    def test_clock_gaps_are_bounded_and_invalid_input_cannot_poison_state(self):
        rover = VirtualRover()
        rover.set_command(10, -10)
        rover.advance(5)
        state = rover.advance(5000)
        self.assertLess(state.distance_m, .02)
        self.assertLessEqual(abs(state.speed_mps), 1.2)
        self.assertIs(rover.advance(1), state)
        self.assertIs(rover.advance(5000), state)
        for invalid in (float("nan"), float("inf"), -float("inf")):
            with self.subTest(value=invalid):
                with self.assertRaises(ValueError):
                    rover.set_command(invalid, 0)
                with self.assertRaises(ValueError):
                    rover.set_command(0, invalid)
                with self.assertRaises(ValueError):
                    rover.advance(invalid)
        self.assertTrue(all(isfinite(value) for value in asdict(state).values()
                            if isinstance(value, float)))

    def test_reset_clears_pose_clock_and_desired_input(self):
        rover = VirtualRover()
        drive(rover, 1, 1)
        rover.reset()
        self.assertEqual(rover.state, RoverMotion())
        rover.advance(100)
        rover.advance(101)
        self.assertEqual(rover.state, RoverMotion())


class DrivenTelemetryTests(unittest.TestCase):
    def test_rest_is_exact_zero_and_polling_never_advances_motion(self):
        rover = VirtualRover()
        rover.set_command(1, 0)
        source = SimulatedTelemetrySource(rover=rover)
        for now in (0, .1, 10):
            packets = source.poll(now)
            self.assertTrue(packets)
            for packet in packets:
                self.assertEqual(packet.speed_mps, 0)
                self.assertEqual(packet.wheel_rpm, (0, 0, 0, 0))
                self.assertEqual(packet.motor_current_a, (0, 0, 0, 0))
                validate_sample(packet)
        self.assertEqual(rover.state, RoverMotion())

    def test_packets_track_signed_speed_pose_and_wheels_with_sensor_jitter(self):
        rover = VirtualRover()
        source = SimulatedTelemetrySource(rover=rover, seed=12)
        source.poll(0)
        state = drive(rover, -.7, .2)
        packet = source.poll(2)[-1]
        self.assertEqual(packet.speed_mps, state.speed_mps)
        self.assertEqual(packet.heading_deg, state.heading_deg)
        self.assertEqual(packet.pitch_deg, state.pitch_deg)
        self.assertEqual(packet.roll_deg, state.roll_deg)
        self.assertEqual(packet.distance_m, state.distance_m)
        self.assertEqual(packet.wheel_rpm, state.wheel_rpm)
        self.assertNotEqual(packet.wheel_slip, state.wheel_slip)
        validate_sample(packet)

    def test_ten_hz_polling_and_source_replacement_need_no_physics_change(self):
        rover = VirtualRover()
        first = SimulatedTelemetrySource(rover=rover)
        self.assertEqual(len(first.poll(10)), 1)
        self.assertEqual(first.poll(10.05), ())
        self.assertEqual(len(first.poll(10.3)), 3)
        replacement = SimulatedTelemetrySource(rover=rover)
        self.assertEqual(replacement.poll(100)[0].speed_mps, 0)


if __name__ == "__main__":
    unittest.main()
