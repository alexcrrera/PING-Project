"""Mount motion, home reset, limits and input expiry without camera hardware."""

import unittest

from ping_base.gimbal import GimbalPose, StabilizationMode, VirtualGimbal


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

    def test_cycle_visits_lock_follow_and_off_once_each(self):
        self.assertEqual(self.gimbal.stabilization_mode, StabilizationMode.OFF)
        self.assertFalse(self.gimbal.stabilized)
        for mode in (StabilizationMode.LOCK, StabilizationMode.FOLLOW, StabilizationMode.OFF):
            self.assertEqual(self.gimbal.cycle_stabilization(), mode)
            self.assertEqual(self.gimbal.stabilization_mode, mode)
            self.assertEqual(self.gimbal.stabilized, mode is not StabilizationMode.OFF)

    def test_follow_holds_pitch_and_levels_roll_while_turning_with_rover(self):
        self.gimbal.update_attitude(350, 3, 4)
        self.gimbal.nudge(yaw=20, pitch=7)
        self.gimbal.set_stabilization_mode("follow")
        self.gimbal.update_attitude(15, -4, 9)
        pose = self.gimbal.state
        self.assertEqual(pose.yaw_deg, 20)
        self.assertAlmostEqual((15 + pose.yaw_deg) % 360, 35)
        self.assertAlmostEqual(-4 + pose.pitch_deg, 10)
        self.assertAlmostEqual(9 + pose.roll_deg, 0)
        self.assertFalse(self.gimbal.limited)

    def test_follow_manual_aim_holds_new_pitch_and_relative_pan(self):
        self.gimbal.update_attitude(350, 4, 2)
        self.gimbal.set_stabilization_mode(StabilizationMode.FOLLOW)
        self.gimbal.update_attitude(5, -2, 5)
        self.gimbal.nudge(yaw=8, pitch=3)
        self.gimbal.update_attitude(25, 1, -4)
        self.assertEqual(self.gimbal.state, GimbalPose(8, 6, 4))
        self.gimbal.set_input("page-a", 1, -1, now=0)
        self.gimbal.advance(.1)
        self.assertEqual(self.gimbal.state, GimbalPose(9.5, 4.5, 4))
        self.gimbal.release("page-a", now=.1)
        self.gimbal.update_attitude(100, -3, 7)
        self.assertEqual(self.gimbal.state, GimbalPose(9.5, 8.5, -7))

    def test_mode_changes_capture_current_aim_without_pan_or_tilt_jumps(self):
        self.gimbal.update_attitude(350, 4, 7)
        self.gimbal.nudge(yaw=25, pitch=8)
        for mode in (StabilizationMode.LOCK, StabilizationMode.FOLLOW, StabilizationMode.LOCK,
                     StabilizationMode.OFF, StabilizationMode.FOLLOW):
            with self.subTest(mode=mode):
                before = self.gimbal.state
                self.gimbal.set_stabilization_mode(mode)
                self.assertEqual(self.gimbal.state.yaw_deg, before.yaw_deg)
                self.assertEqual(self.gimbal.state.pitch_deg, before.pitch_deg)
                self.gimbal.update_attitude(10, -1, -4)
        self.assertEqual(self.gimbal.state.roll_deg, 4)

    def test_follow_to_lock_captures_heading_after_a_vehicle_turn(self):
        self.gimbal.nudge(yaw=10, pitch=5)
        self.gimbal.set_stabilization_mode(StabilizationMode.FOLLOW)
        self.gimbal.update_attitude(90, -2, 3)
        self.gimbal.set_stabilization_mode(StabilizationMode.LOCK)
        self.gimbal.update_attitude(110, 2, 5)
        self.assertEqual(self.gimbal.state, GimbalPose(-10, 3, -5))
        self.assertAlmostEqual(110 + self.gimbal.state.yaw_deg, 100)

    def test_home_retains_follow_mode_and_clears_held_input(self):
        self.gimbal.set_stabilization_mode(StabilizationMode.FOLLOW)
        self.gimbal.set_input("page-a", 1, 1, now=0)
        self.gimbal.update_attitude(80, 5, 7)
        self.gimbal.reset()
        self.gimbal.advance(.1)
        self.gimbal.advance(.2)
        self.assertEqual(self.gimbal.stabilization_mode, StabilizationMode.FOLLOW)
        self.assertEqual(self.gimbal.state, GimbalPose(0, 0, -7))
        self.gimbal.update_attitude(120, -3, 4)
        self.assertEqual(self.gimbal.state, GimbalPose(0, 8, -4))

    def test_both_stabilized_modes_recover_pitch_target_after_pan_at_limit(self):
        for mode in (StabilizationMode.LOCK, StabilizationMode.FOLLOW):
            with self.subTest(mode=mode):
                gimbal = VirtualGimbal()
                gimbal.set_stabilization_mode(mode)
                gimbal.update_attitude(0, 80, 60)
                self.assertTrue(gimbal.limited)
                self.assertEqual(gimbal.state, GimbalPose(0, -60, -45))
                gimbal.nudge(yaw=5)
                gimbal.update_attitude(0, 10, 5)
                self.assertFalse(gimbal.limited)
                self.assertEqual(gimbal.state, GimbalPose(5, -10, -5))

    def test_disabling_follow_restores_unstabilized_body_follow(self):
        self.gimbal.set_stabilization_mode(StabilizationMode.FOLLOW)
        self.gimbal.update_attitude(50, 80, 60)
        self.gimbal.set_stabilized(False)
        before = self.gimbal.state
        self.assertEqual(before, GimbalPose(0, -60, 0))
        self.assertFalse(self.gimbal.limited)
        self.gimbal.update_attitude(90, -10, 12)
        self.assertEqual(self.gimbal.state, before)

    def test_boolean_api_and_invalid_mode_do_not_corrupt_selection(self):
        self.gimbal.set_stabilization_mode(StabilizationMode.FOLLOW)
        self.gimbal.set_stabilized(True)
        self.assertEqual(self.gimbal.stabilization_mode, StabilizationMode.LOCK)
        for invalid in (None, True, 1, "invalid"):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                self.gimbal.set_stabilization_mode(invalid)
            self.assertEqual(self.gimbal.stabilization_mode, StabilizationMode.LOCK)

    def test_switching_at_pitch_limit_captures_actual_view(self):
        self.gimbal.set_stabilization_mode(StabilizationMode.LOCK)
        self.gimbal.update_attitude(20, 80, 0)
        self.assertEqual(self.gimbal.state, GimbalPose(-20, -60, 0))
        self.gimbal.set_stabilization_mode(StabilizationMode.FOLLOW)
        self.assertEqual(self.gimbal.state, GimbalPose(-20, -60, 0))
        self.gimbal.update_attitude(50, 10, 0)
        self.assertEqual(self.gimbal.state, GimbalPose(-20, 10, 0))

    def test_reselecting_active_mode_does_not_replace_locked_pitch_at_limit(self):
        for mode in (StabilizationMode.LOCK, StabilizationMode.FOLLOW):
            with self.subTest(mode=mode):
                gimbal = VirtualGimbal()
                gimbal.set_stabilization_mode(mode)
                gimbal.update_attitude(0, 80, 0)
                gimbal.set_stabilization_mode(mode)
                gimbal.update_attitude(0, 10, 0)
                self.assertEqual(gimbal.state.pitch_deg, -10)


if __name__ == "__main__":
    unittest.main()
