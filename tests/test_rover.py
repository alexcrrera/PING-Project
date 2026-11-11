"""Verify drive visualization without opening a browser or building geometry."""

import math
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from ping_base.rover import RoverView
from ping_base.gimbal import GimbalPose


class RoverViewTests(unittest.TestCase):
    def make_view(self):
        view = object.__new__(RoverView)
        view.body = Mock()
        view._gimbal_reference = Mock()
        view._ground = Mock()
        view._wheels = [Mock() for _ in range(4)]
        view._wheel_angles = [0.0] * 4
        view._last_update = 0.0
        return view

    @staticmethod
    def sample(rpms=None, speed=0):
        return SimpleNamespace(roll_deg=0, pitch_deg=0, heading_deg=0,
                               speed_mps=speed, wheel_rpm=rpms)

    def test_turning_in_place_counter_rotates_each_side_at_zero_ground_speed(self):
        view = self.make_view()
        with patch("ping_base.rover.time.monotonic", return_value=.25):
            view.update(self.sample((-60, 60, -60, 60)))
        # A quarter second at 60 RPM is exactly a quarter turn. Ground speed
        # remains zero, but the two sides must visibly rotate oppositely.
        for index, expected in enumerate((math.tau * .75, math.tau * .25) * 2):
            self.assertAlmostEqual(view._wheel_angles[index], expected)
            view._wheels[index].rotate.assert_called_once()
            rotation = view._wheels[index].rotate.call_args.args
            self.assertAlmostEqual(rotation[0], -expected)
            self.assertEqual(rotation[1:], (0, 0))

    def test_zero_wheel_rpm_stops_animation_even_with_stale_nonzero_speed(self):
        view = self.make_view()
        with patch("ping_base.rover.time.monotonic", return_value=.25):
            view.update(self.sample((0, 0, 0, 0), speed=1))
        self.assertEqual(view._wheel_angles, [0] * 4)

    def test_optional_wheel_rpm_falls_back_to_ground_speed(self):
        view = self.make_view()
        with patch("ping_base.rover.time.monotonic", return_value=.25):
            view.update(self.sample(speed=.66))
        for angle in view._wheel_angles:
            self.assertAlmostEqual(angle, .5)

    def test_world_grid_moves_opposite_to_forward_rover_motion(self):
        view = self.make_view()
        view.update_motion(SimpleNamespace(x_m=0, y_m=.25))
        view._ground.move.assert_called_once_with(0, -.25, 0)

    def test_gimbal_moves_camera_head_independently_of_the_body(self):
        view = self.make_view()
        view._gimbal_yaw, view._gimbal_pitch = Mock(), Mock()
        view.update_gimbal(GimbalPose(90, 30))
        view._gimbal_yaw.rotate.assert_called_once_with(0, 0, -math.pi / 2)
        view._gimbal_pitch.rotate.assert_called_once_with(math.pi / 6, 0, 0)
        view.body.rotate.assert_not_called()

    def test_camera_head_can_compensate_body_roll(self):
        view = self.make_view()
        view._gimbal_yaw, view._gimbal_pitch = Mock(), Mock()
        view.update_gimbal(GimbalPose(0, 0, -12))
        view._gimbal_pitch.rotate.assert_called_once_with(0, math.radians(-12), 0)



if __name__ == "__main__":
    unittest.main()
