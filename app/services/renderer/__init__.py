"""Deterministic slide renderer.

The renderer owns layout, typography and composition; the models own words and
photographs. Give :func:`render_slide` a filled :class:`~app.spec.SlideSpec` and
the assets generated for its image slots, and it returns PNG bytes plus a report
of anything that did not fit.
"""

from .render import RenderError, render_slide

__all__ = ['RenderError', 'render_slide']
