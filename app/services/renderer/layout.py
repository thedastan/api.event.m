"""Geometry and colour resolution -- the only place percentages become pixels.

Templates are written in percentages of the canvas; every drawing routine below
this module works in whole pixels. Keeping the conversion in one function is what
makes "the same template gives the same composition" checkable rather than hoped
for.
"""

from collections import namedtuple

Box = namedtuple('Box', 'left top width height')


def box_of(element, spec):
    """An element's pixel box on this spec's canvas."""
    return Box(*element.layout.pixels(spec.canvas_width, spec.canvas_height))


def right(box):
    return box.left + box.width


def bottom(box):
    return box.top + box.height


def inset(box, amount):
    """Shrink a box by ``amount`` px on every side, never past zero size."""
    amount = int(amount)
    return Box(
        box.left + amount,
        box.top + amount,
        max(0, box.width - 2 * amount),
        max(0, box.height - 2 * amount),
    )


def intersection_area(a, b):
    """Overlapping area of two boxes in square pixels."""
    width = min(right(a), right(b)) - max(a.left, b.left)
    height = min(bottom(a), bottom(b)) - max(a.top, b.top)
    return width * height if width > 0 and height > 0 else 0


def safe_area(spec):
    """The rectangle everything is supposed to stay inside."""
    margin = spec.safe_margin
    return Box(
        margin,
        margin,
        spec.canvas_width - 2 * margin,
        spec.canvas_height - 2 * margin,
    )


def parse_hex(value, default=(0, 0, 0, 255)):
    """``#rgb`` / ``#rrggbb`` / ``#rrggbbaa`` -> an RGBA tuple."""
    text = str(value or '').strip().lstrip('#')
    if len(text) == 3:
        text = ''.join(char * 2 for char in text)
    if len(text) == 6:
        text += 'ff'
    if len(text) != 8:
        return default
    try:
        return tuple(int(text[i:i + 2], 16) for i in range(0, 8, 2))
    except ValueError:
        return default


def color(name, theme, default=(0, 0, 0, 255), opacity=1.0):
    """Resolve a theme key or literal to RGBA, applying ``opacity``."""
    resolved = theme.color(name) if theme is not None else name
    rgba = parse_hex(resolved, default)
    if opacity >= 1.0:
        return rgba
    return rgba[:3] + (int(rgba[3] * max(0.0, opacity)),)


def focal_offsets(focal_point):
    """A focal point name -> ``(x, y)`` in 0..1, used to place a crop window."""
    text = str(focal_point or 'center').strip().lower().replace('_', '-')
    axis = {'left': 0.0, 'center': 0.5, 'centre': 0.5, 'right': 1.0,
            'top': 0.0, 'bottom': 1.0}

    if '-' in text:
        first, _, second = text.partition('-')
        horizontal = axis.get(first, axis.get(second, 0.5))
        vertical = axis.get(second, axis.get(first, 0.5))
        if first in ('top', 'bottom'):
            horizontal, vertical = axis.get(second, 0.5), axis.get(first, 0.5)
        return horizontal, vertical

    if text in ('left', 'right'):
        return axis[text], 0.5
    if text in ('top', 'bottom'):
        return 0.5, axis[text]
    return 0.5, 0.5
