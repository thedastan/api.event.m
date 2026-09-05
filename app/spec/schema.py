"""The Slide Spec v2 data model.

Two rules shape it:

* ``content``/``layout``/``typography`` are separate. In v1 a single ``content``
  string meant "instruction for the copywriter" on a text element and "prompt for
  the image model" on an image one; splitting the two apart is what lets each
  stage read a spec without guessing.
* Geometry stays in template percentages. Percentages are what a human editing a
  template thinks in, and what the API has always exposed; the conversion to
  pixels happens once, in the renderer.

Every dataclass round-trips through ``from_dict``/``to_dict``, because a filled
spec is stored on ``GeneratedImage`` and has to survive a trip through JSON.
"""

from dataclasses import dataclass, field, replace
from typing import Any, Dict, List, Optional

# Modes a ``content`` block can declare.
AI_TEXT = 'ai_text'
AI_IMAGE = 'ai_image'
STATIC = 'static'
NONE = 'none'
CONTENT_MODES = (AI_TEXT, AI_IMAGE, STATIC, NONE)

# Element types the renderer knows how to draw.
TEXT_TYPES = ('text', 'title', 'subtitle', 'quote', 'label', 'footer', 'number')
LIST_TYPES = ('list', 'bullet_list')
IMAGE_TYPES = ('image',)
SHAPE_TYPES = ('shape', 'divider', 'card')
ELEMENT_TYPES = TEXT_TYPES + LIST_TYPES + IMAGE_TYPES + SHAPE_TYPES

ALIGNMENTS = ('left', 'center', 'right')
VALIGNMENTS = ('top', 'middle', 'bottom')
FITS = ('cover', 'contain')
TRANSFORMS = ('none', 'upper', 'lower')

CANVAS_WIDTH = 1920
CANVAS_HEIGHT = 1080


def _get(data, key, default):
    """``data[key]``, treating an explicit null as absent."""
    value = (data or {}).get(key)
    return default if value is None else value


@dataclass
class Content:
    """What goes into an element, and who supplies it."""

    mode: str = NONE
    # For ai_text: what to write. For ai_image: what to depict.
    instruction: str = ''
    # For static: the literal string.
    value: str = ''
    # Copy budget. ``max_chars`` is advisory (the copy prompt states it); the
    # renderer enforces the box itself. Left at 0 the copywriter computes one.
    max_chars: int = 0
    max_lines: int = 0

    @classmethod
    def from_dict(cls, data):
        data = data or {}
        return cls(
            mode=str(_get(data, 'mode', NONE)),
            instruction=str(_get(data, 'instruction', '')),
            value=str(_get(data, 'value', '')),
            max_chars=int(_get(data, 'max_chars', 0)),
            max_lines=int(_get(data, 'max_lines', 0)),
        )

    def to_dict(self):
        return {
            'mode': self.mode,
            'instruction': self.instruction,
            'value': self.value,
            'max_chars': self.max_chars,
            'max_lines': self.max_lines,
        }

    @property
    def is_ai_text(self):
        return self.mode == AI_TEXT

    @property
    def is_ai_image(self):
        return self.mode == AI_IMAGE


@dataclass
class Layout:
    """Position and size as percentages of the canvas."""

    x: float = 0.0
    y: float = 0.0
    width: float = 0.0
    height: float = 0.0

    @classmethod
    def from_dict(cls, data):
        data = data or {}
        return cls(
            x=float(_get(data, 'x', 0)),
            y=float(_get(data, 'y', 0)),
            width=float(_get(data, 'width', 0)),
            height=float(_get(data, 'height', 0)),
        )

    def to_dict(self):
        return {
            'x': self.x, 'y': self.y,
            'width': self.width, 'height': self.height,
        }

    @property
    def right(self):
        return self.x + self.width

    @property
    def bottom(self):
        return self.y + self.height

    def pixels(self, canvas_width, canvas_height):
        """``(left, top, width, height)`` in whole pixels."""
        left = round(self.x / 100 * canvas_width)
        top = round(self.y / 100 * canvas_height)
        right = round(self.right / 100 * canvas_width)
        bottom = round(self.bottom / 100 * canvas_height)
        return left, top, right - left, bottom - top


@dataclass
class Typography:
    """Real type, not a size bucket.

    ``font_size`` is in canvas pixels at 1920x1080 -- the same unit a designer
    would type into Figma, which is the point of dropping v1's ``"xlarge"``.
    """

    family: str = 'body'          # 'heading' | 'body' | a concrete family name
    font_size: int = 24
    font_weight: int = 400
    line_height: float = 1.3
    align: str = 'left'
    valign: str = 'top'
    color: str = 'text'           # theme key or #rrggbb
    letter_spacing: float = 0.0   # px, positive tracks out
    transform: str = 'none'
    italic: bool = False

    @classmethod
    def from_dict(cls, data):
        data = data or {}
        return cls(
            family=str(_get(data, 'family', 'body')),
            font_size=int(_get(data, 'font_size', 24)),
            font_weight=int(_get(data, 'font_weight', 400)),
            line_height=float(_get(data, 'line_height', 1.3)),
            align=str(_get(data, 'align', 'left')),
            valign=str(_get(data, 'valign', 'top')),
            color=str(_get(data, 'color', 'text')),
            letter_spacing=float(_get(data, 'letter_spacing', 0)),
            transform=str(_get(data, 'transform', 'none')),
            italic=bool(_get(data, 'italic', False)),
        )

    def to_dict(self):
        return {
            'family': self.family,
            'font_size': self.font_size,
            'font_weight': self.font_weight,
            'line_height': self.line_height,
            'align': self.align,
            'valign': self.valign,
            'color': self.color,
            'letter_spacing': self.letter_spacing,
            'transform': self.transform,
            'italic': self.italic,
        }

    def at_size(self, font_size):
        return replace(self, font_size=int(font_size))


@dataclass
class Constraints:
    """How far the renderer may bend an element to make the content fit."""

    min_font_size: int = 0        # 0 -> derived from font_size in validate
    allow_wrap: bool = True
    allow_shrink: bool = True
    allow_overlap: bool = False   # opt out of the overlap check (overlays)

    @classmethod
    def from_dict(cls, data):
        data = data or {}
        return cls(
            min_font_size=int(_get(data, 'min_font_size', 0)),
            allow_wrap=bool(_get(data, 'allow_wrap', True)),
            allow_shrink=bool(_get(data, 'allow_shrink', True)),
            allow_overlap=bool(_get(data, 'allow_overlap', False)),
        )

    def to_dict(self):
        return {
            'min_font_size': self.min_font_size,
            'allow_wrap': self.allow_wrap,
            'allow_shrink': self.allow_shrink,
            'allow_overlap': self.allow_overlap,
        }


@dataclass
class ImageSpec:
    """How a generated asset is placed into its slot.

    ``focal_point`` and ``negative_space`` do double duty: the renderer crops by
    the first, and the asset prompt is written from both, so the photograph comes
    back composed for the slot it will live in.
    """

    fit: str = 'cover'
    focal_point: str = 'center'   # center | left | right | top | bottom | x-y pairs
    border_radius: int = 0        # px
    asset_type: str = 'hero_image'
    negative_space: str = ''      # left | right | top | bottom | ''
    subject_position: str = 'center'
    edge_fade: str = ''           # '' | left | right | top | bottom
    overlay: str = ''             # theme colour drawn over the image
    overlay_opacity: float = 0.0

    @classmethod
    def from_dict(cls, data):
        data = data or {}
        return cls(
            fit=str(_get(data, 'fit', 'cover')),
            focal_point=str(_get(data, 'focal_point', 'center')),
            border_radius=int(_get(data, 'border_radius', 0)),
            asset_type=str(_get(data, 'asset_type', 'hero_image')),
            negative_space=str(_get(data, 'negative_space', '')),
            subject_position=str(_get(data, 'subject_position', 'center')),
            edge_fade=str(_get(data, 'edge_fade', '')),
            overlay=str(_get(data, 'overlay', '')),
            overlay_opacity=float(_get(data, 'overlay_opacity', 0)),
        )

    def to_dict(self):
        return {
            'fit': self.fit,
            'focal_point': self.focal_point,
            'border_radius': self.border_radius,
            'asset_type': self.asset_type,
            'negative_space': self.negative_space,
            'subject_position': self.subject_position,
            'edge_fade': self.edge_fade,
            'overlay': self.overlay,
            'overlay_opacity': self.overlay_opacity,
        }


@dataclass
class ShapeSpec:
    fill: str = 'accent'
    radius: int = 0
    opacity: float = 1.0
    stroke: str = ''
    stroke_width: int = 0

    @classmethod
    def from_dict(cls, data):
        data = data or {}
        return cls(
            fill=str(_get(data, 'fill', 'accent')),
            radius=int(_get(data, 'radius', 0)),
            opacity=float(_get(data, 'opacity', 1.0)),
            stroke=str(_get(data, 'stroke', '')),
            stroke_width=int(_get(data, 'stroke_width', 0)),
        )

    def to_dict(self):
        return {
            'fill': self.fill,
            'radius': self.radius,
            'opacity': self.opacity,
            'stroke': self.stroke,
            'stroke_width': self.stroke_width,
        }


@dataclass
class ListSpec:
    """Bullet lists. Items arrive as newline-separated copy."""

    marker: str = 'dot'           # dot | diamond | dash | number | none
    marker_color: str = 'accent'
    item_count: int = 4
    item_gap: int = 16            # px between items, on top of line height
    marker_gap: int = 18          # px between marker and text

    @classmethod
    def from_dict(cls, data):
        data = data or {}
        return cls(
            marker=str(_get(data, 'marker', 'dot')),
            marker_color=str(_get(data, 'marker_color', 'accent')),
            item_count=int(_get(data, 'item_count', 4)),
            item_gap=int(_get(data, 'item_gap', 16)),
            marker_gap=int(_get(data, 'marker_gap', 18)),
        )

    def to_dict(self):
        return {
            'marker': self.marker,
            'marker_color': self.marker_color,
            'item_count': self.item_count,
            'item_gap': self.item_gap,
            'marker_gap': self.marker_gap,
        }


@dataclass
class Theme:
    primary: str = '#10233F'
    accent: str = '#FF7A00'
    text: str = '#172033'
    muted: str = '#6B7280'
    background: str = '#F7F8FA'
    surface: str = '#FFFFFF'
    on_primary: str = '#FFFFFF'
    font_heading: str = 'Inter'
    font_body: str = 'Inter'

    @classmethod
    def from_dict(cls, data):
        data = data or {}
        return cls(
            primary=str(_get(data, 'primary', '#10233F')),
            accent=str(_get(data, 'accent', '#FF7A00')),
            text=str(_get(data, 'text', '#172033')),
            muted=str(_get(data, 'muted', '#6B7280')),
            background=str(_get(data, 'background', '#F7F8FA')),
            surface=str(_get(data, 'surface', '#FFFFFF')),
            on_primary=str(_get(data, 'on_primary', '#FFFFFF')),
            font_heading=str(_get(data, 'font_heading', 'Inter')),
            font_body=str(_get(data, 'font_body', 'Inter')),
        )

    def to_dict(self):
        return {
            'primary': self.primary,
            'accent': self.accent,
            'text': self.text,
            'muted': self.muted,
            'background': self.background,
            'surface': self.surface,
            'on_primary': self.on_primary,
            'font_heading': self.font_heading,
            'font_body': self.font_body,
        }

    def color(self, name, default=None):
        """Resolve a theme key or pass a literal ``#rrggbb`` through."""
        if not name:
            return default
        if str(name).startswith('#'):
            return str(name)
        return getattr(self, str(name), default)


@dataclass
class Background:
    type: str = 'solid'           # solid | gradient
    color: str = 'background'
    color_to: str = ''
    angle: int = 0                # degrees, 0 = left-to-right

    @classmethod
    def from_dict(cls, data):
        data = data or {}
        return cls(
            type=str(_get(data, 'type', 'solid')),
            color=str(_get(data, 'color', 'background')),
            color_to=str(_get(data, 'color_to', '')),
            angle=int(_get(data, 'angle', 0)),
        )

    def to_dict(self):
        return {
            'type': self.type,
            'color': self.color,
            'color_to': self.color_to,
            'angle': self.angle,
        }


@dataclass
class Element:
    id: str = ''
    type: str = 'text'
    role: str = ''
    z: int = 0
    content: Content = field(default_factory=Content)
    layout: Layout = field(default_factory=Layout)
    typography: Typography = field(default_factory=Typography)
    constraints: Constraints = field(default_factory=Constraints)
    image: ImageSpec = field(default_factory=ImageSpec)
    shape: ShapeSpec = field(default_factory=ShapeSpec)
    list: ListSpec = field(default_factory=ListSpec)
    # Filled in by the copy stage; never present in a template on disk.
    text: str = ''

    @classmethod
    def from_dict(cls, data):
        data = data or {}
        return cls(
            id=str(_get(data, 'id', '')),
            type=str(_get(data, 'type', 'text')),
            role=str(_get(data, 'role', '')),
            z=int(_get(data, 'z', 0)),
            content=Content.from_dict(data.get('content')),
            layout=Layout.from_dict(data.get('layout')),
            typography=Typography.from_dict(data.get('typography')),
            constraints=Constraints.from_dict(data.get('constraints')),
            image=ImageSpec.from_dict(data.get('image')),
            shape=ShapeSpec.from_dict(data.get('shape')),
            list=ListSpec.from_dict(data.get('list')),
            text=str(_get(data, 'text', '')),
        )

    def to_dict(self):
        return {
            'id': self.id,
            'type': self.type,
            'role': self.role,
            'z': self.z,
            'content': self.content.to_dict(),
            'layout': self.layout.to_dict(),
            'typography': self.typography.to_dict(),
            'constraints': self.constraints.to_dict(),
            'image': self.image.to_dict(),
            'shape': self.shape.to_dict(),
            'list': self.list.to_dict(),
            'text': self.text,
        }

    @property
    def is_text(self):
        return self.type in TEXT_TYPES

    @property
    def is_list(self):
        return self.type in LIST_TYPES

    @property
    def is_image(self):
        return self.type in IMAGE_TYPES

    @property
    def is_shape(self):
        return self.type in SHAPE_TYPES

    @property
    def writes_text(self):
        """True when the copy stage has to produce a string for this element."""
        return (self.is_text or self.is_list) and self.content.is_ai_text

    def resolved_text(self):
        """The string to draw: written copy, or a static value."""
        if self.content.mode == STATIC:
            return self.content.value
        return self.text


@dataclass
class SlideSpec:
    id: str = ''
    template_id: str = ''
    page: int = 1
    version: int = 2
    canvas_width: int = CANVAS_WIDTH
    canvas_height: int = CANVAS_HEIGHT
    safe_margin: int = 72         # px
    gap: int = 48                 # px
    layout_type: str = ''
    theme: Theme = field(default_factory=Theme)
    background: Background = field(default_factory=Background)
    elements: List[Element] = field(default_factory=list)
    # The event/brand name the copy stage invents, reused by logo elements.
    brand_name: str = ''

    @classmethod
    def from_dict(cls, data: Dict[str, Any]):
        """Accept the on-disk template shape or a stored spec, interchangeably."""
        data = data or {}
        body = data.get('template') or data.get('slide') or data
        canvas = body.get('canvas') or {}
        layout = body.get('layout') or {}

        return cls(
            id=str(_get(body, 'id', '')),
            template_id=str(_get(body, 'template_id', '')),
            page=int(_get(body, 'page', 1)),
            version=int(_get(body, 'version', 2)),
            canvas_width=int(_get(canvas, 'width', CANVAS_WIDTH)),
            canvas_height=int(_get(canvas, 'height', CANVAS_HEIGHT)),
            safe_margin=int(_get(layout, 'safe_margin', 72)),
            gap=int(_get(layout, 'gap', 48)),
            layout_type=str(_get(layout, 'type', '')),
            theme=Theme.from_dict(body.get('theme')),
            background=Background.from_dict(body.get('background')),
            elements=[
                Element.from_dict(item) for item in body.get('elements') or []
            ],
            brand_name=str(_get(body, 'brand_name', '')),
        )

    def to_dict(self):
        return {
            'template': {
                'id': self.id,
                'template_id': self.template_id,
                'page': self.page,
                'version': self.version,
                'canvas': {
                    'width': self.canvas_width,
                    'height': self.canvas_height,
                },
                'layout': {
                    'type': self.layout_type,
                    'safe_margin': self.safe_margin,
                    'gap': self.gap,
                },
                'theme': self.theme.to_dict(),
                'background': self.background.to_dict(),
                'brand_name': self.brand_name,
                'elements': [element.to_dict() for element in self.elements],
            }
        }

    @property
    def aspect_ratio(self):
        from math import gcd

        divisor = gcd(self.canvas_width, self.canvas_height) or 1
        return f'{self.canvas_width // divisor}:{self.canvas_height // divisor}'

    def element(self, element_id):
        for item in self.elements:
            if item.id == element_id:
                return item
        return None

    def text_elements(self):
        return [item for item in self.elements if item.writes_text]

    def image_elements(self):
        return [
            item for item in self.elements
            if item.is_image and item.content.is_ai_image
        ]

    def in_draw_order(self):
        """Elements sorted for painting: explicit ``z`` first, then declaration."""
        return sorted(
            enumerate(self.elements), key=lambda pair: (pair[1].z, pair[0])
        )

    def copy(self):
        return SlideSpec.from_dict(self.to_dict())
