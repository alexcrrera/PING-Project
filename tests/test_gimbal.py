"""Mount motion, home reset, limits and input expiry without camera hardware."""

import unittest

from ping_base.gimbal import GimbalPose, VirtualGimbal


class GimbalTests(unittest.TestCase):
    def setUp(self):
        self.gimbal = VirtualGimbal(clock=lambda: 0)

    def test_hold_moves_both_axes_at_a_fixed_rate_and_release_holds_position(self):
        self.assertTrue(self.gimbal.set_input("page-a", 1, -1, now=0))
        for frame in range(1, 4):
            self.gimbal.advance(frame * .1)
        self.assertAlmostEqual(self.gimbal.state.yaw_deg, 4.5)
        self.assertAlmostEqual(self.gimbal.state.pitch_deg, -4.5)
        self.gimbal.release("page-a", now=.3)
        position = self.gimbal.state
        self.gimbal.advance(1)
        self.assertEqual(position, self.gimbal.state)

    def test_missing_heartbeat_stops_rotation_and_caps_long_clock_gaps(self):
        self.gimbal.set_input("page-a", 1, 1, now=0)
        self.gimbal.advance(10)
        position = self.gimbal.state
        self.assertEqual(position, GimbalPose(1.5, 1.5))
        self.gimbal.advance(20)
        self.assertEqual(position, self.gimbal.state)

    def test_limits_and_reset_clear_held_command_and_restore_exact_home(self):
        self.gimbal.nudge(yaw=999, pitch=-999)
        self.assertEqual(self.gimbal.state, GimbalPose(180, -60))
        self.gimbal.set_input("page-a", 1, -1, now=0)
        self.gimbal.advance(.1)
        self.assertEqual(self.gimbal.state, GimbalPose(180, -60))
        self.gimbal.reset()
        self.gimbal.advance(.2)
        self.gimbal.advance(.3)
        self.assertEqual(self.gimbal.state, GimbalPose())
        self.gimbal.nudge(yaw=-999, pitch=999)
        self.assertEqual(self.gimbal.state, GimbalPose(-180, 60))

    def test_other_pages_cannot_override_or_release_live_input(self):
        self.gimbal.set_input("page-a", 1, 0, now=0)
        self.assertFalse(self.gimbal.set_input("page-b", -1, 0, now=.1))
        self.gimbal.release("page-b", now=.1)
        self.gimbal.advance(.2)
        self.assertGreater(self.gimbal.state.yaw_deg, 0)
        self.assertTrue(self.gimbal.set_input("page-b", -1, 0, now=.5))

    def test_malformed_input_cannot_replace_a_valid_hold(self):
        self.gimbal.set_input("page-a", 1, 0, now=0)
        for invalid in (None, True, "1", float("nan"), float("inf")):
            self.assertFalse(self.gimbal.set_input("page-a", invalid, 0, now=.1))
            self.assertFalse(self.gimbal.set_input("page-a", 0, invalid, now=.1))
        self.gimbal.advance(.1)
        self.assertEqual(self.gimbal.state, GimbalPose(1.5, 0))

    def test_stabilization_holds_direction_and_levels_roll_as_body_rotates(self):
        self.gimbal.update_attitude(10, 3, 4)
        self.gimbal.nudge(yaw=20, pitch=7)
        self.gimbal.set_stabilized(True)
        self.gimbal.update_attitude(65, -4, 9)
        pose = self.gimbal.state
        self.assertAlmostEqual((65 + pose.yaw_deg) % 360, 30)
        self.assertAlmostEqual(-4 + pose.pitch_deg, 10)
        self.assertAlmostEqual(9 + pose.roll_deg, 0)
        self.assertFalse(self.gimbal.limited)

    def test_heading_wrap_and_manual_aim_work_while_stabilized(self):
        self.gimbal.update_attitude(359, 0, 0)
        self.gimbal.set_stabilized(True)
        self.gimbal.update_attitude(2, 0, 0)
        self.assertEqual(self.gimbal.state.yaw_deg, -3)
        self.gimbal.nudge(yaw=5, pitch=2)
        self.gimbal.update_attitude(12, -3, 5)
        self.assertAlmostEqual((12 + self.gimbal.state.yaw_deg) % 360, 4)
        self.assertAlmostEqual(-3 + self.gimbal.state.pitch_deg, 2)

    def test_switching_off_resumes_body_follow_and_home_keeps_mode(self):
        self.gimbal.set_stabilized(True)
        self.gimbal.update_attitude(30, 5, 7)
        self.gimbal.reset()
        self.assertTrue(self.gimbal.stabilized)
        self.assertEqual(self.gimbal.state, GimbalPose(0, 0, -7))
        self.gimbal.set_stabilized(False)
        before = self.gimbal.state
        self.gimbal.update_attitude(90, -10, 12)
        self.assertEqual(self.gimbal.state, before)

    def test_compensation_limits_are_visible_and_recover_within_travel(self):
        self.gimbal.set_stabilized(True)
        self.gimbal.update_attitude(0, 80, 60)
        self.assertTrue(self.gimbal.limited)
        self.assertEqual(self.gimbal.state, GimbalPose(0, -60, -45))
        self.gimbal.advance(0)
        self.gimbal.advance(.1)
        self.gimbal.update_attitude(0, 10, 5)
        self.assertFalse(self.gimbal.limited)
        self.assertEqual(self.gimbal.state, GimbalPose(0, -10, -5))


if __name__ == "__main__":
    unittest.main()
