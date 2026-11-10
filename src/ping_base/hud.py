"""Local camera HUD artwork for heading, gimbal orientation, and aiming."""

from math import ceil, floor, isfinite

from .gimbal import GimbalPose, VirtualGimbal


_CARDINALS = {0: "N", 45: "NE", 90: "E", 135: "SE",
              180: "S", 225: "SW", 270: "W", 315: "NW"}
_PIXELS_PER_DEGREE = 2.3
_HUD_GREEN = "#5dff55"


def range_readout(distance_m: float | None) -> str:
    """The 10 m camera-aligned sensor uses a missing return beyond its limit."""
    if (isinstance(distance_m, bool) or not isinstance(distance_m, (int, float))
            or not isfinite(distance_m) or not 0 <= distance_m <= 10):
        return "---- m"
    return f"{distance_m:.2f} m"


def heading_tape(heading: float | None) -> str:
    """Scroll world bearings beneath a fixed camera-heading index.

    Positive headings turn clockwise from north. Tick positions use unwrapped
    bearings around the current heading, keeping the tape continuous at north.
    """
    valid = (not isinstance(heading, bool) and isinstance(heading, (int, float))
             and isfinite(heading))
    bearing = float(heading) % 360 if valid else None
    readout = f"{round(bearing, 1) % 360:05.1f}°" if bearing is not None else "—"
    label = f"Camera heading {readout}" if bearing is not None else "Camera heading unavailable"
    pieces = [
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 320 64" '
        f'role="img" aria-label="{label}" fill="none">',
        f'<title>{label}</title>',
        '<rect x=".5" y=".5" width="319" height="63" rx="2" '
        'fill="#0c100d" fill-opacity=".78" stroke="#d2d6b9" stroke-opacity=".25"/>',
        '<g font-family="Suisse,Arial,sans-serif" text-anchor="middle" '
        'font-variant-numeric="tabular-nums">',
        '<text x="16" y="15" text-anchor="start" fill="#d2d6b9" '
        'font-size="7" letter-spacing="1">CAM HDG</text>',
        '<text x="304" y="15" text-anchor="end" fill="#d2d6b9" '
        'font-size="7" letter-spacing="1">DEG</text>',
        '<path d="M8 40H312" stroke="#f3f4e9" stroke-opacity=".5" stroke-width=".75"/>',
    ]
    if bearing is not None:
        half_span = 152 / _PIXELS_PER_DEGREE
        start = floor((bearing - half_span) / 5) * 5
        stop = ceil((bearing + half_span) / 5) * 5
        for tick in range(start, stop + 1, 5):
            x = 160 + (tick - bearing) * _PIXELS_PER_DEGREE
            if not 8 <= x <= 312:
                continue
            normalized = tick % 360
            major = normalized % 15 == 0
            cardinal = normalized in _CARDINALS
            tick_label = _CARDINALS.get(normalized, f"{normalized:03d}")
            color = "#e0c17b" if cardinal else "#f3f4e9"
            pieces.append(
                f'<g data-role="tick" data-bearing="{normalized:03d}" '
                f'transform="translate({x:.2f} 0)">'
                f'<path d="M0 {30 if cardinal else 33 if major else 36}V40" '
                f'stroke="{color}" stroke-width="{1.3 if cardinal else 1}"/>')
            if major and 18 <= x <= 302:
                pieces.append(f'<text x="0" y="54" fill="{color}" '
                              f'font-size="{9 if cardinal else 8}" '
                              f'font-weight="{500 if cardinal else 300}">{tick_label}</text>')
            pieces.append('</g>')
    pieces.extend([
        '<rect x="130" y="2" width="60" height="20" rx="1" '
        'fill="#141a14" stroke="#d2d6b9" stroke-opacity=".65"/>',
        f'<text data-role="heading-readout" x="160" y="16" fill="#f7f8ec" '
        f'font-size="12" font-weight="500">{readout}</text>',
        '<path data-role="heading-index" d="M155 24L160 29L165 24M160 29V39" '
        'stroke="#f7f8ec" stroke-width="1.5" stroke-linejoin="round"/>',
        '</g></svg>',
    ])
    return ''.join(pieces)


def gimbal_indicator(pose: GimbalPose) -> str:
    """Plot yaw to the right and pitch up, with home at the box center."""
    x = 64 + 56 * pose.yaw_deg / VirtualGimbal.YAW_LIMIT
    y = 24 - 16 * pose.pitch_deg / VirtualGimbal.PITCH_LIMIT
    label = f"Camera relative to rover: yaw {pose.yaw_deg:+.1f}°, pitch {pose.pitch_deg:+.1f}°"
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 48" '
        f'role="img" aria-label="{label}">'
        f'<g fill="none" stroke="{_HUD_GREEN}" stroke-width="1.4">'
        '<rect x="2" y="2" width="124" height="44" fill="#0c100d" fill-opacity=".58"/>'
        '<path d="M64 2V8M64 40V46M2 24H8M120 24H126"/>'
        '<rect x="57" y="19" width="14" height="10" opacity=".55"/>'
        '</g>'
        f'<circle data-role="gimbal-point" cx="{x:.2f}" cy="{y:.2f}" r="2.6" '
        f'fill="{_HUD_GREEN}" stroke="#080c09" stroke-width="1"/>'
        '</svg>'
    )


_RETICLE_GEOMETRY = '<path d="M62 60H98M80 42V78"/>'

TACTICAL_RETICLE = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 160 120" '
    'aria-hidden="true" fill="none" stroke-linecap="square" '
    'stroke-linejoin="miter">'
    '<g stroke="#080c09" stroke-width="3.2" opacity=".95">'
    + _RETICLE_GEOMETRY + '</g>'
    f'<g stroke="{_HUD_GREEN}" stroke-width="1.5">'
    + _RETICLE_GEOMETRY + '</g></svg>'
)
