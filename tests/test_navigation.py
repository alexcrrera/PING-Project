"""Simulated geolocation, offline map bearings and stale-position behavior."""

import math
import re
import unittest
from xml.etree import ElementTree as ET

from ping_base.navigation import (JUSSIEU_LAT, JUSSIEU_LON, MAP_ZOOM_LEVELS, METERS_PER_DEGREE,
                                  campus_map, simulated_position, world_map)


def element(svg, role):
    return next((item for item in ET.fromstring(svg).iter()
                 if item.attrib.get('data-role') == role), None)


def transform_numbers(svg, role):
    return [float(number) for number in re.findall(r'-?\d+(?:\.\d+)?', element(svg, role).attrib['transform'])]


class NavigationTests(unittest.TestCase):
    def test_world_map_uses_coordinates_and_handles_dateline(self):
        paris = world_map(48.846, 2.35, 90, 30, trail=((48.845, 2.349), (48.846, 2.35)))
        sydney = world_map(-33.8688, 151.2093, 0, None)
        self.assertIn('tile.openstreetmap.org/17/', paris)
        self.assertIn('Latitude -33.868800, longitude 151.209300', sydney)
        self.assertNotEqual(element(paris, 'basemap')[0].attrib['href'], element(sydney, 'basemap')[0].attrib['href'])
        self.assertIsNotNone(element(paris, 'trail'))
        self.assertEqual(transform_numbers(paris, 'vehicle')[-1], 90)
        wrapped = world_map(0, 180, None, None, trail=((0, 179.999), (0, -179.999)))
        self.assertIsNotNone(element(wrapped, 'trail'))
        for zoom in MAP_ZOOM_LEVELS:
            self.assertIn('tile.openstreetmap.org/', world_map(48, 2, 0, 0, zoom=zoom))

    def test_map_layers_have_distinct_tiles_and_attribution(self):
        for layer, provider, attribution in (("street", "tile.openstreetmap.org", "OpenStreetMap"),
                                             ("dark", "tile.thunderforest.com", "Thunderforest"),
                                             ("satellite", "api.maptiler.com", "MapTiler")):
            with self.subTest(layer=layer):
                svg = world_map(48, 2, 0, 0, layer=layer)
                self.assertIn(provider, svg)
                self.assertIn(attribution, svg)
        with self.assertRaises(ValueError):
            world_map(48, 2, 0, 0, layer="invalid")

    def test_highest_street_zoom_overzooms_existing_tiles(self):
        svg = world_map(48.827305, 2.380116, 0, 0, zoom=8)
        tiles = list(element(svg, 'basemap'))
        self.assertTrue(tiles)
        self.assertTrue(all('/19/' in tile.attrib['href'] for tile in tiles))
        self.assertTrue(all(tile.attrib['width'] == '512' for tile in tiles))

    def test_highest_street_zoom_uses_native_tiles_when_key_available(self):
        svg = world_map(48.827305, 2.380116, 0, 0, zoom=8, thunderforest_key="sample")
        tiles = list(element(svg, 'basemap'))
        self.assertTrue(tiles)
        self.assertTrue(all('tile.thunderforest.com/atlas/20/' in tile.attrib['href'] for tile in tiles))
        self.assertTrue(all(tile.attrib['width'] == '256' for tile in tiles))
        self.assertIn('Thunderforest', svg)

    def test_error_circle_diameter_matches_horizontal_error(self):
        svg = world_map(0, 0, 0, 0, zoom=1, horizontal_error_m=10)
        circle = element(svg, 'gnss-error')
        metersPerPixel = 2 * math.pi * 6378137 / (256 * 2 ** 17)
        self.assertAlmostEqual(2 * float(circle.attrib['r']) * metersPerPixel, 10, places=2)
        for invalid in (None, -1, float('nan')):
            self.assertIsNone(element(world_map(0, 0, 0, 0, horizontal_error_m=invalid), 'gnss-error'))

    def test_gimbal_targets_are_drawn_and_coincident_estimates_share_marker(self):
        svg = world_map(48, 2, 0, 0, targets=((48.00001, 2), (48.00001, 2)))
        self.assertIsNotNone(element(svg, 'target-1'))
        self.assertIsNone(element(svg, 'target-2'))
        self.assertIn('1/2', svg)
        svg = world_map(48, 2, 0, 0, targets=(None, (48.00001, 2)))
        self.assertIsNotNone(element(svg, 'target-2'))
        self.assertIsNone(element(world_map(None, None, 0, 0, targets=((48, 2),)), 'target-1'))

    def test_saved_pins_are_rendered_independently_of_live_target(self):
        svg = world_map(48, 2, 0, 0, pins=((48.0001, 2.0001),))
        self.assertIsNotNone(element(svg, 'pin-1'))
        self.assertIsNone(element(svg, 'target-1'))

    def test_world_map_without_fix_has_no_marker_or_tile_requests(self):
        for lat, lon in ((None, None), (float('nan'), 2), (91, 2), (48, 181)):
            svg = world_map(lat, lon, 0, 0)
            self.assertIn('GPS POSITION UNAVAILABLE', svg)
            self.assertNotIn('tile.openstreetmap.org', svg)
            self.assertIsNone(element(svg, 'vehicle'))
            self.assertIsNone(element(svg, 'camera'))

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
