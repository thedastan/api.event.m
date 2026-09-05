"""Template validation, run at load time.

A broken template should fail loudly when it is read, not silently produce a
slide with a title drawn off-canvas. Hard errors raise; softer ones (an element
poking into the safe margin) come back as warnings so a template can be improved
without blocking a generation.

``normalize`` fills in the values that are derivable rather than making every
template repeat them -- most importantly ``min_font_size``, which the renderer's
shrink loop needs and which nobody wants to type on every element.
"""

from . import schema
from .schema import Element, SlideSpec

# How far the renderer may shrink type when a template does not say. Two thirds
# keeps a headline recognisably a headline; below that the hierarchy collapses
# and the slide looks broken in a way overflowing text does not.
DEFAULT_SHRINK_FLOOR = 0.66
ABSOLUTE_MIN_FONT_SIZE = 14


class SpecError(Exception):
    """A template that cannot be rendered as written."""


def normalize(spec: SlideSpec) -> SlideSpec:
    """Fill in derived defaults. Returns the same spec, mutated in place."""
    for element in spec.elements:
        constraints = element.constraints
        if constraints.min_font_size <= 0:
            constraints.min_font_size = max(
                ABSOLUTE_MIN_FONT_SIZE,
                int(element.typography.font_size * DEFAULT_SHRINK_FLOOR),
            )
        constraints.min_font_size = min(
            constraints.min_font_size, element.typography.font_size
        )

        if element.content.mode == schema.NONE:
            # A shape needs no content; anything else without a mode is text the
            # template forgot to mark up, and static-empty is the safe reading.
            element.content.mode = (
                schema.NONE if element.is_shape else schema.STATIC
            )
    return spec


def _check_element(element: Element, index: int, spec: SlideSpec, errors, warnings):
    where = f'element #{index} ({element.id or "no id"})'

    if not element.id:
        errors.append(f'{where}: missing id')
    if element.type not in schema.ELEMENT_TYPES:
        errors.append(f'{where}: unknown type {element.type!r}')

    layout = element.layout
    if layout.width <= 0 or layout.height <= 0:
        errors.append(f'{where}: width and height must be positive')
    if layout.x < 0 or layout.y < 0:
        errors.append(f'{where}: negative position')
    if layout.right > 100.001 or layout.bottom > 100.001:
        errors.append(
            f'{where}: extends past the canvas '
            f'(right={layout.right:.1f}%, bottom={layout.bottom:.1f}%)'
        )

    content = element.content
    if content.mode not in schema.CONTENT_MODES:
        errors.append(f'{where}: unknown content mode {content.mode!r}')
    if content.is_ai_image and not element.is_image:
        errors.append(f'{where}: ai_image content on a {element.type} element')
    if content.is_ai_text and element.is_image:
        errors.append(f'{where}: ai_text content on an image element')
    if content.is_ai_text and not content.instruction:
        errors.append(f'{where}: ai_text content needs an instruction')
    if content.is_ai_image and not content.instruction:
        errors.append(f'{where}: ai_image content needs an instruction')
    if element.is_image and content.mode == schema.NONE:
        errors.append(f'{where}: an image element needs ai_image content')

    if element.is_text or element.is_list:
        typography = element.typography
        if typography.font_size <= 0:
            errors.append(f'{where}: font_size must be positive')
        if typography.align not in schema.ALIGNMENTS:
            errors.append(f'{where}: unknown align {typography.align!r}')
        if typography.valign not in schema.VALIGNMENTS:
            errors.append(f'{where}: unknown valign {typography.valign!r}')
        if typography.transform not in schema.TRANSFORMS:
            errors.append(f'{where}: unknown transform {typography.transform!r}')
        if not 0.7 <= typography.line_height <= 3.0:
            errors.append(
                f'{where}: implausible line_height {typography.line_height}'
            )
        if spec.theme.color(typography.color) is None:
            errors.append(f'{where}: unknown colour {typography.color!r}')

    if element.is_image and element.image.fit not in schema.FITS:
        errors.append(f'{where}: unknown image fit {element.image.fit!r}')
    if element.is_shape and spec.theme.color(element.shape.fill) is None:
        errors.append(f'{where}: unknown shape fill {element.shape.fill!r}')

    # Soft: inside the safe margin. Full-bleed elements opt out with allow_overlap.
    margin_x = spec.safe_margin / spec.canvas_width * 100
    margin_y = spec.safe_margin / spec.canvas_height * 100
    if not element.constraints.allow_overlap and (
        layout.x + 0.001 < margin_x
        or layout.y + 0.001 < margin_y
        or layout.right > 100 - margin_x + 0.001
        or layout.bottom > 100 - margin_y + 0.001
    ):
        warnings.append(f'{where}: breaks the safe margin')


def validate_spec(spec: SlideSpec, strict=True):
    """Check a spec. Raises :class:`SpecError` on hard errors; returns warnings."""
    errors, warnings = [], []

    if spec.version != 2:
        errors.append(f'unsupported spec version {spec.version}')
    if spec.canvas_width <= 0 or spec.canvas_height <= 0:
        errors.append('canvas must have a positive size')
    if not spec.elements:
        errors.append('slide has no elements')

    seen = set()
    for index, element in enumerate(spec.elements):
        if element.id in seen:
            errors.append(f'duplicate element id {element.id!r}')
        seen.add(element.id)
        _check_element(element, index, spec, errors, warnings)

    if errors and strict:
        raise SpecError('; '.join(errors))
    return warnings
