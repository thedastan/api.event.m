"""Rectangles, rules, gradients and markers.

Everything here used to be something the image model was asked to draw -- a
"thin horizontal rule with a small diamond accent", a "rounded banner bar". Drawn
directly they cost a millisecond, land on the pixel they were specified on, and
never come back with a typo in them.

Rounded corners and markers are rendered on a supersampled mask and scaled down,
because Pillow's own shape drawing has no antialiasing and hard stair-steps read
as amateurish at 1920x1080.
"""

from PIL import Image, ImageDraw, ImageFilter

from . import layout as geometry

SUPERSAMPLE = 4


def _mask(size, painter):
    """An antialiased alpha mask of ``size``, painted at 4x and reduced."""
    width, height = max(1, size[0]), max(1, size[1])
    big = Image.new('L', (width * SUPERSAMPLE, height * SUPERSAMPLE), 0)
    painter(ImageDraw.Draw(big), SUPERSAMPLE)
    return big.resize((width, height), Image.LANCZOS)


def rounded_mask(size, radius):
    """Alpha mask of a rounded rectangle filling ``size``."""
    if radius <= 0:
        return Image.new('L', (max(1, size[0]), max(1, size[1])), 255)

    def paint(draw, scale):
        draw.rounded_rectangle(
            [0, 0, size[0] * scale - 1, size[1] * scale - 1],
            radius=radius * scale,
            fill=255,
        )

    return _mask(size, paint)


def fill_rect(canvas, box, color, radius=0):
    """Paint a solid (optionally rounded) rectangle onto an RGBA canvas."""
    if box.width <= 0 or box.height <= 0:
        return
    patch = Image.new('RGBA', (box.width, box.height), color)
    canvas.paste(patch, (box.left, box.top), rounded_mask(
        (box.width, box.height), radius
    ))


def stroke_rect(canvas, box, color, width, radius=0):
    """Outline a rectangle: the rounded fill minus an inset copy of itself."""
    if width <= 0 or box.width <= 0 or box.height <= 0:
        return
    outer = rounded_mask((box.width, box.height), radius)
    inner_box = geometry.inset(box, width)
    if inner_box.width > 0 and inner_box.height > 0:
        inner = rounded_mask(
            (inner_box.width, inner_box.height), max(0, radius - width)
        )
        outer.paste(0, (width, width), inner)
    canvas.paste(Image.new('RGBA', (box.width, box.height), color),
                 (box.left, box.top), outer)


def drop_shadow(canvas, box, radius=0, blur=28, offset=(0, 12), opacity=0.18):
    """A soft shadow under a card. Drawn as a blurred copy of its own mask."""
    pad = blur * 2
    size = (box.width + pad * 2, box.height + pad * 2)
    shadow = Image.new('RGBA', size, (0, 0, 0, 0))
    shadow.paste(
        Image.new('RGBA', (box.width, box.height), (0, 0, 0, int(255 * opacity))),
        (pad, pad),
        rounded_mask((box.width, box.height), radius),
    )
    shadow = shadow.filter(ImageFilter.GaussianBlur(blur / 2))
    canvas.alpha_composite(
        shadow, (box.left - pad + offset[0], box.top - pad + offset[1])
    )


def linear_gradient(size, start_color, end_color, angle=0):
    """A two-stop gradient. ``angle`` 0 runs left to right, 90 top to bottom."""
    width, height = max(1, size[0]), max(1, size[1])
    horizontal = angle % 180 < 90
    steps = width if horizontal else height

    ramp = Image.new('RGBA', (steps, 1))
    pixels = ramp.load()
    for index in range(steps):
        ratio = index / max(1, steps - 1)
        pixels[index, 0] = tuple(
            int(start + (end - start) * ratio)
            for start, end in zip(start_color, end_color)
        )

    ramp = ramp.resize((width, height) if horizontal else (1, steps))
    if not horizontal:
        ramp = ramp.resize((width, height))
    if angle % 360 >= 180:
        ramp = ramp.transpose(
            Image.FLIP_LEFT_RIGHT if horizontal else Image.FLIP_TOP_BOTTOM
        )
    return ramp


def edge_fade_mask(size, side, extent=0.45):
    """Alpha mask that fades one edge of an image out to nothing."""
    width, height = max(1, size[0]), max(1, size[1])
    mask = Image.new('L', (width, height), 255)
    if side not in ('left', 'right', 'top', 'bottom'):
        return mask

    horizontal = side in ('left', 'right')
    span = max(1, int((width if horizontal else height) * extent))
    ramp = Image.linear_gradient('L').resize((span, 1) if horizontal else (1, span))
    if horizontal:
        ramp = ramp.resize((span, height))
        if side == 'right':
            ramp = ramp.transpose(Image.FLIP_LEFT_RIGHT)
        mask.paste(ramp, (0 if side == 'left' else width - span, 0))
    else:
        ramp = ramp.resize((width, span))
        if side == 'bottom':
            ramp = ramp.transpose(Image.FLIP_TOP_BOTTOM)
        mask.paste(ramp, (0, 0 if side == 'top' else height - span))
    return mask


def marker(canvas, kind, center, size, color):
    """A list bullet: dot, diamond or dash."""
    x, y = center
    half = max(1, size // 2)

    if kind == 'none':
        return
    if kind == 'dash':
        box = geometry.Box(int(x - half), int(y - max(1, size // 8)),
                           size, max(2, size // 4))
        fill_rect(canvas, box, color, radius=max(1, size // 8))
        return

    def paint(draw, scale):
        span = size * scale
        if kind == 'diamond':
            middle = span / 2
            draw.polygon(
                [(middle, 0), (span, middle), (middle, span), (0, middle)],
                fill=255,
            )
        else:
            draw.ellipse([0, 0, span - 1, span - 1], fill=255)

    canvas.paste(
        Image.new('RGBA', (size, size), color),
        (int(x - half), int(y - half)),
        _mask((size, size), paint),
    )
