"""Map tool that lets the user drag a rectangle on the canvas as the area of interest."""
from qgis.PyQt.QtCore import pyqtSignal, Qt
from qgis.PyQt.QtGui import QColor
from qgis.gui import QgsMapTool, QgsRubberBand
from qgis.core import QgsRectangle, QgsPointXY, QgsWkbTypes


class RectangleMapTool(QgsMapTool):
    """Drag to draw a rectangle; emits the rectangle (in the canvas CRS) when released."""

    finished = pyqtSignal(QgsRectangle)

    def __init__(self, canvas):
        super().__init__(canvas)
        self.canvas = canvas
        self._band = QgsRubberBand(canvas, QgsWkbTypes.PolygonGeometry)
        self._band.setColor(QColor(0, 80, 170, 60))
        self._band.setStrokeColor(QColor(0, 80, 170))
        self._band.setWidth(2)
        self._start = None
        self._dragging = False

    def _show(self, rect):
        self._band.reset(QgsWkbTypes.PolygonGeometry)
        pts = [
            QgsPointXY(rect.xMinimum(), rect.yMinimum()),
            QgsPointXY(rect.xMaximum(), rect.yMinimum()),
            QgsPointXY(rect.xMaximum(), rect.yMaximum()),
            QgsPointXY(rect.xMinimum(), rect.yMaximum()),
        ]
        for i, p in enumerate(pts):
            self._band.addPoint(p, i == len(pts) - 1)

    def canvasPressEvent(self, event):
        if event.button() != Qt.LeftButton:
            return
        self._start = self.toMapCoordinates(event.pos())
        self._dragging = True

    def canvasMoveEvent(self, event):
        if not self._dragging or self._start is None:
            return
        self._show(QgsRectangle(self._start, self.toMapCoordinates(event.pos())))

    def canvasReleaseEvent(self, event):
        if event.button() != Qt.LeftButton or not self._dragging or self._start is None:
            return
        self._dragging = False
        rect = QgsRectangle(self._start, self.toMapCoordinates(event.pos()))
        self._start = None
        if rect.isEmpty():
            self.clear()
            return
        self._show(rect)
        self.finished.emit(rect)

    def clear(self):
        self._band.reset(QgsWkbTypes.PolygonGeometry)

    def deactivate(self):
        self.clear()
        super().deactivate()
