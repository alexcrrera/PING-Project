"""Orientation instrument geometry, cardinal directions and unavailable data."""

import math
import re
import unittest
from xml.etree import ElementTree as ET

from ping_base.orientation import heading_indicator, pitch_indicator, roll_indicator


def group(svg, role):
    return next((element for element in ET.fromstring(svg).iter()
                 if element.attrib.get('data-role') == role), None)


def rotation(svg, role):
    transform = group(svg, role).attrib['transform']
    return tuple(float(value) for value in re.findall(r'-?\d+(?:\.\d+)?', transform))


class OrientationTests(unittest.TestCase):
    def test_indicators_are_accessible_self_contained_svg(self):
        for svg in (pitch_indicator(7.5), roll_indicator(-3), heading_indicator(95, 310)):
            root = ET.fromstring(svg)
            self.assertEqual(root.attrib['viewBox'], '0 0 120 120')
            self.assertEqual(root.attrib['role'], 'img')
            self.assertTrue(root.attrib['aria-label'])
            self.assertFalse(any('id' in element.attrib for element in root.iter()))
            self.assertNotIn('href', svg)

    def test_positive_pitch_raises_the_right_facing_nose(self):
        angle, cx, cy = rotation(pitch_indicator(30), 'vehicle')
        self.assertEqual((cx, cy), (60, 54))
        # The nose starts to the right of the pivot. In SVG, decreasing y is up.
        nose_y = cy + 25 * math.sin(math.radians(angle))
        self.assertLess(nose_y, cy)
        self.assertGreater(rotation(pitch_indicator(-30), 'vehicle')[0], 0)

    def test_positive_roll_lowers_vehicle_right_at_the_left_of_front_view(self):
        angle, _, cy = rotation(roll_indicator(20), 'vehicle')
        right_wheel_y = cy - 25 * math.sin(math.radians(angle))
        self.assertGreater(right_wheel_y, cy)
        self.assertGreater(rotation(roll_indicator(-20), 'vehicle')[0], 0)

    def test_north_up_cardinal_headings_match_screen_directions(self):
        for heading, expected in ((0, (0, -1)), (90, (1, 0)), (180, (0, 1)), (270, (-1, 0))):
            with self.subTest(heading=heading):
                svg = heading_indicator(heading, heading)
                for role in ('vehicle', 'camera'):
                    angle, cx, cy = rotation(svg, role)
                    self.assertEqual((cx, cy), (60, 60))
                    direction = math.sin(math.radians(angle)), -math.cos(math.radians(angle))
                    self.assertAlmostEqual(direction[0], expected[0])
                    self.assertAlmostEqual(direction[1], expected[1])

    def test_camera_and_body_rotate_independently_with_fixed_compass(self):
        first = heading_indicator(90, 0)
        second = heading_indicator(180, 0)
        self.assertNotEqual(rotation(first, 'vehicle'), rotation(second, 'vehicle'))
        self.assertEqual(rotation(first, 'camera'), rotation(second, 'camera'))
        self.assertIsNone(group(first, 'compass').attrib.get('transform'))
        self.assertIn('Vehicle heading 90.0 degrees', ET.fromstring(first).attrib['aria-label'])
        self.assertIn('Camera heading 0.0 degrees', ET.fromstring(first).attrib['aria-label'])

    def test_heading_wrap_is_normalized(self):
        self.assertEqual(rotation(heading_indicator(360, -360), 'vehicle')[0], 0)
        self.assertEqual(rotation(heading_indicator(-1, 721), 'vehicle')[0], 359)
        self.assertEqual(rotation(heading_indicator(-1, 721), 'camera')[0], 1)

    def test_missing_camera_keeps_vehicle_heading_without_inventing_camera_pose(self):
        svg = heading_indicator(90, None)
        self.assertIsNotNone(group(svg, 'vehicle'))
        self.assertIsNone(group(svg, 'camera'))
        self.assertIn('Camera heading unavailable', ET.fromstring(svg).attrib['aria-label'])

    def test_missing_or_nonfinite_values_never_draw_live_orientation(self):
        for invalid in (None, True, '90', float('nan'), float('inf'), float('-inf')):
            with self.subTest(value=invalid):
                for svg in (pitch_indicator(invalid), roll_indicator(invalid),
                            heading_indicator(invalid, invalid)):
                    self.assertIsNone(group(svg, 'vehicle'))
                    self.assertIsNone(group(svg, 'camera'))
                    self.assertIn('unavailable', ET.fromstring(svg).attrib['aria-label'])
                    self.assertNotIn('nan', svg.lower())
                    self.assertNotIn('inf', svg.lower())


if __name__ == '__main__':
    unittest.main()
