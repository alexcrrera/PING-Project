"""Dashboard controls and telemetry rendering without a server or hardware."""

from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from ping_base.dashboard import CAMERA_ZOOM_LEVELS, Dashboard
from ping_base.gimbal import GimbalPose
from ping_base.navigation import MAP_ZOOM_LEVELS
from ping_base.telemetry.model import RoverTelemetrySample


class DashboardControlTests(unittest.TestCase):
    def setUp(self):
        self.page = object.__new__(Dashboard)
        self.page.camera_zoom_index = 0
        self.page.camera_image = Mock()
        self.page._text = Mock()
        self.page.map_zoom_index = MAP_ZOOM_LEVELS.index(1)
        self.page.map_zoom_controls = [(Mock(), Mock(), Mock())]
        self.page.refresh = Mock()

    def test_directional_camera_zoom_clamps_and_q_still_cycles(self):
        self.page.step_camera_zoom(-1)
        self.assertEqual(self.page.camera_zoom_index, 0)
        self.page.camera_image.style.assert_called_with("transform:scale(1)")
        for zoom in (2, 5, 12, 20, 1):
            self.page.cycle_camera_zoom()
            self.page.camera_image.style.assert_called_with(f"transform:scale({zoom})")
        for _ in range(20):
            self.page.step_camera_zoom(1)
        self.assertEqual(self.page.camera_zoom_index, len(CAMERA_ZOOM_LEVELS) - 1)
        self.page.camera_image.style.assert_called_with("transform:scale(20)")
        self.page.step_camera_zoom(-1)
        self.page.camera_image.style.assert_called_with("transform:scale(12)")
        self.page.step_camera_zoom(1)
        self.page.cycle_camera_zoom()
        self.assertEqual(self.page.camera_zoom_index, 0)

    def test_map_zoom_cycle_wraps_and_updates_both_sets_of_controls(self):
        self.page.map_zoom_controls.append((Mock(), Mock(), Mock()))
        self.page.map_zoom_index = len(MAP_ZOOM_LEVELS) - 1
        self.page.cycle_map_zoom()
        self.assertEqual(self.page.map_zoom_index, 0)
        for zoom_out, reset, zoom_in in self.page.map_zoom_controls:
            zoom_out.set_enabled.assert_called_with(False)
            zoom_in.set_enabled.assert_called_with(True)
            reset.set_text.assert_called_with(f"{MAP_ZOOM_LEVELS[0]:g}×")
        self.page.cycle_map_zoom()
        self.assertEqual(self.page.map_zoom_index, 1)

    def test_rover_camera_uses_body_frame_angles_from_live_telemetry(self):
        virtualPose = GimbalPose(5, 10, 15)
        self.page.station = SimpleNamespace(gimbal=SimpleNamespace(state=virtualPose))
        self.page.rover = Mock()
        sample = RoverTelemetrySample(received_at=0, heading_deg=120, pitch_deg=25,
                                      roll_deg=12, gimbal_pan_deg=-35, gimbal_pitch_deg=20)

        self.page._update_rover_gimbal(sample, simulated=False)
        self.page.rover.update_gimbal.assert_called_with(GimbalPose(-35, 20))

        self.page._update_rover_gimbal(RoverTelemetrySample(received_at=1), simulated=False)
        self.page.rover.update_gimbal.assert_called_with(GimbalPose())

        self.page._update_rover_gimbal(None, simulated=True)
        self.page.rover.update_gimbal.assert_called_with(virtualPose)
