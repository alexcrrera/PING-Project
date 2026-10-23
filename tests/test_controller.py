import math
import unittest

from ping_base.controller import Button, PS4Controller, RawInput, Stick, apply_deadzone


def reading(*buttons, **kwargs):
    return RawInput(connected=True, device_id="ps4-1", held=frozenset(buttons), **kwargs)


class ControllerTests(unittest.TestCase):
    def setUp(self):
        self.controller = PS4Controller()
        self.controller.update(reading())

    def test_hold_press_release_and_toggle_are_distinct(self):
        first = self.controller.update(reading(Button.CROSS))
        self.assertTrue(first.buttons[Button.CROSS].pressed)
        self.assertTrue(first.buttons[Button.CROSS].held)
        self.assertTrue(first.buttons[Button.CROSS].toggled)
        for _ in range(10):
            button = self.controller.update(reading(Button.CROSS)).buttons[Button.CROSS]
            self.assertTrue(button.held)
            self.assertTrue(button.toggled)
            self.assertFalse(button.pressed)
        button = self.controller.update(reading()).buttons[Button.CROSS]
        self.assertTrue(button.released)
        self.assertTrue(button.toggled)
        self.assertFalse(button.held)
        self.assertFalse(self.controller.update(reading()).buttons[Button.CROSS].released)
        self.assertFalse(self.controller.update(reading(Button.CROSS)).buttons[Button.CROSS].toggled)

    def test_short_taps_and_duplicate_down_events(self):
        state = self.controller.update(reading(changes=(
            (Button.CROSS, True), (Button.CROSS, True), (Button.CROSS, False),
        )))
        button = state.buttons[Button.CROSS]
        self.assertTrue(button.pressed and button.released and button.toggled)
        self.assertFalse(button.held)
        self.assertFalse(self.controller.update(reading()).buttons[Button.CROSS].pressed)

    def test_two_taps_in_one_frame_toggle_twice(self):
        button = self.controller.update(reading(changes=(
            (Button.CROSS, True), (Button.CROSS, False),
            (Button.CROSS, True), (Button.CROSS, False),
        ))).buttons[Button.CROSS]
        self.assertFalse(button.toggled)
        self.assertTrue(button.pressed and button.released)

    def test_snapshot_is_immutable_and_retained_across_updates(self):
        state = self.controller.update(reading(Button.L1))
        self.controller.update(reading())
        self.assertTrue(state.buttons[Button.L1].held)
        with self.assertRaises(TypeError):
            state.buttons[Button.L1] = None

    def test_disconnect_neutralizes_everything_and_resets_toggles(self):
        self.controller.update(reading(Button.L1, left_stick=Stick(1, 1), l2=1))
        state = self.controller.update(RawInput())
        self.assertFalse(state.connected)
        self.assertEqual(state.left_stick, Stick())
        self.assertEqual(state.l2, 0)
        self.assertTrue(state.buttons[Button.L1].released)
        self.assertFalse(any(b.held or b.toggled for b in state.buttons.values()))
        self.assertFalse(self.controller.update(RawInput()).buttons[Button.L1].released)

    def test_connection_with_held_button_does_not_generate_press(self):
        state = self.controller.update(RawInput(connected=True, device_id="new", held=frozenset({Button.PS})))
        self.assertTrue(state.buttons[Button.PS].held)
        self.assertFalse(state.buttons[Button.PS].pressed or state.buttons[Button.PS].toggled)
        self.controller.update(RawInput(connected=True, device_id="new"))
        self.assertTrue(self.controller.update(RawInput(
            connected=True, device_id="new", held=frozenset({Button.PS})
        )).buttons[Button.PS].pressed)

    def test_radial_deadzone_and_diagonal_limit(self):
        self.assertEqual(apply_deadzone(Stick(.05, .04), .1), Stick())
        self.assertAlmostEqual(apply_deadzone(Stick(.55, 0), .1).x, .5)
        diagonal = apply_deadzone(Stick(1, 1), .1)
        self.assertAlmostEqual(math.hypot(diagonal.x, diagonal.y), 1)
        self.assertEqual(apply_deadzone(Stick(float("nan"), 0), .1), Stick())

    def test_triggers_are_clamped_and_independent(self):
        state = self.controller.update(reading(l2=-1, r2=2))
        self.assertEqual((state.l2, state.r2), (0, 1))
        for invalid in (-.1, 1, float("nan")):
            with self.assertRaises(ValueError):
                PS4Controller(invalid)


if __name__ == "__main__":
    unittest.main()
