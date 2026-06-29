"""Interactive map for route management (WebEngine or canvas fallback)."""

from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (
    QGraphicsEllipseItem,
    QGraphicsLineItem,
    QGraphicsScene,
    QGraphicsTextItem,
    QGraphicsView,
    QVBoxLayout,
    QWidget,
)

from ui.geo_utils import GILAN_BOUNDS

_WEBENGINE_AVAILABLE = False
try:
    from PySide6.QtCore import QUrl
    from PySide6.QtWebChannel import QWebChannel
    from PySide6.QtWebEngineCore import QWebEnginePage
    from PySide6.QtWebEngineWidgets import QWebEngineView

    _WEBENGINE_AVAILABLE = True
except ImportError:
    QUrl = None  # type: ignore
    QWebChannel = None  # type: ignore
    QWebEnginePage = None  # type: ignore
    QWebEngineView = None  # type: ignore

_MAP_HTML = Path(__file__).resolve().parent.parent / "assets" / "map" / "route_map.html"


class _MapBridge(QWidget):
  """Qt WebChannel bridge for Leaflet map."""

  map_clicked = Signal(float, float)

  def mapClicked(self, lat: float, lng: float) -> None:
    self.map_clicked.emit(lat, lng)


class CanvasRouteMap(QGraphicsView):
  """Offline canvas map when WebEngine is unavailable."""

  map_clicked = Signal(float, float)

  def __init__(self, parent: QWidget | None = None) -> None:
    super().__init__(parent)
    self.setObjectName("routeMapCanvas")
    self.setRenderHint(QPainter.RenderHint.Antialiasing)
    self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
    self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
    self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    self._scene = QGraphicsScene(self)
    self.setScene(self._scene)
    self._markers: list[dict] = []
    self._route: list[tuple[float, float]] = []
    self._scene_rect = QRectF(0, 0, 800, 600)
    self._scene.setSceneRect(self._scene_rect)
    self._draw_background()

  def _lat_lng_to_scene(self, lat: float, lng: float) -> QPointF:
    min_lat = GILAN_BOUNDS["lat_min"]
    max_lat = GILAN_BOUNDS["lat_max"]
    min_lng = GILAN_BOUNDS["lng_min"]
    max_lng = GILAN_BOUNDS["lng_max"]
    w = self._scene_rect.width()
    h = self._scene_rect.height()
    x = (lng - min_lng) / (max_lng - min_lng) * w
    y = (max_lat - lat) / (max_lat - min_lat) * h
    return QPointF(x, y)

  def _scene_to_lat_lng(self, point: QPointF) -> tuple[float, float]:
    min_lat = GILAN_BOUNDS["lat_min"]
    max_lat = GILAN_BOUNDS["lat_max"]
    min_lng = GILAN_BOUNDS["lng_min"]
    max_lng = GILAN_BOUNDS["lng_max"]
    w = self._scene_rect.width()
    h = self._scene_rect.height()
    lng = min_lng + (point.x() / w) * (max_lng - min_lng)
    lat = max_lat - (point.y() / h) * (max_lat - min_lat)
    return lat, lng

  def _draw_background(self) -> None:
    self._scene.addRect(
      self._scene_rect,
      QPen(Qt.PenStyle.NoPen),
      QBrush(QColor("#dbeafe")),
    )
    land = self._scene.addRect(
      QRectF(40, 80, 720, 440),
      QPen(QColor("#94a3b8"), 1),
      QBrush(QColor("#dcfce7")),
    )
    land.setZValue(0)
    hint = self._scene.addText("نقشه آفلاین — دوبار کلیک برای ثبت موقعیت")
    hint.setDefaultTextColor(QColor("#64748b"))
    hint.setFont(QFont("Tahoma", 9))
    hint.setPos(180, 20)
    hint.setZValue(1)

  def resizeEvent(self, event) -> None:
    super().resizeEvent(event)
    self.fitInView(self._scene_rect, Qt.AspectRatioMode.KeepAspectRatio)

  def mouseDoubleClickEvent(self, event) -> None:
    if event.button() == Qt.MouseButton.LeftButton:
      pt = self.mapToScene(event.position().toPoint())
      lat, lng = self._scene_to_lat_lng(pt)
      self.map_clicked.emit(lat, lng)
      event.accept()
      return
    super().mouseDoubleClickEvent(event)

  def set_markers(self, markers: list[dict]) -> None:
    self._markers = list(markers)
    self._redraw()

  def draw_route(self, points: list[tuple[float, float]]) -> None:
    self._route = list(points)
    self._redraw()

  def clear_route(self) -> None:
    self._route = []
    self._redraw()

  def _redraw(self) -> None:
    for item in list(self._scene.items()):
      if getattr(item, "_route_item", False):
        self._scene.removeItem(item)
    for m in self._markers:
      pt = self._lat_lng_to_scene(float(m["lat"]), float(m["lng"]))
      dot = QGraphicsEllipseItem(pt.x() - 7, pt.y() - 7, 14, 14)
      dot.setBrush(QBrush(QColor("#dc2626")))
      dot.setPen(QPen(QColor("#ffffff"), 2))
      dot._route_item = True  # type: ignore[attr-defined]
      dot.setZValue(10)
      self._scene.addItem(dot)
      label = QGraphicsTextItem(str(m.get("title", "")))
      label.setDefaultTextColor(QColor("#0f172a"))
      label.setFont(QFont("Tahoma", 8, QFont.Weight.Bold))
      label.setPos(pt.x() + 10, pt.y() - 18)
      label._route_item = True  # type: ignore[attr-defined]
      label.setZValue(11)
      self._scene.addItem(label)
    if len(self._route) >= 2:
      pen = QPen(QColor("#2563eb"), 4)
      for i in range(len(self._route) - 1):
        a = self._lat_lng_to_scene(*self._route[i])
        b = self._lat_lng_to_scene(*self._route[i + 1])
        line = QGraphicsLineItem(a.x(), a.y(), b.x(), b.y())
        line.setPen(pen)
        line._route_item = True  # type: ignore[attr-defined]
        line.setZValue(5)
        self._scene.addItem(line)


if _WEBENGINE_AVAILABLE:

  class WebEngineRouteMap(QWebEngineView):
    map_clicked = Signal(float, float)

    def __init__(self, parent: QWidget | None = None) -> None:
      super().__init__(parent)
      self.setObjectName("routeMapWeb")
      self._bridge = _MapBridge()
      self._bridge.map_clicked.connect(self.map_clicked)
      channel = QWebChannel(self.page())
      channel.registerObject("bridge", self._bridge)
      self.page().setWebChannel(channel)
      if _MAP_HTML.is_file():
        self.load(QUrl.fromLocalFile(str(_MAP_HTML.resolve())))

    def _run_js(self, script: str) -> None:
      self.page().runJavaScript(script)

    def set_markers(self, markers: list[dict]) -> None:
      payload = json.dumps(markers, ensure_ascii=False)
      self._run_js(f"setMarkers({json.dumps(payload)});")

    def draw_route(self, points: list[tuple[float, float]]) -> None:
      payload = json.dumps([[p[0], p[1]] for p in points])
      self._run_js(f"drawRoute({json.dumps(payload)});")

    def clear_route(self) -> None:
      self._run_js("clearRoute();")


class RouteMapWidget(QWidget):
  """Map container; picks WebEngine or canvas automatically."""

  map_clicked = Signal(float, float)

  def __init__(self, parent: QWidget | None = None) -> None:
    super().__init__(parent)
    self.setObjectName("routeMapWidget")
    layout = QVBoxLayout(self)
    layout.setContentsMargins(0, 0, 0, 0)
    if _WEBENGINE_AVAILABLE:
      self._map = WebEngineRouteMap(self)
    else:
      self._map = CanvasRouteMap(self)
    self._map.map_clicked.connect(self.map_clicked)
    layout.addWidget(self._map)

  def set_markers(self, markers: list[dict]) -> None:
    self._map.set_markers(markers)

  def draw_route(self, points: list[tuple[float, float]]) -> None:
    self._map.draw_route(points)

  def clear_route(self) -> None:
    self._map.clear_route()

  def uses_web_engine(self) -> bool:
    return _WEBENGINE_AVAILABLE
