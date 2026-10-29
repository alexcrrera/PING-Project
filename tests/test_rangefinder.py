"""Camera-center terrain/object returns, aim alignment and the 10 m boundary."""

from dataclasses import FrozenInstanceError
import math
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from ping_base.camera import SimulatedCameraSource
from ping_base.gimbal import GimbalPose


class RangefinderTests(unittest.TestCase):
    def setUp(self):
        self.camera = SimulatedCameraSource(width=320, height=180, fps=30)
        self.rocks = []
        self.camera._terrain_chunk = lambda x, y: (self.rocks if (x, y) == (0, 0) else [], [])

    def set_view(self, *, x=0, y=0, heading=0, pitch=0, roll=0, pan=0, tilt=0):
        motion = SimpleNamespace(x_m=x, y_m=y, heading_deg=heading, pitch_deg=pitch, roll_deg=roll)
        self.camera.set_view(motion, GimbalPose(pan, tilt))

    def capture_range(self):
        return self.camera._capture_frame(time.monotonic())[4]

    @staticmethod
    def expected_ground(pitch):
        depression = math.atan((.5 - .405) * 180 / (320 * .71)) - math.radians(pitch)
        return 1.12 / math.sin(depression)

    def test_downward_center_ray_reports_slant_range_to_visible_ground(self):
        self.set_view(tilt=-20)
        self.assertAlmostEqual(self.capture_range(), self.expected_ground(-20))
        self.set_view(pitch=-7, tilt=-13)
        self.assertAlmostEqual(self.capture_range(), self.expected_ground(-20))

    def test_sky_and_ground_beyond_ten_meters_have_no_return(self):
        for pitch in (0, 10, 60):
            with self.subTest(pitch=pitch):
                self.set_view(tilt=pitch)
                self.assertIsNone(self.capture_range())

    def test_exact_ten_meter_boundary_is_inclusive(self):
        alpha = math.atan((.5 - .405) * 180 / (320 * .71))
        for distance in (9.99, 10, 10.001):
            with self.subTest(distance=distance):
                self.set_view(tilt=math.degrees(alpha - math.asin(1.12 / distance)))
                reading = self.capture_range()
                if distance <= 10:
                    self.assertAlmostEqual(reading, distance)
                else:
                    self.assertIsNone(reading)

    def test_rock_at_crosshair_is_closer_than_ground_and_panning_away_loses_it(self):
        self.rocks[:] = [(0, 6, 1.3, 0)]
        self.set_view()
        ray_factor = math.hypot(1, (.5 - .405) * 180 / (320 * .71))
        self.assertAlmostEqual(self.capture_range(), 6 * ray_factor)
        self.set_view(pan=45)
        self.assertIsNone(self.capture_range())
        self.set_view(heading=45, pan=-45)
        self.assertAlmostEqual(self.capture_range(), 6 * ray_factor)

    def test_nearest_visible_rock_and_driving_change_the_return(self):
        self.rocks[:] = [(0, 8, 1.3, 0), (0, 6, 1.3, 1)]
        self.set_view()
        before = self.capture_range()
        self.set_view(y=2)
        after = self.capture_range()
        self.assertAlmostEqual(before / after, 6 / 4)
        self.assertLess(after, before)

    def test_centered_marker_post_returns_its_distance(self):
        # The even-numbered lane post at (2.45, 0) is five meters ahead.
        self.set_view(x=2.45, y=-5)
        factor = math.hypot(1, (.5 - .405) * 180 / (320 * .71))
        self.assertAlmostEqual(self.capture_range(), 5 * factor)

    def test_roll_retains_center_target(self):
        self.rocks[:] = [(0, 6, 1.3, 0)]
        self.set_view()
        expected = self.capture_range()
        for roll in (-30, 30):
            self.set_view(roll=roll)
            self.assertAlmostEqual(self.capture_range(), expected)

    def test_capture_does_not_mix_updated_aim_with_a_previously_rendered_pose(self):
        self.set_view(tilt=-20)
        original = self.camera._render_motion

        def change_aim_during_render(pose, mount):
            self.set_view(tilt=20)
            return original(pose, mount)

        with patch.object(self.camera, '_render_motion', side_effect=change_aim_during_render):
            capture = self.camera._capture_frame(123)
        self.assertEqual(capture[3], 123)
        self.assertAlmostEqual(capture[4], self.expected_ground(-20))
        self.assertIsNone(self.capture_range())

    def test_worker_publishes_immutable_range_with_its_jpeg(self):
        self.set_view(tilt=-20)
        try:
            self.camera.start()
            deadline = time.monotonic() + 2
            while self.camera.latest_frame() is None and time.monotonic() < deadline:
                time.sleep(.01)
            frame = self.camera.latest_frame()
            self.assertIsNotNone(frame)
            self.assertTrue(frame.jpeg.startswith(b'\xff\xd8'))
            self.assertAlmostEqual(frame.range_m, self.expected_ground(-20))
            self.set_view(tilt=20)
            self.assertAlmostEqual(frame.range_m, self.expected_ground(-20))
            with self.assertRaises(FrozenInstanceError):
                frame.range_m = 99
        finally:
            self.camera.close()


if __name__ == '__main__':
    unittest.main()
