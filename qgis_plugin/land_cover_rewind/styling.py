"""Renderers for the result rasters. Imported only inside QGIS."""
from qgis.PyQt.QtGui import QColor
from qgis.core import (
    QgsPalettedRasterRenderer,
    QgsColorRampShader,
    QgsRasterShader,
    QgsSingleBandPseudoColorRenderer,
)

from . import core


def _paletted(layer, classes):
    """classes: list of (value, (r, g, b), label)."""
    items = [
        QgsPalettedRasterRenderer.Class(value, QColor(r, g, b), label)
        for value, (r, g, b), label in classes
    ]
    renderer = QgsPalettedRasterRenderer(layer.dataProvider(), 1, items)
    layer.setRenderer(renderer)
    layer.triggerRepaint()


def apply_builtup_style(layer):
    _paletted(layer, core.BUILTUP_CLASSES)


def apply_lc4_style(layer):
    _paletted(layer, core.LC4_CLASSES)


def apply_first_detection_style(layer, epochs):
    """Colour the first-detection epochs with a dark-to-bright ramp.

    Only pixels whose value falls within the epoch range [lo, hi] are drawn.
    The ramp is clipped, so "never built-up" pixels (value 0, below lo) and the
    raster nodata (-1) stay fully transparent instead of being clamped to the
    oldest-epoch colour.
    """
    years = core.normalize_epochs(epochs)
    if not years:
        return
    lo, hi = years[0], years[-1]
    span = max(hi - lo, 1)
    # dark blue (oldest) -> yellow-green (newest)
    start = (44, 20, 90)
    end = (170, 210, 60)

    def lerp(a, b, t):
        return int(round(a + (b - a) * t))

    ramp = QgsColorRampShader(lo, hi)
    ramp.setColorRampType(QgsColorRampShader.Interpolated)
    ramp.setClip(True)  # values outside [lo, hi] (0 = never built-up, -1 = nodata) stay transparent
    items = []
    for y in years:
        t = (y - lo) / span
        col = QColor(lerp(start[0], end[0], t), lerp(start[1], end[1], t), lerp(start[2], end[2], t))
        items.append(QgsColorRampShader.ColorRampItem(y, col, str(y)))
    ramp.setColorRampItemList(items)
    shader = QgsRasterShader()
    shader.setRasterShaderFunction(ramp)
    renderer = QgsSingleBandPseudoColorRenderer(layer.dataProvider(), 1, shader)
    layer.setRenderer(renderer)
    layer.triggerRepaint()


def style_layer(layer, kind, epochs=None):
    """Apply the right renderer for a result layer described by core.result_layers."""
    if kind == "built_up":
        apply_builtup_style(layer)
    elif kind == "land_cover_4class":
        apply_lc4_style(layer)
    elif kind == "first_detection":
        apply_first_detection_style(layer, epochs or core.EPOCHS)
