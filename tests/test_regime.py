import unittest

from ping_base.telemetry.rvr import RoverGroups
from ping_base.orientation import pitch_indicator
from ping_base.dashboard import target_speed_indicator


class RegimeTests(unittest.TestCase):
    def test_regime_decoding_merging_and_expiry(self):
        groups = RoverGroups()
        sample = groups.decode(b'$RVR,RGM,NAVIGATION_NO_TRACTION,1,0.50,2.00,30.00,2500.00,15.00,9999.00,0.0,100.0*', 0)
        self.assertEqual(sample.regime_mode, 'NAVIGATION_NO_TRACTION')
        self.assertEqual(sample.regime_max_velocity_mps, .5)
        self.assertEqual(sample.regime_pitch_roll_limit_deg, 15)
        self.assertTrue(sample.regime_dynamic)
        sample = groups.decode(b'$RVR,ATVL,0,0,0,0,0*', 2)
        self.assertEqual(sample.regime_max_yaw_rate_dps, 30)
        sample = groups.decode(b'$RVR,ATVL,0,0,0,0,0*', 6)
        self.assertIsNone(sample.regime_max_velocity_mps)

    def test_invalid_limits_do_not_replace_last_valid_regime(self):
        groups = RoverGroups()
        groups.decode(b'$RVR,RGM,TRACTION,1,0.5,2,30,2500,15,9999,0,100*', 0)
        with self.assertRaises(ValueError):
            groups.decode(b'$RVR,RGM,TRACTION,1,0.5,2,30,2500,15,9999,90,10*', 1)
        self.assertEqual(groups.latest_frames['RGM'][0], 0)

    def test_instruments_show_limits_and_estimated_speed(self):
        self.assertIn('data-role="tilt-limits"', pitch_indicator(3, 15))
        self.assertIn('+0.45 m/s', target_speed_indicator(.9, .5))
        self.assertIn('#f17168', target_speed_indicator(-.9, .5))
        self.assertIn('— m/s', target_speed_indicator(.5, None))
        self.assertIn('INPUT UNAVAILABLE', target_speed_indicator(None, .5))
