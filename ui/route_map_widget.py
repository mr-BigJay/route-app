"""Interactive map for route management (WebEngine or canvas fallback)."""

from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt, QUrl, Signal, Slot
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

from ui.geo_utils import RUDSAR_BOUNDS

_MAP_DIR = Path(__file__).resolve().parent.parent / "assets" / "map"
_MAP_HTML = _MAP_DIR / "route_map.html"


def _webengine_available() -> bool:
    try:
        from PySide6.QtWebEngineWidgets import QWebEngineView  # noqa: F401

        return True
    except ImportError:
        return False


class _MapBridge(QWidget):
    """Qt WebChannel bridge for Leaflet map."""

    map_clicked = Signal(float, float)
    map_ready = Signal()

    @Slot(float, float)
    def mapClicked(self, lat: float, lng: float) -> None:
        self.map_clicked.emit(float(lat), float(lng))

    @Slot()
    def mapReady(self) -> None:
        self.map_ready.emit()


class CanvasRouteMap(QGraphicsView):
    """Offline canvas map when WebEngine is unavailable."""

    map_clicked = Signal(float, float)
    map_ready = Signal()

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
        self._press_pos = None
        self._scene.setSceneRect(self._scene_rect)
        self._draw_background()
        self.map_ready.emit()

    def _lat_lng_to_scene(self, lat: float, lng: float) -> QPointF:
        min_lat = RUDSAR_BOUNDS["lat_min"]
        max_lat = RUDSAR_BOUNDS["lat_max"]
        min_lng = RUDSAR_BOUNDS["lng_min"]
        max_lng = RUDSAR_BOUNDS["lng_max"]
        w = self._scene_rect.width()
        h = self._scene_rect.height()
        x = (lng - min_lng) / (max_lng - min_lng) * w
        y = (max_lat - lat) / (max_lat - min_lat) * h
        return QPointF(x, y)

    def _scene_to_lat_lng(self, point: QPointF) -> tuple[float, float]:
        min_lat = RUDSAR_BOUNDS["lat_min"]
        max_lat = RUDSAR_BOUNDS["lat_max"]
        min_lng = RUDSAR_BOUNDS["lng_min"]
        max_lng = RUDSAR_BOUNDS["lng_max"]
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
        hint = self._scene.addText("نقشه آفلاین شهرستان رودسر — کلیک برای ثبت موقعیت")
        hint.setDefaultTextColor(QColor("#64748b"))
        hint.setFont(QFont("Tahoma", 9))
        hint.setPos(170, 20)
        hint.setZValue(1)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.fitInView(self._scene_rect, Qt.AspectRatioMode.KeepAspectRatio)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._press_pos = event.position()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if (
            event.button() == Qt.MouseButton.LeftButton
            and self._press_pos is not None
            and (event.position() - self._press_pos).manhattanLength() < 8
        ):
            pt = self.mapToScene(event.position().toPoint())
            if self._scene_rect.contains(pt):
                lat, lng = self._scene_to_lat_lng(pt)
                self.map_clicked.emit(lat, lng)
                event.accept()
                self._press_pos = None
                return
        self._press_pos = None
        super().mouseReleaseEvent(event)

    def set_markers(self, markers: list[dict]) -> None:
        self._markers = list(markers)
        self._redraw()

    def draw_route(self, points: list[tuple[float, float]]) -> None:
        self._route = list(points)
        self._redraw()

    def clear_route(self) -> None:
        self._route = []
        self._redraw()

    def _marker_color(self, role: str | None) -> QColor:
        if role == "origin":
            return QColor("#16a34a")
        if role == "destination":
            return QColor("#dc2626")
        return QColor("#2563eb")

    def _redraw(self) -> None:
        for item in list(self._scene.items()):
            if getattr(item, "_route_item", False):
                self._scene.removeItem(item)
        for marker in self._markers:
            pt = self._lat_lng_to_scene(float(marker["lat"]), float(marker["lng"]))
            color = self._marker_color(marker.get("role"))
            dot = QGraphicsEllipseItem(pt.x() - 8, pt.y() - 8, 16, 16)
            dot.setBrush(QBrush(color))
            dot.setPen(QPen(QColor("#ffffff"), 2))
            dot._route_item = True  # type: ignore[attr-defined]
            dot.setZValue(10)
            self._scene.addItem(dot)
            label_text = str(marker.get("label") or marker.get("title") or "")
            if label_text:
                label = QGraphicsTextItem(label_text)
                label.setDefaultTextColor(QColor("#0f172a"))
                label.setFont(QFont("Tahoma", 8, QFont.Weight.Bold))
                label.setPos(pt.x() + 10, pt.y() - 18)
                label._route_item = True  # type: ignore[attr-defined]
                label.setZValue(11)
                self._scene.addItem(label)
        if len(self._route) >= 2:
            pen = QPen(QColor("#2563eb"), 4)
            for index in range(len(self._route) - 1):
                start = self._lat_lng_to_scene(*self._route[index])
                end = self._lat_lng_to_scene(*self._route[index + 1])
                line = QGraphicsLineItem(start.x(), start.y(), end.x(), end.y())
                line.setPen(pen)
                line._route_item = True  # type: ignore[attr-defined]
                line.setZValue(5)
                self._scene.addItem(line)


if _webengine_available():
    from PySide6.QtWebChannel import QWebChannel
    from PySide6.QtWebEngineCore import QWebEngineSettings
    from PySide6.QtWebEngineWidgets import QWebEngineView

    class WebEngineRouteMap(QWebEngineView):
        map_clicked = Signal(float, float)
        map_ready = Signal()

        def __init__(self, parent: QWidget | None = None) -> None:
            super().__init__(parent)
            self.setObjectName("routeMapWeb")
            settings = self.page().settings()
            settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
            settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True)
            settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)
            self._bridge = _MapBridge()
            self._bridge.map_clicked.connect(self.map_clicked)
            self._bridge.map_ready.connect(self._on_bridge_ready)
            channel = QWebChannel(self.page())
            channel.registerObject("bridge", self._bridge)
            self.page().setWebChannel(channel)
            self._js_ready = False
            self._pending_scripts: list[str] = []
            self._pending_markers: list[dict] = []
            self._pending_route: list[tuple[float, float]] | None = None
            self.loadFinished.connect(self._on_load_finished)
            if _MAP_HTML.is_file():
                self.load(QUrl.fromLocalFile(str(_MAP_HTML.resolve())))

        def _on_load_finished(self, ok: bool) -> None:
            if not ok:
                return
            self.page().runJavaScript("typeof map !== 'undefined' && map !== null")

        def _on_bridge_ready(self) -> None:
            self._js_ready = True
            for script in self._pending_scripts:
                self.page().runJavaScript(script)
            self._pending_scripts.clear()
            self.map_ready.emit()
            if self._pending_markers:
                self.set_markers(self._pending_markers)
            if self._pending_route is not None:
                if self._pending_route:
                    self.draw_route(self._pending_route)
                else:
                    self.clear_route()

        def _run_js(self, script: str) -> None:
            if self._js_ready:
                self.page().runJavaScript(script)
            else:
                self._pending_scripts.append(script)

        def set_markers(self, markers: list[dict]) -> None:
            self._pending_markers = list(markers)
            payload = json.dumps(markers, ensure_ascii=False)
            self._run_js(f"setMarkers({json.dumps(payload)});")

        def draw_route(self, points: list[tuple[float, float]]) -> None:
            self._pending_route = list(points)
            payload = json.dumps([[point[0], point[1]] for point in points])
            self._run_js(f"drawRoute({json.dumps(payload)});")

        def clear_route(self) -> None:
            self._pending_route = []
            self._run_js("clearRoute();")


def _create_map_widget(parent: QWidget | None = None) -> QWidget:
    if _webengine_available():
        try:
            return WebEngineRouteMap(parent)
        except Exception:
            pass
    return CanvasRouteMap(parent)


class RouteMapWidget(QWidget):
    """Map container; picks WebEngine or canvas automatically."""

    map_clicked = Signal(float, float)
    map_ready = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("routeMapWidget")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._map = _create_map_widget(self)
        self._map.map_clicked.connect(self.map_clicked)
        if hasattr(self._map, "map_ready"):
            self._map.map_ready.connect(self.map_ready)
        layout.addWidget(self._map)
        self._uses_web_engine = not isinstance(self._map, CanvasRouteMap)

    def set_markers(self, markers: list[dict]) -> None:
        self._map.set_markers(markers)

    def draw_route(self, points: list[tuple[float, float]]) -> None:
        self._map.draw_route(points)

    def clear_route(self) -> None:
        self._map.clear_route()

    def uses_web_engine(self) -> bool:
        return self._uses_web_engine

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if self._uses_web_engine and hasattr(self._map, "_run_js"):
            self._map._run_js("if (typeof map !== 'undefined' && map) { map.invalidateSize(); }")
