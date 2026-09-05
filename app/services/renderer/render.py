"""Turning a filled spec plus its assets into a PNG.

This is the module the whole change is about: the composition is decided here,
by code reading coordinates, instead of by an image model reading an English
description of them. Nothing on this path can invent a word, move a title or
change a font.

``render_slide`` returns the PNG together with a report -- per element, the size
its text ended up at and whether it fit -- which the validator turns into a
score and the debugger reads when a slide comes out wrong.
"""

import io
import logging

from PIL import Image, ImageDraw

from app.spec import SlideSpec

from . import fonts, images, layout as geometry, shapes, text as typeset

logger = logging.getLogger(__name__)

RENDER_VERSION = 1


class RenderError(Exception):
    """The slide could not be drawn at all."""


def _background(spec):
    size = (spec.canvas_width, spec.canvas_height)
    background = spec.background
    base = geometry.color(background.color, spec.theme, (255, 255, 255, 255))

    if background.type == 'gradient' and background.color_to:
        canvas = Image.new('RGBA', size, base)
        canvas.alpha_composite(
            shapes.linear_gradient(
                size, base,
                geometry.color(background.color_to, spec.theme, base),
                background.angle,
            )
        )
        return canvas
    return Image.new('RGBA', size, base)


def _draw_shape(canvas, element, box, theme):
    shape = element.shape
    fill = geometry.color(shape.fill, theme, opacity=shape.opacity)
    if element.type == 'divider':
        # A rule is specified by its slot; its thickness is the slot's height.
        box = geometry.Box(box.left, box.top, box.width, max(1, box.height))
    shapes.fill_rect(canvas, box, fill, shape.radius)
    if shape.stroke and shape.stroke_width > 0:
        shapes.stroke_rect(
            canvas, box, geometry.color(shape.stroke, theme),
            shape.stroke_width, shape.radius,
        )


def _draw_text(canvas, draw, element, box, spec):
    block = typeset.layout(
        element.resolved_text(), box.width, box.height,
        element.typography, element.constraints, spec.theme,
        max_lines=element.content.max_lines,
    )
    typeset.draw(
        draw, block, box, element.typography,
        geometry.color(element.typography.color, spec.theme), spec.theme,
    )
    return {
        'font_size': block.font_size,
        'lines': block.line_count,
        'shrunk': block.shrunk,
        'truncated': block.truncated,
        'overflow_x': block.overflow_x,
        'overflow_y': block.overflow_y,
        'used_height': round(block.height, 1),
    }


def _draw_list(canvas, draw, element, box, spec):
    block = typeset.layout_list(
        element.resolved_text(), box.width, box.height,
        element.typography, element.constraints, spec.theme, element.list,
    )
    if not block.items:
        return {'font_size': block.font_size, 'lines': 0, 'shrunk': False,
                'truncated': False, 'overflow_x': False, 'overflow_y': False,
                'used_height': 0}

    spacing = element.list.item_gap * block.font_size / max(
        1, element.typography.font_size
    )
    indent = (
        0 if element.list.marker == 'none'
        else typeset._marker_indent(block.font_size, element.list)
    )
    marker_size = max(4, int(block.font_size * 0.34))
    marker_color = geometry.color(element.list.marker_color, spec.theme)
    typography = element.typography.at_size(block.font_size)

    cursor = box.top
    if element.typography.valign == 'middle':
        cursor = box.top + (box.height - block.height) / 2
    elif element.typography.valign == 'bottom':
        cursor = box.top + box.height - block.height

    for item in block.items:
        item_box = geometry.Box(
            box.left + indent, int(cursor), box.width - indent,
            int(item.height) + 1,
        )
        typeset.draw(
            draw, item, item_box, typography,
            geometry.color(element.typography.color, spec.theme), spec.theme,
        )
        shapes.marker(
            canvas, element.list.marker,
            (box.left + indent / 2, cursor + item.line_height / 2),
            marker_size, marker_color,
        )
        cursor += item.height + spacing

    return {
        'font_size': block.font_size,
        'lines': sum(item.line_count for item in block.items),
        'items': len(block.items),
        'shrunk': block.shrunk,
        'truncated': block.truncated,
        'overflow_x': block.overflow_x,
        'overflow_y': block.overflow_y,
        'used_height': round(block.height, 1),
    }


def _draw_image(canvas, element, box, spec, assets):
    asset = (assets or {}).get(element.id)
    path = getattr(asset, 'path', asset) if asset is not None else None
    source = images.open_asset(path)
    images.place(canvas, box, source, element.image, spec.theme)
    return {'asset': bool(source), 'asset_path': str(path) if path else ''}


def render_slide(spec, assets=None):
    """Draw a filled spec. Returns ``(png_bytes, report)``.

    ``assets`` maps element id to something with a ``.path`` (or to a path).
    A missing asset is drawn as a themed gradient and recorded in the report --
    losing one photograph should not lose the slide.
    """
    if isinstance(spec, dict):
        spec = SlideSpec.from_dict(spec)
    if not spec.elements:
        raise RenderError('slide spec has no elements')

    try:
        canvas = _background(spec)
        draw = ImageDraw.Draw(canvas)
        report = {
            'render_version': RENDER_VERSION,
            'canvas': [spec.canvas_width, spec.canvas_height],
            'elements': {},
            'missing_assets': [],
        }

        for _, element in spec.in_draw_order():
            box = geometry.box_of(element, spec)
            if box.width <= 0 or box.height <= 0:
                continue

            if element.is_shape:
                _draw_shape(canvas, element, box, spec.theme)
                entry = {}
            elif element.is_image:
                entry = _draw_image(canvas, element, box, spec, assets)
                if not entry['asset']:
                    report['missing_assets'].append(element.id)
            elif element.is_list:
                entry = _draw_list(canvas, draw, element, box, spec)
            else:
                entry = _draw_text(canvas, draw, element, box, spec)

            entry['box'] = list(box)
            entry['type'] = element.type
            report['elements'][element.id] = entry

        buffer = io.BytesIO()
        canvas.convert('RGB').save(buffer, format='PNG', optimize=True)
        return buffer.getvalue(), report
    except fonts.FontError:
        raise
    except RenderError:
        raise
    except Exception as exc:  # noqa: BLE001 - context beats a bare traceback
        raise RenderError(f'{type(exc).__name__}: {exc}') from exc
