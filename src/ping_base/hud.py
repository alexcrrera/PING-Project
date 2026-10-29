"""Local camera HUD artwork: a scrolling heading tape and a precise reticle."""

from math import ceil, floor, isfinite


_CARDINALS = {0: "N", 45: "NE", 90: "E", 135: "SE",
              180: "S", 225: "SW", 270: "W", 315: "NW"}
_PIXELS_PER_DEGREE = 2.3


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


_RETICLE_GEOMETRY = (
    '<path d="M80 19V43M80 77V101M25 60H63M97 60H135"/>'
    '<path d="M73 28H87M76 36H84M76 84H84M73 92H87'
    'M37 53V67M48 56V64M112 56V64M123 53V67"/>'
    '<path d="M52 38V33H59M101 33H108V38M52 82V87H59M101 87H108V82"/>'
    '<circle cx="80" cy="60" r="4"/>'
    '<path d="M79 60H81"/>'
)

TACTICAL_RETICLE = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 160 120" '
    'aria-hidden="true" fill="none" stroke-linecap="square" '
    'stroke-linejoin="miter">'
    '<g stroke="#080c09" stroke-width="3.2" opacity=".95">'
    + _RETICLE_GEOMETRY + '</g>'
    '<g stroke="#f0f3df" stroke-width="1.1">'
    + _RETICLE_GEOMETRY + '</g></svg>'
)
