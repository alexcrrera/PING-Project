"""Exercise actual rendering and the application loop without a desktop window."""

import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import unittest
from unittest.mock import patch

import pygame

from ping_base.app import main
from ping_base.controller import Button, PS4Controller, RawInput, Stick
from ping_base.viewer import BG, ControllerViewer, GREEN, SIZE


class ViewerTests(unittest.TestCase):
    def tearDown(self):
        pygame.quit()

    def test_render_connected_and_disconnected_snapshots(self):
        pygame.font.init()
        surface = pygame.Surface(SIZE)
        viewer = ControllerViewer()
        model = PS4Controller()
        viewer.render(surface, model.state, "Waiting for controller")
        self.assertEqual(tuple(surface.get_at((0, 0)))[:3], BG)
        model.update(RawInput(connected=True, device_id="test"))
        state = model.update(RawInput(
            connected=True, device_id="test", name="Render test",
            held=frozenset({Button.CROSS}), left_stick=Stick(.6, -.3), l2=.75,
        ))
        viewer.render(surface, state, "Demo", demo=True)
        self.assertEqual(tuple(surface.get_at((490, 373)))[:3], GREEN)
        self.assertIs(model.state, state)

    def test_demo_application_processes_input_and_shuts_down(self):
        frames = [
            [pygame.event.Event(pygame.KEYDOWN, key=pygame.K_j)],
            [pygame.event.Event(pygame.KEYUP, key=pygame.K_j)],
            [pygame.event.Event(pygame.QUIT)],
        ]
        with patch("pygame.event.get", side_effect=frames):
            self.assertEqual(main(["--demo"]), 0)
        self.assertFalse(pygame.get_init())

    def test_escape_closes_hardware_viewer_without_a_device(self):
        with patch("pygame.event.get", return_value=[pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE)]):
            self.assertEqual(main([]), 0)


if __name__ == "__main__":
    unittest.main()
