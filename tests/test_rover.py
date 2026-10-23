"""Verify drive visualization without opening a browser or building geometry."""

import math
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from ping_base.rover import RoverView


class RoverViewTests(unittest.TestCase):
    def make_view(self):
        view = object.__new__(RoverView)
        view.body = Mock()
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


if __name__ == "__main__":
    unittest.main()
