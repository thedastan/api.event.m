"""Slide Spec v2: the intermediate model between a template and a rendered PNG.

A spec says *what* is on a slide and *where* -- in template coordinates, with
real typography attached. Everything downstream reads it: the copywriter derives
its character budgets from it, the asset generator derives its image prompts from
it, and the renderer draws it. The AI never writes one; it only fills in the
strings a spec asks for.
"""

from .schema import (
    Constraints,
    Content,
    Element,
    ImageSpec,
    Layout,
    ListSpec,
    ShapeSpec,
    SlideSpec,
    Theme,
    Typography,
)
from .validate import SpecError, validate_spec

__all__ = [
    'Constraints',
    'Content',
    'Element',
    'ImageSpec',
    'Layout',
    'ListSpec',
    'ShapeSpec',
    'SlideSpec',
    'SpecError',
    'Theme',
    'Typography',
    'validate_spec',
]
