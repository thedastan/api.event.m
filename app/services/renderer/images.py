"""Placing a generated asset into its slot.

The image model returns one of a handful of fixed sizes, never the exact aspect
of a template slot, so cropping is unavoidable. Doing it here -- with a focal
point the asset prompt also knew about -- is what keeps the subject in frame
instead of trusting the model to have centred it.
"""

import logging

from PIL import Image

from . import layout as geometry, shapes

logger = logging.getLogger(__name__)


def _cover_box(source_size, box, focal_point):
    """Crop window in the source that fills ``box`` at its aspect ratio."""
    source_width, source_height = source_size
    scale = max(box.width / source_width, box.height / source_height)
    window_width = min(source_width, box.width / scale)
    window_height = min(source_height, box.height / scale)

    focal_x, focal_y = geometry.focal_offsets(focal_point)
    left = (source_width - window_width) * focal_x
    top = (source_height - window_height) * focal_y
    return (
        int(round(left)), int(round(top)),
        int(round(left + window_width)), int(round(top + window_height)),
    )


def fit(source, box, image_spec):
    """Resize (and crop) an opened image to exactly ``box``."""
    target = (max(1, box.width), max(1, box.height))

    if image_spec.fit == 'contain':
        contained = source.copy()
        contained.thumbnail(target, Image.LANCZOS)
        canvas = Image.new('RGBA', target, (0, 0, 0, 0))
        canvas.paste(
            contained,
            ((target[0] - contained.width) // 2,
             (target[1] - contained.height) // 2),
        )
        return canvas

    window = _cover_box(source.size, box, image_spec.focal_point)
    return source.crop(window).resize(target, Image.LANCZOS)


def placeholder(box, theme, image_spec):
    """Stand-in for an asset that could not be generated.

    A themed gradient, not an error: one failed photograph should cost the slide
    its photograph, not the whole generation. The report says what happened.
    """
    return shapes.linear_gradient(
        (max(1, box.width), max(1, box.height)),
        geometry.color(theme.primary, theme),
        geometry.color(theme.accent, theme),
        angle=45,
    )


def place(canvas, box, source, image_spec, theme):
    """Draw an asset into its slot, honouring fit, radius, fade and overlay."""
    if box.width <= 0 or box.height <= 0:
        return

    patch = (
        fit(source, box, image_spec) if source is not None
        else placeholder(box, theme, image_spec)
    ).convert('RGBA')

    if image_spec.overlay and image_spec.overlay_opacity > 0:
        tint = Image.new(
            'RGBA', patch.size,
            geometry.color(
                image_spec.overlay, theme, opacity=image_spec.overlay_opacity
            ),
        )
        patch = Image.alpha_composite(patch, tint)

    mask = shapes.rounded_mask(patch.size, image_spec.border_radius)
    if image_spec.edge_fade:
        fade = shapes.edge_fade_mask(patch.size, image_spec.edge_fade)
        mask = Image.composite(mask, Image.new('L', patch.size, 0), fade)

    canvas.paste(patch, (box.left, box.top), mask)


def open_asset(path):
    """Open an asset file, or None if it is missing or unreadable."""
    if not path:
        return None
    try:
        with Image.open(path) as handle:
            return handle.convert('RGBA')
    except (OSError, ValueError) as exc:
        logger.warning('asset %s could not be opened: %s', path, exc)
        return None
