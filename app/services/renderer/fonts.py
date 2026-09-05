"""Font loading.

The faces are committed to the repository rather than taken from the host: a
slide is only as reliable as its font file, and a server without a Cyrillic face
renders Russian copy as tofu -- exactly the failure the deterministic renderer
exists to eliminate. Inter and Playfair Display are both OFL and both cover
Cyrillic; their licences sit next to them.

Fonts are cached per thread. Generations run on background threads and a
FreeType face is not safe to share between them, so each thread gets its own.
"""

import logging
import threading
from pathlib import Path

from PIL import ImageFont

logger = logging.getLogger(__name__)

FONT_DIR = Path(__file__).resolve().parents[2] / 'static' / 'fonts'

SANS = 'Inter'
SERIF = 'Playfair Display'

# family -> weight -> (filename, variation name or None)
_FACES = {
    SANS: {
        400: ('Inter-Regular.ttf', None),
        500: ('Inter-Medium.ttf', None),
        600: ('Inter-SemiBold.ttf', None),
        700: ('Inter-Bold.ttf', None),
        900: ('Inter-Black.ttf', None),
    },
    SERIF: {
        400: ('PlayfairDisplay-Variable.ttf', 'Regular'),
        500: ('PlayfairDisplay-Variable.ttf', 'Medium'),
        600: ('PlayfairDisplay-Variable.ttf', 'SemiBold'),
        700: ('PlayfairDisplay-Variable.ttf', 'Bold'),
        900: ('PlayfairDisplay-Variable.ttf', 'Black'),
    },
}

_ITALICS = {SANS: 'Inter-Italic.ttf'}

# Aliases, so a template may say "serif" or name a font it does not ship.
_ALIASES = {
    'inter': SANS,
    'sans': SANS,
    'sans-serif': SANS,
    'playfair': SERIF,
    'playfair display': SERIF,
    'serif': SERIF,
}

_local = threading.local()


class FontError(Exception):
    """A face the renderer cannot load. Always a packaging problem."""


def resolve_family(name, theme=None):
    """``'heading'``/``'body'`` -> the theme's face; anything else -> a real family."""
    key = str(name or '').strip()
    if theme is not None and key in ('heading', 'body'):
        key = theme.font_heading if key == 'heading' else theme.font_body
    return _ALIASES.get(key.lower(), key if key in _FACES else SANS)


def _nearest_weight(family, weight):
    available = sorted(_FACES[family])
    return min(available, key=lambda candidate: abs(candidate - int(weight)))


def _cache():
    cache = getattr(_local, 'fonts', None)
    if cache is None:
        cache = _local.fonts = {}
    return cache


def load(family, weight=400, size=24, italic=False, theme=None):
    """A ``FreeTypeFont`` for this face at this size, cached per thread."""
    family = resolve_family(family, theme)
    if family not in _FACES:
        family = SANS
    weight = _nearest_weight(family, weight)
    size = max(1, int(round(size)))
    italic = bool(italic) and family in _ITALICS

    key = (family, weight, size, italic)
    cache = _cache()
    if key in cache:
        return cache[key]

    if italic:
        filename, variation = _ITALICS[family], None
    else:
        filename, variation = _FACES[family][weight]

    path = FONT_DIR / filename
    try:
        font = ImageFont.truetype(str(path), size)
        if variation:
            font.set_variation_by_name(variation)
    except OSError as exc:
        raise FontError(f'cannot load font {path}: {exc}') from exc

    cache[key] = font
    return font


def for_typography(typography, theme, size=None):
    """The font a :class:`~app.spec.Typography` block asks for."""
    return load(
        typography.family,
        typography.font_weight,
        size if size is not None else typography.font_size,
        typography.italic,
        theme,
    )


def available():
    """Faces present on disk. Used by the checks and by ``manage.py`` commands."""
    found = {}
    for family, weights in _FACES.items():
        found[family] = sorted(
            weight for weight, (filename, _) in weights.items()
            if (FONT_DIR / filename).exists()
        )
    return found
