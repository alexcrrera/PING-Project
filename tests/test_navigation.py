"""Simulated geolocation, offline map bearings and stale-position behavior."""

import math
import re
import unittest
from xml.etree import ElementTree as ET

from ping_base.navigation import (JUSSIEU_LAT, JUSSIEU_LON, MAP_ZOOM_LEVELS, METERS_PER_DEGREE,
                                  campus_map, simulated_position)


def element(svg, role):
    return next((item for item in ET.fromstring(svg).iter()
                 if item.attrib.get('data-role') == role), None)


def transform_numbers(svg, role):
    return [float(number) for number in re.findall(r'-?\d+(?:\.\d+)?', element(svg, role).attrib['transform'])]


class NavigationTests(unittest.TestCase):
    def test_origin_is_the_published_jussieu_coordinate(self):
        position = simulated_position(0, 0)
        self.assertEqual(position.lat_deg, JUSSIEU_LAT)
        self.assertEqual(position.lon_deg, JUSSIEU_LON)
        self.assertAlmostEqual(position.lat_deg, 48.84586370113)
        self.assertAlmostEqual(position.lon_deg, 2.3567370576704)

    def test_local_motion_moves_gps_east_and_north_in_meters(self):
        origin = simulated_position(0, 0)
        east, north = simulated_position(100, 0), simulated_position(0, 100)
        self.assertEqual(east.lat_deg, origin.lat_deg)
        self.assertEqual(north.lon_deg, origin.lon_deg)
        self.assertAlmostEqual((north.lat_deg - origin.lat_deg) * METERS_PER_DEGREE, 100)
        self.assertAlmostEqual((east.lon_deg - origin.lon_deg) * METERS_PER_DEGREE
                               * math.cos(math.radians(origin.lat_deg)), 100)

    def test_invalid_gps_coordinates_are_rejected(self):
        for invalid in (None, True, '1', float('nan'), float('inf')):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                simulated_position(invalid, 0)

    def test_map_is_local_accessible_square_with_source_attribution(self):
        svg = campus_map(0, 0, 0, 20)
        root = ET.fromstring(svg)
        self.assertEqual(root.attrib['viewBox'], '0 0 400 400')
        self.assertEqual(root.attrib['role'], 'img')
        self.assertIn('Latitude 48.845864', root.attrib['aria-label'])
        self.assertIn('OpenStreetMap contributors', svg)
        self.assertIn('ZAMANSKY', svg)
        self.assertIn('RUE JUSSIEU', svg)
        self.assertNotIn('href=', svg)

    def test_rover_and_camera_cardinal_bearings_are_independent(self):
        for heading, expected in ((0, (0, -1)), (90, (1, 0)), (180, (0, 1)), (270, (-1, 0))):
            with self.subTest(heading=heading):
                svg = campus_map(0, 0, heading, 15)
                angle = transform_numbers(svg, 'vehicle')[-1]
                self.assertAlmostEqual(math.sin(math.radians(angle)), expected[0])
                self.assertAlmostEqual(-math.cos(math.radians(angle)), expected[1])
                self.assertEqual(transform_numbers(svg, 'camera')[-1], 15)
        svg = campus_map(0, 0, 360, -1)
        self.assertEqual(transform_numbers(svg, 'vehicle')[-1], 0)
        self.assertEqual(transform_numbers(svg, 'camera')[-1], 359)

    def test_map_moves_marker_east_and_north_without_rotating_basemap(self):
        origin = campus_map(0, 0, 0, 0)
        east = campus_map(10, 0, 90, 0)
        north = campus_map(0, 10, 0, 90)
        self.assertEqual(element(origin, 'basemap').attrib['transform'], element(east, 'basemap').attrib['transform'])
        self.assertGreater(transform_numbers(east, 'vehicle')[0], transform_numbers(origin, 'vehicle')[0])
        self.assertLess(transform_numbers(north, 'vehicle')[1], transform_numbers(origin, 'vehicle')[1])

    def test_long_roaming_pans_geography_and_preserves_actual_fix(self):
        origin, distant = campus_map(0, 0, 0, 0), campus_map(2000, 3000, 90, 20)
        self.assertNotEqual(element(origin, 'basemap').attrib['transform'], element(distant, 'basemap').attrib['transform'])
        x, y, _ = transform_numbers(distant, 'vehicle')
        self.assertTrue(0 < x < 400 and 0 < y < 400)
        position = simulated_position(2000, 3000)
        self.assertIn(f'Latitude {position.lat_deg:.6f}', distant)
        self.assertIn('OUTSIDE CACHED CAMPUS AREA', distant)

    def test_missing_fix_removes_live_markers_and_missing_heading_keeps_position(self):
        for invalid in (None, True, float('nan'), float('inf')):
            with self.subTest(invalid=invalid):
                svg = campus_map(invalid, 0, 90, 45)
                self.assertIsNone(element(svg, 'vehicle'))
                self.assertIsNone(element(svg, 'camera'))
                self.assertIn('position unavailable', svg)
        svg = campus_map(0, 0, None, None)
        self.assertIsNotNone(element(svg, 'position'))
        self.assertIsNone(element(svg, 'camera'))

    def test_track_uses_valid_points_and_is_bounded(self):
        svg = campus_map(0, 0, 0, None, trail=tuple((i, 0) for i in range(500)))
        track = element(svg, 'trail')
        self.assertEqual(track.attrib['d'].count('L'), 255)
        self.assertTrue(track.attrib['d'].startswith('M244.0,'))
        svg = campus_map(0, 0, 0, None, trail=((0, 0), (float('nan'), 0), (10, 10)))
        self.assertNotIn('nan', svg.lower())
        self.assertEqual(element(svg, 'trail').attrib['d'].count('L'), 1)

    def test_zoom_changes_geography_scale_while_retaining_rover_and_camera_alignment(self):
        original = campus_map(25, 15, 90, 30)
        original_scale = transform_numbers(original, 'basemap')[-1]
        position = transform_numbers(original, 'vehicle')[:2]
        for zoom in MAP_ZOOM_LEVELS:
            with self.subTest(zoom=zoom):
                svg = campus_map(25, 15, 90, 30, trail=((0, 0), (25, 15)), zoom=zoom)
                self.assertAlmostEqual(transform_numbers(svg, 'basemap')[-1] / original_scale, zoom, places=5)
                self.assertEqual(transform_numbers(svg, 'vehicle')[:2], position)
                self.assertEqual(transform_numbers(svg, 'camera')[:2], position)
                self.assertEqual(transform_numbers(svg, 'vehicle')[-1], 90)
                self.assertEqual(transform_numbers(svg, 'camera')[-1], 30)
                self.assertEqual(element(svg, 'basemap').attrib['transform'], element(svg, 'trail').attrib['transform'])
                self.assertEqual(ET.fromstring(svg).attrib['aria-label'], ET.fromstring(original).attrib['aria-label'])

    def test_scale_bar_remains_an_accurate_ground_distance_at_every_zoom(self):
        for zoom in MAP_ZOOM_LEVELS:
            with self.subTest(zoom=zoom):
                svg = campus_map(0, 0, 0, 0, zoom=zoom)
                scale_bar = element(svg, 'scale-bar')
                meters = float(scale_bar.attrib['data-distance-m'])
                path = next(child for child in scale_bar if child.tag.endswith('path'))
                pixels = float(re.search(r'H([\d.]+)', path.attrib['d']).group(1))
                self.assertAlmostEqual(pixels, meters * transform_numbers(svg, 'basemap')[-1], places=2)
                self.assertIn(f'{meters:g} m', ''.join(scale_bar.itertext()))

    def test_zoom_keeps_a_distant_rover_visible_and_does_not_invent_missing_fixes(self):
        for zoom in MAP_ZOOM_LEVELS:
            svg = campus_map(2000, 3000, 0, 90, zoom=zoom)
            x, y, _ = transform_numbers(svg, 'vehicle')
            self.assertTrue(0 < x < 400 and 0 < y < 400)
            self.assertIsNone(element(campus_map(None, None, 0, 90, zoom=zoom), 'vehicle'))

    def test_invalid_map_zoom_is_rejected(self):
        for zoom in (None, True, '2', 0, -.5, .49, 8.01, float('nan'), float('inf')):
            with self.subTest(zoom=zoom), self.assertRaises(ValueError):
                campus_map(0, 0, 0, 0, zoom=zoom)


if __name__ == '__main__':
    unittest.main()
