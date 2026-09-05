"""Text layout: wrapping, vertical rhythm, alignment and font scaling.

Pillow draws glyphs; it does not lay out text. Everything a browser would do for
free is here instead -- greedy word wrap measured against the real face, line
boxes from a line-height multiplier, alignment inside the slot, and the shrink
loop that steps the size down until the copy fits the box the template drew.

The shrink loop is the safety net, not the plan: the copy stage is told how many
characters a slot holds (computed from these same measurements), so most slides
should render at their template size.
"""

from dataclasses import dataclass, field
from typing import List

from . import fonts

# Shrink step. One pixel at a time is needlessly slow at display sizes and
# indistinguishable in the result.
STEP = 2

ELLIPSIS = '…'


@dataclass
class Line:
    text: str
    width: float


@dataclass
class Block:
    """A laid-out run of text, ready to draw."""

    lines: List[Line] = field(default_factory=list)
    font_size: int = 0
    line_height: float = 0.0      # px between baselines' line boxes
    width: float = 0.0            # widest line
    height: float = 0.0           # total occupied height
    overflow_x: bool = False
    overflow_y: bool = False
    truncated: bool = False
    shrunk: bool = False

    @property
    def overflows(self):
        return self.overflow_x or self.overflow_y

    @property
    def line_count(self):
        return len(self.lines)


def measure(text, font, letter_spacing=0.0):
    """Advance width of ``text``, including tracking."""
    if not text:
        return 0.0
    width = font.getlength(text)
    if letter_spacing:
        width += letter_spacing * (len(text) - 1)
    return width


def apply_transform(text, transform):
    if transform == 'upper':
        return text.upper()
    if transform == 'lower':
        return text.lower()
    return text


def _break_word(word, font, max_width, letter_spacing):
    """Split a word too long for the box. Returns a list of fragments."""
    fragments, current = [], ''
    for char in word:
        candidate = current + char
        if current and measure(candidate, font, letter_spacing) > max_width:
            fragments.append(current)
            current = char
        else:
            current = candidate
    if current:
        fragments.append(current)
    return fragments or ['']


def wrap(text, font, max_width, letter_spacing=0.0, allow_wrap=True):
    """Greedy word wrap. Explicit newlines always break."""
    lines = []
    for paragraph in str(text).split('\n'):
        paragraph = paragraph.strip()
        if not paragraph:
            lines.append('')
            continue
        if not allow_wrap:
            lines.append(paragraph)
            continue

        current = ''
        for word in paragraph.split():
            candidate = f'{current} {word}' if current else word
            if current and measure(candidate, font, letter_spacing) > max_width:
                lines.append(current)
                current = word
            else:
                current = candidate

            if measure(current, font, letter_spacing) > max_width:
                # A single word wider than the slot: break it rather than let it
                # bleed across the neighbouring column.
                *head, current = _break_word(
                    current, font, max_width, letter_spacing
                )
                lines.extend(head)
        if current:
            lines.append(current)
    return lines or ['']


def _build(lines, font, line_height_ratio, box_width, box_height, letter_spacing):
    line_height = line_height_ratio * font.size
    widths = [measure(line, font, letter_spacing) for line in lines]
    return Block(
        lines=[Line(text, width) for text, width in zip(lines, widths)],
        font_size=font.size,
        line_height=line_height,
        width=max(widths) if widths else 0.0,
        height=line_height * len(lines),
        overflow_x=any(width > box_width + 0.5 for width in widths),
        overflow_y=line_height * len(lines) > box_height + 0.5,
    )


def _truncate(block, box_height, font, letter_spacing, box_width):
    """Drop the lines that do not fit and mark the last one with an ellipsis."""
    if block.line_height <= 0:
        return block
    keep = max(1, int((box_height + 0.5) // block.line_height))
    if keep >= block.line_count:
        return block

    lines = [line.text for line in block.lines[:keep]]
    tail = lines[-1].rstrip()
    while tail and measure(tail + ELLIPSIS, font, letter_spacing) > box_width:
        tail = tail[:-1].rstrip()
    lines[-1] = tail + ELLIPSIS

    truncated = _build(
        lines, font, block.line_height / font.size, box_width,
        box_height, letter_spacing,
    )
    truncated.truncated = True
    truncated.overflow_y = True
    truncated.shrunk = block.shrunk
    return truncated


def layout(text, box_width, box_height, typography, constraints, theme,
           max_lines=0, truncate=True):
    """Fit ``text`` into a box, shrinking the type if the template allows it.

    Returns a :class:`Block` describing exactly what to draw and whether it
    overflowed -- the validator reads the flags, the drawing code reads the lines.
    """
    text = apply_transform(str(text or ''), typography.transform)
    if not text.strip():
        return Block(font_size=typography.font_size)

    start = int(typography.font_size)
    floor = int(constraints.min_font_size) if constraints.allow_shrink else start
    floor = max(1, min(floor, start))

    block = None
    for size in range(start, floor - 1, -STEP):
        font = fonts.for_typography(typography, theme, size)
        limit = box_height
        if max_lines > 0:
            limit = min(limit, typography.line_height * size * max_lines)

        lines = wrap(
            text, font, box_width, typography.letter_spacing,
            constraints.allow_wrap,
        )
        block = _build(
            lines, font, typography.line_height, box_width, limit,
            typography.letter_spacing,
        )
        block.shrunk = size != start
        if not block.overflows:
            return block

    # Nothing fit. Keep the smallest attempt, trimmed so the slide stays legible;
    # the overflow flag rides along so the validator can fail the page.
    if block is not None and truncate:
        font = fonts.for_typography(typography, theme, block.font_size)
        block = _truncate(
            block, box_height, font, typography.letter_spacing, box_width
        )
    return block or Block(font_size=start)


@dataclass
class ListBlock:
    """A bullet list laid out as one unit."""

    items: List[Block] = field(default_factory=list)
    font_size: int = 0
    height: float = 0.0
    overflow_x: bool = False
    overflow_y: bool = False
    truncated: bool = False
    shrunk: bool = False
    dropped: int = 0              # items that did not fit at all

    @property
    def overflows(self):
        return self.overflow_x or self.overflow_y


def split_items(text, limit=0):
    """Copy for a list arrives newline-separated, sometimes with stray bullets."""
    items = [
        line.strip().lstrip('•-–—*·').strip()
        for line in str(text or '').split('\n')
    ]
    items = [item for item in items if item]
    return items[:limit] if limit > 0 else items


def layout_list(text, box_width, box_height, typography, constraints, theme,
                list_spec):
    """Fit a whole list into a box, shrinking every item together.

    Items are laid out as one unit so they keep a single type size -- a list
    whose third bullet is two points smaller than the others is the tell that a
    layout was fitted item by item.
    """
    items = split_items(text, list_spec.item_count)
    if not items:
        return ListBlock(font_size=typography.font_size)

    indent = 0 if list_spec.marker == 'none' else _marker_indent(
        typography.font_size, list_spec
    )
    start = int(typography.font_size)
    floor = int(constraints.min_font_size) if constraints.allow_shrink else start
    floor = max(1, min(floor, start))

    result = None
    for size in range(start, floor - 1, -STEP):
        font = fonts.for_typography(typography, theme, size)
        scaled_indent = 0 if list_spec.marker == 'none' else _marker_indent(
            size, list_spec
        )
        available = max(1, box_width - scaled_indent)

        blocks = [
            _build(
                wrap(item, font, available, typography.letter_spacing,
                     constraints.allow_wrap),
                font, typography.line_height, available, box_height,
                typography.letter_spacing,
            )
            for item in items
        ]
        gap = list_spec.item_gap * size / max(1, start)
        height = sum(block.height for block in blocks) + gap * (len(blocks) - 1)

        result = ListBlock(
            items=blocks,
            font_size=size,
            height=height,
            overflow_x=any(block.overflow_x for block in blocks),
            overflow_y=height > box_height + 0.5,
            shrunk=size != start,
        )
        if not result.overflows:
            return result

    if result is not None:
        result.overflow_y = True
    return result or ListBlock(font_size=start)


def _marker_indent(font_size, list_spec):
    return int(font_size * 0.42) + list_spec.marker_gap


def draw(image_draw, block, box, typography, color, theme=None):
    """Paint a laid-out block into ``box`` = ``(left, top, width, height)``."""
    if not block.lines:
        return

    font = fonts.for_typography(typography, theme, block.font_size)

    left, top, width, height = box
    used = block.height
    if typography.valign == 'middle':
        cursor = top + (height - used) / 2
    elif typography.valign == 'bottom':
        cursor = top + height - used
    else:
        cursor = top

    # Centre each glyph run inside its line box, so line-height changes do not
    # shift the first line up against the box edge.
    padding = (block.line_height - block.font_size) / 2

    for line in block.lines:
        if typography.align == 'center':
            x = left + (width - line.width) / 2
        elif typography.align == 'right':
            x = left + width - line.width
        else:
            x = left

        _draw_line(
            image_draw, line.text, (x, cursor + padding), font, color,
            typography.letter_spacing,
        )
        cursor += block.line_height


def _draw_line(image_draw, text, origin, font, color, letter_spacing):
    if not text:
        return
    if not letter_spacing:
        image_draw.text(origin, text, font=font, fill=color)
        return

    x, y = origin
    for char in text:
        image_draw.text((x, y), char, font=font, fill=color)
        x += font.getlength(char) + letter_spacing


def chars_per_box(box_width, box_height, typography, theme, font_size=None):
    """How many characters this slot holds -- the copy stage's budget.

    Measured against the real face at the real size rather than guessed from
    area, which is what v1 did and why its budgets were only ever approximate.
    """
    size = int(font_size or typography.font_size)
    font = fonts.for_typography(typography, theme, size)
    # A Cyrillic lowercase average; 'о' is close to the mean advance in Inter.
    unit = measure('о', font, typography.letter_spacing) or size * 0.5
    per_line = max(1, int(box_width / unit))
    lines = max(1, int(box_height / (typography.line_height * size)))
    return per_line * lines
