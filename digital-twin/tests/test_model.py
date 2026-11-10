"""Behavioral checks for the independent rover experiment model."""

import unittest
import tempfile
import json
from math import cos, radians
from pathlib import Path
from types import SimpleNamespace
import time

from ping_twin.model import DigitalTwin, MOTORS
from ping_twin.settings import VehicleSettings
from ping_twin.view import TwinPage
from ping_twin.view import rod_rotation
from nicegui.elements.scene.scene_object3d import Object3D


class DigitalTwinTests(unittest.TestCase):
    def test_presets_and_configuration_are_independent_of_motion(self):
        self.assertEqual(set(MOTORS), {"50:1", "70:1", "100:1"})
        self.assertEqual(MOTORS["100:1"].ratio, 102.08)
        twin = DigitalTwin()
        twin.configure(motor="50:1", mass_kg=17, wheel_diameter_m=.32)
        self.assertEqual(twin.config.mass_kg, 17)
        self.assertEqual(twin.state.y_m, 0)
        with self.assertRaises(ValueError):
            twin.configure(mass_kg=0)

    def test_drive_produces_wheel_and_ground_truth_separately(self):
        twin = DigitalTwin()
        for _ in range(100):
            twin.step(.01, .6, 0)
        self.assertGreater(twin.state.y_m, 0)
        self.assertGreater(twin.state.vx_mps, 0)
        self.assertTrue(all(current > 0 for current in twin.state.motor_current_a))
        self.assertTrue(any(abs(slip) > .001 for slip in twin.state.slip_mps))
        twin.reset()
        self.assertEqual(twin.state.y_m, 0)

    def test_terrain_zones_and_obstacle_height_follow_configuration(self):
        twin = DigitalTwin()
        self.assertEqual(twin.terrain(0, 2)[2], "low traction")
        self.assertEqual(twin.terrain(0, 5)[2], "high traction")
        twin.configure(rock_height_m=.23, stair_height_m=.12)
        self.assertAlmostEqual(twin.terrain(0, 7)[0], .23)
        self.assertAlmostEqual(twin.terrain(0, 9.1)[0], .12)

    def test_arm_geometry_determines_axle_spacing(self):
        twin = DigitalTwin()
        before = list(twin._wheel_places(0, 0, 0))
        twin.configure(front_arm_deg=60)
        after = list(twin._wheel_places(0, 0, 0))
        self.assertGreater(after[0][1], before[0][1])
        self.assertEqual(after[2][1], before[2][1])
        self.assertAlmostEqual(after[0][1] - after[2][1], twin.config.wheelbase_m)
        self.assertNotIn("wheelbase_m", twin.config.__dict__)

    def test_joint_offset_moves_straight_arms_and_wheel_track(self):
        twin = DigitalTwin()
        twin.configure(body_width_m=.2, joint_offset_m=.21)
        self.assertAlmostEqual(twin.config.track_m, .62)
        self.assertNotIn("track_m", twin.config.__dict__)
        for side in (-1, 1):
            body_side, pivot = twin.config.joint_connection(side)
            self.assertAlmostEqual(abs(pivot[0] - body_side[0]), .21)
            for fore in (-1, 1):
                arm_start, hub = twin.config.arm_endpoints(side, fore)
                self.assertEqual(arm_start, pivot)
                self.assertEqual(arm_start[0], hub[0])
        with self.assertRaises(ValueError):
            twin.configure(joint_offset_m=-.01)

    def test_box_centre_height_is_derived_from_arms(self):
        twin = DigitalTwin()
        self.assertNotIn("cg_height_m", twin.config.__dict__)
        self.assertAlmostEqual(twin.config.body_center_above_axle_m,
                               twin.config.arm_length_m * cos(radians(30)))
        twin.configure(front_arm_deg=60)
        self.assertLess(twin.config.body_center_above_axle_m,
                        twin.config.arm_length_m * cos(radians(30)))
        for side in (-1, 1):
            for fore in (-1, 1):
                pivot, hub = twin.config.arm_endpoints(side, fore)
                self.assertEqual(pivot[1], 0)
                self.assertAlmostEqual(pivot[2], twin.config.wheel_diameter_m / 2 +
                                       twin.config.body_center_above_axle_m)
                self.assertEqual(hub, twin.config.wheel_offset(side, fore))

    def test_rendered_arm_axis_reaches_both_endpoints(self):
        twin = DigitalTwin()
        twin.configure(body_width_m=.2, joint_offset_m=.21, arm_length_m=.2,
                       front_arm_deg=30, rear_arm_deg=45)
        for side in (-1, 1):
            for fore in (-1, 1):
                a, b = twin.config.arm_endpoints(side, fore)
                rotation = Object3D.rotation_matrix_from_euler(*rod_rotation(a, b))
                length = sum((b[i] - a[i]) ** 2 for i in range(3)) ** .5
                for i in range(3):
                    self.assertAlmostEqual(rotation[i][1] * length, b[i] - a[i])

    def test_rock_blocks_small_wheels_but_larger_wheels_clear_the_edge(self):
        twin = DigitalTwin()
        for _ in range(1200):
            twin.step(.01, 1, 0)
        self.assertTrue(twin.state.blocked)
        self.assertLess(twin.state.y_m, 6.6)
        small_wheel_position = twin.state.y_m
        twin.configure(wheel_diameter_m=.5)
        for _ in range(5):
            twin.step(.01, 1, 0)
        self.assertFalse(twin.state.blocked)
        self.assertGreater(twin.state.y_m, small_wheel_position)

    def test_vehicle_settings_survive_reload_and_ignore_invalid_file(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            path = Path(directory) / "vehicle-settings.json"
            settings = VehicleSettings(path)
            twin = DigitalTwin()
            twin.configure(motor="100:1", mass_kg=19, low_mu=.22)
            settings.save(twin.config)
            restored = settings.load()
            self.assertEqual(restored.motor, "100:1")
            self.assertEqual(restored.mass_kg, 19)
            self.assertEqual(restored.low_mu, .22)
            legacy = json.loads(path.read_text(encoding="utf-8"))
            legacy["cg_height_m"] = .5
            legacy["wheelbase_m"] = 1.2
            legacy["track_m"] = .71
            legacy.pop("joint_offset_m")
            path.write_text(json.dumps(legacy), encoding="utf-8")
            self.assertEqual(settings.load().mass_kg, 19)
            self.assertAlmostEqual(settings.load().track_m, .71)
            settings.save(settings.load())
            self.assertNotIn("cg_height_m", json.loads(path.read_text(encoding="utf-8")))
            self.assertNotIn("wheelbase_m", json.loads(path.read_text(encoding="utf-8")))
            self.assertNotIn("track_m", json.loads(path.read_text(encoding="utf-8")))
            path.write_text('{"mass_kg": NaN}', encoding="utf-8")
            self.assertEqual(settings.load().mass_kg, 12)

    def test_keyboard_overrides_sliders_only_while_keys_are_fresh(self):
        page = TwinPage.__new__(TwinPage)
        page.running = True
        page.throttle, page.steer = .25, -.3
        page.keyboard_throttle = page.keyboard_steer = 0.
        page.keyboard_throttle_active = page.keyboard_steer_active = False
        page.keyboard_last_at = 0.
        page._keyboard_event(SimpleNamespace(args={
            "throttle": 1, "steer": 1,
            "throttle_active": True, "steer_active": True,
        }))
        self.assertEqual(page._drive_inputs(time.monotonic()), (1., 1.))
        self.assertEqual(page._drive_inputs(page.keyboard_last_at + 1), (.25, -.3))
        page._keyboard_event(SimpleNamespace(args={"release": True}))
        self.assertEqual(page._drive_inputs(time.monotonic()), (.25, -.3))

    def test_new_wasd_press_starts_but_heartbeat_does_not_cancel_pause(self):
        page = TwinPage.__new__(TwinPage)
        page.running = False
        page.keyboard_throttle_active = page.keyboard_steer_active = False
        page.run_button = SimpleNamespace(set_text=lambda value: None, props=lambda value: None)
        pressed = SimpleNamespace(args={
            "throttle": 1, "steer": 0,
            "throttle_active": True, "steer_active": False,
        })
        page._keyboard_event(pressed)
        self.assertTrue(page.running)
        page._toggle()  # user presses Pause while W remains held
        page._keyboard_event(pressed)  # heartbeat from the held key
        self.assertFalse(page.running)


if __name__ == "__main__":
    unittest.main()
