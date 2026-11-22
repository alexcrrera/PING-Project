"""Dashboard controls and telemetry rendering without a server or hardware."""

from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, Mock, patch

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
        self.page.map_layer = "street"
        self.page.thunderforest_key = "test-dark"
        self.page.maptiler_key = "test-satellite"
        self.page.map_layer_controls = [Mock()]
        self.page._update_map_element = Mock()

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

    def test_map_layer_control_cycles_and_syncs_buttons(self):
        self.page.map_layer_controls.append(Mock())
        for expected in ("dark", "satellite", "street"):
            self.page.cycle_map_layer()
            self.assertEqual(self.page.map_layer, expected)
            for button in self.page.map_layer_controls:
                button.set_text.assert_called_with(expected.upper())

    def test_expanded_map_registers_all_navigation_metrics(self):
        self.page.values = {}
        self.page._label = Mock(side_effect=lambda key, *args: self.page.values.update({key: Mock()}))
        self.page._map_zoom_buttons = Mock()
        self.page._map_layer_button = Mock()
        self.page._map_wheel_events = Mock()
        with patch("ping_base.dashboard.ui") as uiMock:
            uiMock.element.return_value.classes.return_value.props.return_value = MagicMock()
            uiMock.element.return_value.classes.return_value = MagicMock()
            uiMock.html.return_value.classes.return_value = MagicMock()
            self.page._expanded_map()
        for suffix in ("sats", "error", "speed_error", "tracking"):
            self.assertIn("map_large_" + suffix, self.page.values)

    def test_navigation_uses_live_gnss_and_clears_stale_fix(self):
        self.page._navigation_trail = []
        self.page._navigation_simulated = None
        self.page._last_navigation = None
        self.page.map_mini = Mock()
        self.page.map_large = Mock()
        self.page.map_expanded = True
        motion = SimpleNamespace(x_m=0, y_m=0, heading_deg=0)
        sample = RoverTelemetrySample(received_at=0, latitude_deg=-33.8688,
                                      longitude_deg=151.2093, heading_deg=90,
                                      gnss_horizontal_uncertainty_m=10, gnss_num_sats=12,
                                      gnss_velocity_uncertainty_mps=0.14)
        self.page._refresh_navigation(motion, sample, simulated=False, camera_heading=120)
        content = self.page._update_map_element.call_args_list[-2].args[1]
        self.assertIn('Latitude -33.868800, longitude 151.209300', content)
        self.assertIn('rotate(90.00)', content)
        self.assertIn('data-role="gnss-error"', content)
        self.page._text.assert_any_call("map_sats", "12")
        self.page._text.assert_any_call("map_error", "10.00 m")
        self.page._text.assert_any_call("map_speed_error", "0.14 m/s")
        self.page._text.assert_any_call("map_tracking", "FOLLOW")
        self.assertEqual(self.page._navigation_trail, [(-33.8688, 151.2093)])
        self.page._refresh_navigation(motion, None, simulated=False, camera_heading=None)
        content = self.page._update_map_element.call_args_list[-2].args[1]
        self.assertIn('GPS POSITION UNAVAILABLE', content)
        self.assertNotIn('data-role="vehicle"', content)
        self.assertEqual(self.page._navigation_trail, [])
        self.page._text.assert_any_call("map_sats", "-")
        self.page._text.assert_any_call("map_tracking", "WAITING")

    def test_rover_camera_uses_body_frame_for_live_telemetry(self):
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
