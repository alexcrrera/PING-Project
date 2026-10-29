"""Small local SVG attitude instruments with a fixed north-up compass."""

from html import escape
from math import cos, isfinite, radians, sin


_WHITE = "#e8e7df"
_AMBER = "#b49a50"
_MUTED = "#62655b"
_DARK = "#191a18"


def _number(value: float | None) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value) if isfinite(value) else None


def _svg(label: str, content: str) -> str:
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 120" '
            f'role="img" aria-label="{escape(label, quote=True)}" fill="none">'
            f'<title>{escape(label)}</title>{content}</svg>')


def _attitude_scale() -> str:
    ticks = []
    for angle in range(0, 181, 30):
        a = radians(angle)
        inner = 36 if angle % 90 == 0 else 38
        ticks.append(f'<path d="M{60 + inner * cos(a):.2f},{54 + inner * sin(a):.2f}'
                     f'L{60 + 44 * cos(a):.2f},{54 + 44 * sin(a):.2f}"/>')
    return ('<g data-role="scale" stroke="' + _AMBER + '" stroke-width="1.6">'
            '<path d="M18 54A42 42 0 0 0 102 54"/>' + ''.join(ticks) + '</g>'
            f'<path d="M16 54H104" stroke="{_MUTED}" stroke-dasharray="2 4" '
            'stroke-width=".7" opacity=".7"/>')


def _side_rover() -> str:
    return (f'<g fill="{_WHITE}" stroke="{_WHITE}" stroke-linejoin="round">'
            '<path d="M31 47H80L89 53L85 59H34L28 54Z" stroke-width="1.2"/>'
            '<path d="M39 57L46 63H70L77 57" fill="none" stroke-width="2"/>'
            '<path d="M53 45V35H69" fill="none" stroke-width="2.5"/>'
            '<rect x="57" y="30" width="18" height="9" rx="1.5"/>'
            f'<path d="M76 50L83 53L76 56Z" fill="{_DARK}" stroke="none"/>'
            f'<g fill="{_DARK}" stroke-width="2">'
            '<circle cx="38" cy="61" r="7"/><circle cx="78" cy="61" r="7"/>'
            '</g><g stroke-width="1" opacity=".7">'
            '<path d="M35 61H41M38 58V64M75 61H81M78 58V64"/></g></g>')


def _front_rover() -> str:
    return (f'<g fill="{_WHITE}" stroke="{_WHITE}" stroke-linejoin="round">'
            '<g fill="none" stroke-width="1.3" opacity=".55">'
            '<rect x="32" y="46" width="9" height="18" rx="3"/>'
            '<rect x="79" y="46" width="9" height="18" rx="3"/></g>'
            '<path d="M35 44H85L89 55L82 61H38L31 55Z" stroke-width="1.3"/>'
            '<path d="M60 44V33" stroke-width="3"/>'
            '<rect x="44" y="26" width="32" height="12" rx="2"/>'
            f'<g fill="{_DARK}" stroke="none">'
            '<circle cx="51" cy="32" r="3.2"/><circle cx="69" cy="32" r="3.2"/>'
            '<path d="M43 49H77V53H43Z"/></g>'
            f'<g fill="{_DARK}" stroke-width="2">'
            '<rect x="28" y="51" width="12" height="21" rx="3"/>'
            '<rect x="80" y="51" width="12" height="21" rx="3"/></g>'
            '<path d="M32 57H36M32 63H36M84 57H88M84 63H88" stroke-width="1"/>'
            '</g>')


def _attitude_indicator(value: float | None, name: str, silhouette: str) -> str:
    value = _number(value)
    label = f'{name} {value:+.1f} degrees' if value is not None else f'{name} unavailable'
    scale = _attitude_scale()
    if value is None:
        content = f'<g opacity=".28">{scale}{silhouette}</g>'
        content += f'<path d="M49 104H71" stroke="{_MUTED}" stroke-width="2"/>'
    else:
        content = scale + f'<g data-role="vehicle" transform="rotate({-value:.2f} 60 54)">{silhouette}</g>'
    return _svg(label, content)


def pitch_indicator(pitch: float | None) -> str:
    """Side view, nose pointing right; positive pitch raises the nose."""
    return _attitude_indicator(pitch, 'Pitch', _side_rover())


def roll_indicator(roll: float | None) -> str:
    """Front view; positive right-side-down roll lowers the image's left side."""
    return _attitude_indicator(roll, 'Roll', _front_rover())


def _top_rover() -> str:
    wheels = ''.join(f'<rect x="{x}" y="{y}" width="7" height="13" rx="2"/>'
                     for x in (42, 71) for y in (45, 65))
    return (f'<g fill="{_WHITE}" stroke="{_WHITE}" stroke-width="1.3" '
            'stroke-linejoin="round">' + wheels +
            '<path d="M49 48L54 41H66L71 48V77L67 81H53L49 77Z"/>'
            f'<path d="M53 52H67V72H53Z" fill="{_DARK}" stroke-width=".8"/>'
            '<path d="M56 45L60 39L64 45" stroke-width="2"/>'
            f'<circle cx="60" cy="60" r="4" fill="{_DARK}"/>'
            '</g>')


def heading_indicator(heading: float | None, camera_heading: float | None) -> str:
    """Plan view: north stays up; independent headings rotate clockwise from it."""
    heading, camera_heading = _number(heading), _number(camera_heading)
    if heading is not None:
        heading %= 360
    if camera_heading is not None:
        camera_heading %= 360
    label = 'North up, 0 degrees. '
    label += f'Vehicle heading {heading:.1f} degrees. ' if heading is not None else 'Vehicle heading unavailable. '
    label += f'Camera heading {camera_heading:.1f} degrees.' if camera_heading is not None else 'Camera heading unavailable.'
    ticks = []
    for angle in range(0, 360, 30):
        a = radians(angle)
        inner = 36 if angle % 90 == 0 else 38
        ticks.append(f'<path d="M{60 + inner * sin(a):.2f},{60 - inner * cos(a):.2f}'
                     f'L{60 + 41 * sin(a):.2f},{60 - 41 * cos(a):.2f}"/>')
    compass = (f'<g data-role="compass" stroke="{_AMBER}" stroke-width="1">'
               '<circle cx="60" cy="60" r="40" opacity=".55"/>' + ''.join(ticks) + '</g>'
               f'<g fill="{_MUTED}" font-family="Suisse,Arial,sans-serif" font-size="9" '
               'text-anchor="middle"><text x="60" y="12" fill="' + _AMBER + '">N</text>'
               '<text x="111" y="63">E</text><text x="60" y="115">S</text>'
               '<text x="9" y="63">W</text></g>')
    camera = ''
    if camera_heading is not None:
        camera = (f'<g data-role="camera" transform="rotate({camera_heading:.2f} 60 60)" '
                  f'stroke="{_AMBER}" stroke-linejoin="round">'
                  f'<path d="M60 60L43 27A37 37 0 0 1 77 27Z" fill="{_AMBER}" '
                  'fill-opacity=".14" stroke-width=".8"/>'
                  '<path d="M60 58V23M56 28L60 22L64 28" stroke-width="2"/></g>')
    vehicle = ''
    if heading is not None:
        vehicle = f'<g data-role="vehicle" transform="rotate({heading:.2f} 60 60)">{_top_rover()}</g>'
    if heading is None and camera_heading is None:
        vehicle = (f'<g opacity=".35" stroke="{_MUTED}" stroke-width="1.5">'
                   '<path d="M49 60H71M60 49V71"/><circle cx="60" cy="60" r="16" '
                   'stroke-dasharray="2 4"/></g>')
    return _svg(label, compass + camera + vehicle)
