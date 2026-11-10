"""Camera HUD heading tracking, cardinal wrap and local vector artwork."""

import re
import unittest
from xml.etree import ElementTree as ET

from ping_base.gimbal import GimbalPose, VirtualGimbal
from ping_base.hud import TACTICAL_RETICLE, gimbal_indicator, heading_tape, range_readout


def ticks(svg):
    return {int(element.attrib['data-bearing']): element
            for element in ET.fromstring(svg).iter()
            if element.attrib.get('data-role') == 'tick'}


def tick_x(element):
    return float(re.search(r'translate\(([-\d.]+)', element.attrib['transform']).group(1))


class HUDTests(unittest.TestCase):
    def test_rangefinder_readout_includes_ten_meters_and_blanks_other_returns(self):
        self.assertEqual(range_readout(4.125), '4.12 m')
        self.assertEqual(range_readout(10), '10.00 m')
        for invalid in (None, True, '5', -1, 10.001, float('nan'), float('inf')):
            with self.subTest(value=invalid):
                self.assertEqual(range_readout(invalid), '---- m')

    def test_heading_tape_is_accessible_and_self_contained(self):
        root = ET.fromstring(heading_tape(214.9))
        self.assertEqual(root.attrib['viewBox'], '0 0 320 64')
        self.assertEqual(root.attrib['role'], 'img')
        self.assertIn('214.9°', root.attrib['aria-label'])
        self.assertFalse(any('id' in element.attrib for element in root.iter()))
        self.assertNotIn('href', heading_tape(214.9))

    def test_each_cardinal_centers_at_its_world_bearing(self):
        for bearing, name in ((0, 'N'), (45, 'NE'), (90, 'E'), (135, 'SE'),
                              (180, 'S'), (225, 'SW'), (270, 'W'), (315, 'NW')):
            with self.subTest(bearing=bearing):
                tick = ticks(heading_tape(bearing))[bearing]
                self.assertEqual(tick_x(tick), 160)
                self.assertIn(name, ''.join(tick.itertext()))

    def test_heading_change_scrolls_bearings_left_beneath_fixed_index(self):
        first, second = heading_tape(60), heading_tape(70)
        self.assertAlmostEqual(tick_x(ticks(first)[90]) - tick_x(ticks(second)[90]), 23)
        index = lambda svg: next(e.attrib['d'] for e in ET.fromstring(svg).iter()
                                 if e.attrib.get('data-role') == 'heading-index')
        self.assertEqual(index(first), index(second))

    def test_north_wrap_has_no_jump_or_duplicate_bearing(self):
        left, right = ticks(heading_tape(359)), ticks(heading_tape(1))
        self.assertAlmostEqual(tick_x(left[0]), 162.3)
        self.assertAlmostEqual(tick_x(right[0]), 157.7)
        self.assertIn(345, left)
        self.assertIn(15, right)
        self.assertEqual(heading_tape(-1), heading_tape(359))
        self.assertEqual(heading_tape(721), heading_tape(1))

    def test_fractional_heading_is_preserved_and_readout_wraps_to_zero(self):
        svg = heading_tape(214.9)
        self.assertAlmostEqual(tick_x(ticks(svg)[210]), 148.73)
        self.assertIn('214.9°', svg)
        self.assertIn('000.0°', heading_tape(359.99))

    def test_missing_or_invalid_heading_has_no_live_scale(self):
        for invalid in (None, True, '90', float('nan'), float('inf'), float('-inf')):
            with self.subTest(value=invalid):
                svg = heading_tape(invalid)
                self.assertFalse(ticks(svg))
                self.assertIn('unavailable', ET.fromstring(svg).attrib['aria-label'])
                self.assertNotIn('nan', svg.lower())
                self.assertNotIn('inf', svg.lower())

    def test_gimbal_indicator_centers_at_home_and_tracks_each_axis(self):
        for pose, coordinates in (
            (GimbalPose(), (64, 24)),
            (GimbalPose(yaw_deg=VirtualGimbal.YAW_LIMIT), (120, 24)),
            (GimbalPose(pitch_deg=VirtualGimbal.PITCH_LIMIT), (64, 8)),
            (GimbalPose(-VirtualGimbal.YAW_LIMIT, -VirtualGimbal.PITCH_LIMIT), (8, 40)),
            (GimbalPose(90, -30, 10), (92, 32)),
        ):
            with self.subTest(pose=pose):
                root = ET.fromstring(gimbal_indicator(pose))
                point = next(e for e in root.iter() if e.get('data-role') == 'gimbal-point')
                self.assertEqual((float(point.get('cx')), float(point.get('cy'))), coordinates)

    def test_reticle_has_matching_dark_outline_and_green_detail(self):
        root = ET.fromstring(TACTICAL_RETICLE)
        self.assertEqual(root.attrib['viewBox'], '0 0 160 120')
        groups = list(root)
        self.assertGreater(float(groups[0].attrib['stroke-width']), float(groups[1].attrib['stroke-width']))
        self.assertEqual([e.attrib for e in groups[0]], [e.attrib for e in groups[1]])
        self.assertFalse(any(element.tag.endswith('text') for element in root.iter()))


if __name__ == '__main__':
    unittest.main()
