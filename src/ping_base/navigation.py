"""Offline Jussieu basemap and simulated GPS from the rover's local meter pose.

The origin is Sorbonne Universite's published Campus Pierre et Marie Curie
location: https://guideetudiant.sorbonne-universite.fr/vos-campus . Geometry is
a simplified OpenStreetMap extract; source and ODbL attribution are stored in
assets/jussieu_map.json. No tile service or location permission is used.
"""

from dataclasses import dataclass
from functools import lru_cache
from html import escape
from importlib.resources import files
import json
from math import atan2, cos, degrees, floor, hypot, isfinite, log, log2, pi, radians, tan
from urllib.parse import quote


JUSSIEU_LAT = 48.84586370113
JUSSIEU_LON = 2.3567370576704
METERS_PER_DEGREE = 111319.49079327358
MAP_SPAN_M = 620.0
MAP_ZOOM_LEVELS = (.5, 1, 2, 4, 8)
_SCALE = 400 / MAP_SPAN_M
_BASE_CENTER = (-35.0, 130.0)
_MAP_BACKGROUND = '#0c1219'
_ROVER_COLOR = '#a7ff64'
_CAMERA_COLOR = '#ffc166'


@dataclass(frozen=True, slots=True)
class GeoPosition:
    lat_deg: float
    lon_deg: float


def _finite(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and isfinite(value)


def simulated_position(x_m: float, y_m: float) -> GeoPosition:
    """Place local +x east/+y north at Jussieu using a small-area projection."""
    if not _finite(x_m) or not _finite(y_m):
        raise ValueError('Simulated GPS requires finite local coordinates')
    return GeoPosition(JUSSIEU_LAT + y_m / METERS_PER_DEGREE,
                       JUSSIEU_LON + x_m / (METERS_PER_DEGREE * cos(radians(JUSSIEU_LAT))))


def _path(points, *, closed=False) -> str:
    if not points:
        return ''
    return ('M' + 'L'.join(f'{x:.1f},{-y:.1f}' for x, y in points)
            + ('Z' if closed else ''))


@lru_cache(maxsize=1)
def _basemap() -> str:
    data = json.loads(files('ping_base').joinpath('assets/jussieu_map.json').read_text(encoding='utf-8'))
    roads = {kind: [] for kind in ('major', 'minor', 'path')}
    buildings = []
    named = {}
    landmarks = {}
    for feature in data['features']:
        points = feature['points']
        if feature['kind'] == 'building':
            buildings.append(_path(points, closed=True))
            if feature['name'] in ('Tour Zamansky', 'Atrium - CFA'):
                unique = points[:-1] if points[0] == points[-1] else points
                landmarks[feature['name']] = (sum(p[0] for p in unique) / len(unique),
                                                sum(p[1] for p in unique) / len(unique))
            continue
        kind = ('major' if feature['type'] in ('primary', 'tertiary', 'tertiary_link')
                else 'path' if feature['type'] in ('path', 'footway') else 'minor')
        roads[kind].append(_path(points))
        if feature['name'] in ('Rue Jussieu', 'Rue Cuvier', 'Quai Saint-Bernard', 'Rue des Fossés Saint-Bernard'):
            for first, second in zip(points, points[1:]):
                length = hypot(second[0] - first[0], second[1] - first[1])
                if length < 45:
                    continue
                x, y = (first[0] + second[0]) / 2, (first[1] + second[1]) / 2
                score = hypot(x - _BASE_CENTER[0], y - _BASE_CENTER[1])
                if feature['name'] not in named or score < named[feature['name']][0]:
                    angle = degrees(atan2(-(second[1] - first[1]), second[0] - first[0]))
                    if angle > 90:
                        angle -= 180
                    elif angle < -90:
                        angle += 180
                    named[feature['name']] = (score, x, y, angle)
    output = []
    for kind, width, color in (('major', 8, '#a8b7c4'), ('minor', 4, '#667e92'), ('path', 1.8, '#567082')):
        output.append(f'<path d="{"".join(roads[kind])}" stroke="{color}" stroke-width="{width}" '
                      'fill="none" stroke-linecap="round" stroke-linejoin="round"/>')
    output.append(f'<path d="{"".join(buildings)}" fill="#1d2a37" stroke="#53697d" '
                  'stroke-width="1.2" stroke-linejoin="round"/>')
    for name, (_, x, y, angle) in named.items():
        label = name.upper().replace('RUE DES FOSSÉS SAINT-BERNARD', 'R. FOSSÉS ST-BERNARD')
        output.append(f'<text transform="translate({x:.1f} {-y - 5:.1f}) rotate({angle:.1f})" '
                      'fill="#e0ebf4" font-size="13" text-anchor="middle" '
                      f'stroke="{_MAP_BACKGROUND}" stroke-width="3" paint-order="stroke">'
                      f'{escape(label)}</text>')
    for name, (x, y) in landmarks.items():
        label = 'ZAMANSKY' if name == 'Tour Zamansky' else 'ATRIUM'
        output.append(f'<text x="{x:.1f}" y="{-y - 12:.1f}" fill="#c1d6e8" '
                      f'font-size="12" text-anchor="middle" stroke="{_MAP_BACKGROUND}" '
                      f'stroke-width="3" paint-order="stroke">{label}</text>')
    return ''.join(output)


def campus_map(x_m: float | None, y_m: float | None, heading_deg: float | None,
               camera_heading_deg: float | None, trail: tuple[tuple[float, float], ...] = (),
               *, zoom: float = 1) -> str:
    """A fixed-north square map; pan the cached geography when the rover moves.

    The campus frame remains steady during local movement. Beyond its central
    area the map follows the real simulated position rather than clamping the
    marker. Outside cached geometry, only the grid, track and marker remain.
    """
    if not _finite(zoom) or not MAP_ZOOM_LEVELS[0] <= zoom <= MAP_ZOOM_LEVELS[-1]:
        raise ValueError('Map zoom must be between 0.5 and 8')
    scale = _SCALE * zoom
    valid = _finite(x_m) and _finite(y_m)
    cx, cy = _BASE_CENTER
    if valid:
        cx = x_m - max(-190, min(190, x_m - cx))
        cy = y_m - max(-190, min(190, y_m - cy))
        # Zoom around the rover's existing screen position, retaining the same
        # tracking margin at every scale rather than letting it leave the map.
        cx, cy = x_m + (cx - x_m) / zoom, y_m + (cy - y_m) / zoom
    tx, ty = 200 - cx * scale, 200 + cy * scale
    world_transform = f'translate({tx:.2f} {ty:.2f}) scale({scale:.6f})'
    grid = ''.join(f'M{p} 0V400M0 {p}H400' for p in range(0, 401, 40))
    content = (f'<rect width="400" height="400" fill="{_MAP_BACKGROUND}"/>'
               f'<path d="{grid}" stroke="#69859e" opacity=".3" stroke-width=".7"/>'
               f'<g data-role="basemap" transform="{world_transform}">{_basemap()}</g>')
    if valid:
        clean_trail = [point for point in trail[-256:]
                       if isinstance(point, (list, tuple)) and len(point) == 2
                       and all(_finite(value) for value in point)]
        if len(clean_trail) > 1:
            content += (f'<path data-role="trail" transform="{world_transform}" d="{_path(clean_trail)}" '
                        'fill="none" stroke="#65ddff" stroke-width="2.5" stroke-dasharray="4 5" opacity=".9"/>')
        px, py = tx + x_m * scale, ty - y_m * scale
        if _finite(camera_heading_deg):
            content += (f'<g data-role="camera" transform="translate({px:.2f} {py:.2f}) rotate({camera_heading_deg % 360:.2f})" '
                        f'stroke="{_CAMERA_COLOR}" stroke-linejoin="round">'
                        f'<path d="M0 0L-25 -48A54 54 0 0 1 25 -48Z" fill="{_CAMERA_COLOR}" fill-opacity=".16" '
                        'stroke-width="1.5"/><path d="M0 -10V-46M-4 -40L0 -47L4 -40" stroke-width="1.8"/></g>')
        if _finite(heading_deg):
            content += (f'<g data-role="vehicle" transform="translate({px:.2f} {py:.2f}) rotate({heading_deg % 360:.2f})">'
                        f'<circle r="14" fill="{_MAP_BACKGROUND}" stroke="{_ROVER_COLOR}" stroke-opacity=".75"/>'
                        f'<path d="M0 -11L8 9L0 5L-8 9Z" fill="{_ROVER_COLOR}" '
                        f'stroke="{_MAP_BACKGROUND}" stroke-width="1.5"/></g>')
        else:
            content += f'<circle data-role="position" cx="{px:.2f}" cy="{py:.2f}" r="5" fill="{_ROVER_COLOR}"/>'
        if x_m < -400 or x_m > 400 or y_m < -230 or y_m > 590:
            content += ('<rect x="85" y="343" width="230" height="20" fill="#101610" fill-opacity=".88"/>'
                        '<text x="200" y="357" fill="#b5bda7" font-size="9" text-anchor="middle">OUTSIDE CACHED CAMPUS AREA</text>')
        label = 'Jussieu campus map, north up, simulated position. '
        position = simulated_position(x_m, y_m)
        label += f'Latitude {position.lat_deg:.6f}, longitude {position.lon_deg:.6f}.'
    else:
        label = 'Jussieu campus map, north up. Simulated GPS position unavailable.'
        content += ('<rect x="109" y="183" width="182" height="28" fill="#101610" fill-opacity=".9"/>'
                    '<text x="200" y="201" fill="#a6ad9a" font-size="10" text-anchor="middle">GPS POSITION UNAVAILABLE</text>')
    scale_m = max(distance for distance in (1, 2, 5, 10, 20, 50, 100, 200, 500)
                  if distance <= 100 / zoom)
    scale_length = scale_m * scale
    content += ('<g transform="translate(367 27)"><path d="M0 21V-2M-4 5L0 -3L4 5" '
                'stroke="#e8e7df" stroke-width="1.5" fill="none"/>'
                '<text x="0" y="-9" fill="#e8e7df" font-size="10" text-anchor="middle">N</text></g>'
                f'<g data-role="scale-bar" data-distance-m="{scale_m}" transform="translate(19 366)" fill="#d9dfc9" font-size="9">'
                f'<path d="M0 -4V0H{scale_length:.2f}V-4" stroke="#d9dfc9" fill="none"/>'
                f'<text x="{scale_length / 2:.2f}" y="14" text-anchor="middle">{scale_m} m</text></g>'
                '<text x="385" y="388" fill="#88947e" font-size="8" text-anchor="end">© OpenStreetMap contributors</text>')
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 400" role="img" '
            f'aria-label="{escape(label, quote=True)}" font-family="Suisse,Arial,sans-serif">'
            f'<title>{escape(label)}</title>{content}</svg>')


WEB_MERCATOR_MAX_LAT = 85.05112878
MAP_LAYERS = ("street", "dark", "satellite")
MAP_ATTRIBUTION = {
    "street": "© OpenStreetMap contributors",
    "dark": "© Thunderforest, © OpenStreetMap contributors",
    "satellite": "© MapTiler © OpenStreetMap contributors",
}


def world_map(latitude: float | None, longitude: float | None,
              heading_deg: float | None, camera_heading_deg: float | None,
              trail: tuple[tuple[float, float], ...] = (), *, zoom: float = 1,
              layer: str = "street", horizontal_error_m: float | None = None,
              thunderforest_key: str = "", maptiler_key: str = "",
              targets: tuple = (), pins: tuple = ()) -> str:
    """North-up map centered on a geographic fix, using OpenStreetMap tiles.

    Tiles are requested by the browser and require internet access. GPS remains
    useful without a tile connection. Web Mercator is limited to about 85° N/S.
    """
    if zoom not in MAP_ZOOM_LEVELS or isinstance(zoom, bool):
        raise ValueError('Unsupported map zoom')
    if layer not in MAP_LAYERS:
        raise ValueError('Unsupported map layer')
    valid = (_finite(latitude) and _finite(longitude) and
             -90 <= latitude <= 90 and -180 <= longitude <= 180)
    content = f'<rect width="400" height="400" fill="{_MAP_BACKGROUND}"/>'
    if valid:
        level = 17 + int(log2(zoom))
        # OSM standard tiles stop at z19. At z20 use the configured
        # Thunderforest Atlas layer; without a key, enlarge z19 tiles.
        atlasStreet = layer == "street" and level > 19 and bool(thunderforest_key)
        tileLevel = min(level, 19) if layer == "street" and not atlasStreet else level
        tileScale = 2 ** (level - tileLevel)
        tileSize = 256 * tileScale
        tileCount = 1 << tileLevel
        worldSize = tileSize * tileCount

        def project(lat, lon):
            lat = max(-WEB_MERCATOR_MAX_LAT, min(WEB_MERCATOR_MAX_LAT, lat))
            x = ((lon + 180) / 360) * worldSize
            y = (1 - log(tan(pi / 4 + radians(lat) / 2)) / pi) / 2 * worldSize
            return x, y

        centerX, centerY = project(latitude, longitude)
        minX = floor((centerX - 200) / tileSize)
        maxX = floor((centerX + 200) / tileSize)
        minY = max(0, floor((centerY - 200) / tileSize))
        maxY = min(tileCount - 1, floor((centerY + 200) / tileSize))
        content += '<g data-role="basemap">'
        for tileY in range(minY, maxY + 1):
            for tileX in range(minX, maxX + 1):
                x, y = 200 + tileX * tileSize - centerX, 200 + tileY * tileSize - centerY
                tileColumn = tileX % tileCount
                if atlasStreet:
                    url = (f'https://tile.thunderforest.com/atlas/{tileLevel}/{tileColumn}/{tileY}.png'
                           f'?apikey={quote(thunderforest_key, safe="")}')
                elif layer == 'street':
                    url = f'https://tile.openstreetmap.org/{tileLevel}/{tileColumn}/{tileY}.png'
                elif layer == 'dark':
                    url = (f'https://tile.thunderforest.com/transport-dark/{tileLevel}/{tileColumn}/{tileY}.png'
                           f'?apikey={quote(thunderforest_key, safe="")}')
                else:
                    url = (f'https://api.maptiler.com/maps/satellite-v4/{tileLevel}/{tileColumn}/{tileY}.jpg'
                           f'?key={quote(maptiler_key, safe="")}')
                content += (f'<image x="{x:.3f}" y="{y:.3f}" width="{tileSize}" height="{tileSize}" '
                            f'href="{escape(url, quote=True)}" preserveAspectRatio="none"/>')
        content += '</g>'
        points = []
        for point in trail[-256:]:
            if (isinstance(point, (tuple, list)) and len(point) == 2 and
                    all(_finite(value) for value in point) and
                    -90 <= point[0] <= 90 and -180 <= point[1] <= 180):
                x, y = project(*point)
                dx = (x - centerX + worldSize / 2) % worldSize - worldSize / 2
                points.append((200 + dx, 200 + y - centerY))
        if len(points) > 1:
            path = 'M' + 'L'.join(f'{x:.2f},{y:.2f}' for x, y in points)
            content += (f'<path data-role="trail" d="{path}" fill="none" stroke="#00d4ff" '
                        'stroke-width="2.5" stroke-dasharray="4 5"/>')
        metersPerPixel = cos(radians(max(-WEB_MERCATOR_MAX_LAT, min(WEB_MERCATOR_MAX_LAT, latitude)))) * 2 * pi * 6378137 / worldSize
        if _finite(horizontal_error_m) and horizontal_error_m >= 0:
            radius = horizontal_error_m / (2 * metersPerPixel)
            content += (f'<circle data-role="gnss-error" cx="200" cy="200" r="{radius:.3f}" '
                        'fill="#65ddff" fill-opacity=".15" stroke="#65ddff" stroke-width="1.5"/>')
        for index, target in enumerate(targets[:2], 1):
            if (not isinstance(target, (tuple, list)) or len(target) != 2 or
                    not all(_finite(v) for v in target) or abs(target[0]) > 90 or abs(target[1]) > 180):
                continue
            x, y = project(*target)
            dx = (x - centerX + worldSize / 2) % worldSize - worldSize / 2
            px, py = 200 + dx, 200 + y - centerY
            # Coincident estimates share one marker, with both indices.
            if index == 2 and targets[0] == target:
                continue
            markerLabel = '1/2' if index == 1 and len(targets) > 1 and targets[1] == target else str(index)
            content += (f'<g data-role="target-{index}" transform="translate({px:.2f} {py:.2f})">'
                        '<circle r="7" fill="#17160f" stroke="#ffc166" stroke-width="2"/>'
                        f'<circle r="2" fill="#ffc166"/><text x="10" y="-8" fill="#fff" '
                        f'stroke="#111" stroke-width="3" paint-order="stroke" font-size="10">{markerLabel}</text></g>')
        for index, pin in enumerate(pins, 1):
            if (not isinstance(pin, (tuple, list)) or len(pin) != 2 or
                    not all(_finite(v) for v in pin) or abs(pin[0]) > 90 or abs(pin[1]) > 180):
                continue
            x, y = project(*pin)
            dx = (x - centerX + worldSize / 2) % worldSize - worldSize / 2
            px, py = 200 + dx, 200 + y - centerY
            content += (f'<g data-role="pin-{index}" transform="translate({px:.2f} {py:.2f})">'
                        '<path d="M0 0C-3 -5 -7 -8 -7 -12a7 7 0 0 1 14 0C7 -8 3 -5 0 0Z" '
                        'fill="#ff5e56" stroke="#17160f" stroke-width="1.5"/>'
                        f'<text x="9" y="-10" fill="#fff" stroke="#111" stroke-width="3" '
                        f'paint-order="stroke" font-size="10">{index}</text></g>')
        if _finite(camera_heading_deg):
            content += (f'<g data-role="camera" transform="translate(200 200) rotate({camera_heading_deg % 360:.2f})" '
                        f'stroke="{_CAMERA_COLOR}" stroke-linejoin="round">'
                        f'<path d="M0 0L-25 -48A54 54 0 0 1 25 -48Z" fill="{_CAMERA_COLOR}" fill-opacity=".16" '
                        'stroke-width="1.5"/><path d="M0 -10V-46M-4 -40L0 -47L4 -40" stroke-width="1.8"/></g>')
        if _finite(heading_deg):
            content += (f'<g data-role="vehicle" transform="translate(200 200) rotate({heading_deg % 360:.2f})">'
                        f'<circle r="14" fill="{_MAP_BACKGROUND}" stroke="{_ROVER_COLOR}"/>'
                        f'<path d="M0 -11L8 9L0 5L-8 9Z" fill="{_ROVER_COLOR}" stroke="{_MAP_BACKGROUND}" stroke-width="1.5"/></g>')
        else:
            content += f'<circle data-role="position" cx="200" cy="200" r="6" fill="{_ROVER_COLOR}" stroke="{_MAP_BACKGROUND}"/>'
        label = f'Navigation map, north up. Latitude {latitude:.6f}, longitude {longitude:.6f}.'
        if abs(latitude) > WEB_MERCATOR_MAX_LAT:
            label += ' Basemap latitude is limited by Web Mercator.'
        scaleMeters = max((v for v in (0.1, 0.2, 0.5, 1, 2, 5, 10, 20, 50, 100, 200, 500, 1000)
                           if v <= 100 * metersPerPixel), default=0.1)
        scaleLength = scaleMeters / metersPerPixel
        content += (f'<g data-role="scale-bar" transform="translate(19 366)" fill="#fff" font-size="10" '
                    'stroke="#111" paint-order="stroke" stroke-width="3">'
                    f'<path d="M0 -4V0H{scaleLength:.2f}V-4" fill="none" stroke="#111"/>'
                    f'<text x="{scaleLength/2:.2f}" y="14" text-anchor="middle">{scaleMeters:g} m</text></g>')
    else:
        label = 'Navigation map. GPS position unavailable.'
        content += ('<text x="200" y="201" fill="#a6ad9a" font-size="11" text-anchor="middle">'
                    'GPS POSITION UNAVAILABLE</text>')
    attribution = MAP_ATTRIBUTION["dark"] if valid and layer == "street" and atlasStreet else MAP_ATTRIBUTION[layer]
    content += ('<g transform="translate(367 27)"><path d="M0 21V-2M-4 5L0 -3L4 5" '
                'stroke="#fff" stroke-width="2" fill="none"/>'
                '<text x="0" y="-9" fill="#fff" stroke="#111" stroke-width="3" paint-order="stroke" '
                'font-size="10" text-anchor="middle">N</text></g>'
                '<text x="392" y="392" fill="#fff" stroke="#111" stroke-width="3" paint-order="stroke" '
                f'font-size="9" text-anchor="end">{escape(attribution)}</text>')
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 400" role="img" '
            f'aria-label="{escape(label, quote=True)}" font-family="Suisse,Arial,sans-serif">'
            f'<title>{escape(label)}</title>{content}</svg>')
