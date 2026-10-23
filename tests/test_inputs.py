import os
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import unittest
from unittest.mock import Mock, patch

import pygame

from ping_base.controller import Button, PS4Controller, Stick
from ping_base.inputs import KeyboardInput, PygamePS4Input, normalize_axis, normalize_trigger


class InputTests(unittest.TestCase):
    def fake_device(self, instance_id=42):
        device = Mock()
        device.name = "PS4 Controller"
        device.attached.return_value = True
        device.as_joystick.return_value.get_instance_id.return_value = instance_id
        device.get_mapping.return_value = {"touchpad": "b15"}
        device.get_axis.return_value = 0
        device.get_button.return_value = False
        return device

    def connect(self, fake_sdl, device):
        fake_sdl.get_count.return_value = 1
        fake_sdl.is_controller.return_value = True
        fake_sdl.name_forindex.return_value = "PS4 Controller"
        fake_sdl.Controller.return_value = device
        source = PygamePS4Input()
        self.assertTrue(source.read([]).connected)
        return source

    @patch("ping_base.inputs.sdl")
    def test_sdl_mapping_axes_and_trigger_threshold(self, fake_sdl):
        device = self.fake_device()
        source = self.connect(fake_sdl, device)
        device.get_button.side_effect = lambda code: code in (pygame.CONTROLLER_BUTTON_A, 20)
        device.get_axis.side_effect = lambda axis: {
            pygame.CONTROLLER_AXIS_LEFTX: -32768,
            pygame.CONTROLLER_AXIS_RIGHTY: 32767,
            pygame.CONTROLLER_AXIS_TRIGGERLEFT: 20000,
        }.get(axis, 0)
        state = source.read([])
        self.assertEqual(state.held, frozenset({Button.CROSS, Button.L2, Button.TOUCHPAD}))
        self.assertEqual(state.left_stick, Stick(-1, 0))
        self.assertEqual(state.right_stick, Stick(0, 1))
        self.assertAlmostEqual(state.l2, 20000/32767)

    @patch("ping_base.inputs.sdl")
    def test_events_are_filtered_by_instance_and_short_taps_survive(self, fake_sdl):
        source = self.connect(fake_sdl, self.fake_device())
        model = PS4Controller()
        model.update(source.read([]))
        events = [pygame.event.Event(kind, instance_id=instance, button=pygame.CONTROLLER_BUTTON_A)
                  for kind, instance in [(pygame.CONTROLLERBUTTONDOWN, 99),
                                         (pygame.CONTROLLERBUTTONDOWN, 42),
                                         (pygame.CONTROLLERBUTTONUP, 42)]]
        button = model.update(source.read(events)).buttons[Button.CROSS]
        self.assertTrue(button.pressed and button.released and button.toggled)
        self.assertFalse(button.held)

    @patch("ping_base.inputs.sdl")
    def test_disconnect_then_reconnect_tracks_new_instance(self, fake_sdl):
        first = self.fake_device()
        source = self.connect(fake_sdl, first)
        first.attached.return_value = False
        self.assertFalse(source.read([]).connected)
        first.quit.assert_called_once()
        fake_sdl.Controller.return_value = self.fake_device(73)
        self.assertEqual(source.read([]).device_id, "73")

    @patch("ping_base.inputs.sdl")
    def test_missing_mapping_and_device_errors_remain_disconnected(self, fake_sdl):
        fake_sdl.get_count.return_value = 1
        fake_sdl.is_controller.return_value = False
        source = PygamePS4Input()
        self.assertFalse(source.read([]).connected)
        fake_sdl.Controller.assert_not_called()
        device = self.fake_device()
        source = self.connect(fake_sdl, device)
        device.get_axis.side_effect = pygame.error("unplugged")
        self.assertFalse(source.read([]).connected)
        self.assertIn("unplugged", source.status)

    @patch("ping_base.inputs.sdl")
    def test_auto_selection_skips_unrelated_gamepad(self, fake_sdl):
        fake_sdl.get_count.return_value = 1
        fake_sdl.is_controller.return_value = True
        fake_sdl.name_forindex.return_value = "Xbox Wireless Controller"
        source = PygamePS4Input()
        self.assertFalse(source.read([]).connected)
        fake_sdl.Controller.assert_not_called()
        fake_sdl.Controller.return_value = self.fake_device()
        self.assertTrue(PygamePS4Input(device_index=0).read([]).connected)

    def test_signed_axis_and_trigger_extremes(self):
        self.assertEqual([normalize_axis(x) for x in (-32768, 0, 32767)], [-1, 0, 1])
        self.assertEqual([normalize_trigger(x) for x in (-1, 0, 32767, 32768)], [0, 0, 1, 1])

    def test_demo_short_tap_key_repeat_and_focus_loss(self):
        source = KeyboardInput()
        model = PS4Controller()
        model.update(source.read([]))
        events = [pygame.event.Event(kind, key=pygame.K_j) for kind in
                  (pygame.KEYDOWN, pygame.KEYDOWN, pygame.KEYUP)]
        button = model.update(source.read(events)).buttons[Button.CROSS]
        self.assertTrue(button.pressed and button.released and button.toggled)
        source.read([pygame.event.Event(pygame.KEYDOWN, key=pygame.K_d),
                     pygame.event.Event(pygame.KEYDOWN, key=pygame.K_q)])
        released = source.read([pygame.event.Event(pygame.WINDOWFOCUSLOST)])
        self.assertEqual(released.left_stick, Stick())
        self.assertFalse(released.held)
        self.assertIn((Button.L1, False), released.changes)


if __name__ == "__main__":
    unittest.main()
