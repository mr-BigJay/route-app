from __future__ import annotations

import json

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from database.db import DatabaseError, DatabaseManager
from ui.geo_utils import clamp_to_gilan, estimate_route
from ui.route_map_widget import RouteMapWidget
from ui.utils import Page, clear_layout, make_stat_card, show_error, show_success, to_persian_digits


class RoutesPage(Page):
    def __init__(self, db: DatabaseManager) -> None:
        super().__init__("مدیریت مسیر", "ثبت موقعیت نقاط روی نقشه و محاسبه مسافت بین مبدا و مقصد")
        self.setObjectName("routesPage")
        self.db = db
        self._calculating = False

        self.stats_layout = QGridLayout()
        self.stats_layout.setSpacing(12)
        self.root_layout.addLayout(self.stats_layout)

        body = QHBoxLayout()
        body.setDirection(QHBoxLayout.Direction.RightToLeft)
        body.setSpacing(16)
        body.addWidget(self._map_card(), stretch=7)
        body.addWidget(self._panel_card(), stretch=3)
        self.root_layout.addLayout(body, stretch=1)
        self._center_page_header()

    def _center_page_header(self) -> None:
        header = self.root_layout.itemAt(0).widget()
        if header is None:
            return
        layout = header.layout()
        if layout is None:
            return
        for index in range(layout.count()):
            item = layout.itemAt(index)
            widget = item.widget()
            if widget is not None:
                widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
                layout.setAlignment(widget, Qt.AlignmentFlag.AlignHCenter)

    def _map_card(self) -> QWidget:
        card = self.card()
        card.setObjectName("routeMapCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)
        title = QLabel("نقشه گیلان")
        title.setObjectName("sectionTitle")
        self.map_hint = QLabel("برای ثبت موقعیت، نقطه را انتخاب کنید و روی نقشه کلیک کنید.")
        self.map_hint.setObjectName("routeMapHint")
        self.map_hint.setWordWrap(True)
        self.map_widget = RouteMapWidget()
        self.map_widget.setMinimumHeight(420)
        self.map_widget.map_clicked.connect(self._on_map_clicked)
        layout.addWidget(title)
        layout.addWidget(self.map_hint)
        layout.addWidget(self.map_widget, stretch=1)
        return card

    def _panel_card(self) -> QWidget:
        card = self.card()
        card.setObjectName("routePanelCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(16)

        pin_title = QLabel("ثبت موقعیت روی نقشه")
        pin_title.setObjectName("sectionTitle")
        self.pin_location_combo = self._location_combo()
        layout.addWidget(pin_title)
        layout.addWidget(self._field_box("انتخاب نقطه", self.pin_location_combo))

        route_title = QLabel("محاسبه مسیر")
        route_title.setObjectName("sectionTitle")
        self.origin_combo = self._location_combo()
        self.destination_combo = self._location_combo()
        calc_button = self.action_button("محاسبه مسیر")
        calc_button.clicked.connect(self.calculate_route)
        self.distance_label = QLabel("مسافت: —")
        self.distance_label.setObjectName("routeDistanceValue")
        self.route_mode_label = QLabel("")
        self.route_mode_label.setObjectName("routeModeHint")

        layout.addWidget(route_title)
        layout.addWidget(self._field_box("مبدا", self.origin_combo))
        layout.addWidget(self._field_box("مقصد", self.destination_combo))
        layout.addWidget(calc_button)
        layout.addWidget(self.distance_label)
        layout.addWidget(self.route_mode_label)
        layout.addStretch(1)
        return card

    def _location_combo(self) -> QComboBox:
        combo = QComboBox()
        combo.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        combo.setMinimumHeight(34)
        return combo

    def _field_box(self, label: str, widget: QWidget) -> QWidget:
        box = QWidget()
        box.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        layout = QVBoxLayout(box)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        label_widget = QLabel(label)
        label_widget.setObjectName("fieldLabel")
        label_widget.setAlignment(Qt.AlignmentFlag.AlignRight)
        layout.addWidget(label_widget)
        layout.addWidget(widget)
        return box

    def _populate_location_combos(self) -> None:
        locations = self.db.list_locations()
        combos = [self.pin_location_combo, self.origin_combo, self.destination_combo]
        saved = [combo.currentData() for combo in combos]
        for combo, current_id in zip(combos, saved):
            combo.blockSignals(True)
            combo.clear()
            combo.addItem("— انتخاب کنید —", None)
            for location in locations:
                label = f"{location['category_title']} — {location['title']}"
                combo.addItem(label, location["id"])
            index = combo.findData(current_id)
            if index >= 0:
                combo.setCurrentIndex(index)
            combo.blockSignals(False)

    def _marker_payload(self) -> list[dict]:
        markers = []
        for location in self.db.list_mapped_locations():
            markers.append(
                {
                    "id": location["id"],
                    "title": f"{location['category_title']} — {location['title']}",
                    "lat": float(location["latitude"]),
                    "lng": float(location["longitude"]),
                }
            )
        return markers

    def refresh(self) -> None:
        self._populate_location_combos()
        self.map_widget.set_markers(self._marker_payload())
        self.map_widget.clear_route()
        self.distance_label.setText("مسافت: —")
        self.route_mode_label.setText("")
        self._refresh_stats()
        if self.map_widget.uses_web_engine():
            self.map_hint.setText("برای ثبت موقعیت، نقطه را انتخاب کنید و روی نقشه کلیک کنید.")
        else:
            self.map_hint.setText(
                "نقشه آفلاین فعال است. برای ثبت موقعیت، نقطه را انتخاب کنید و روی نقشه دوبار کلیک کنید."
            )

    def _refresh_stats(self) -> None:
        mapped_count = len(self.db.list_mapped_locations())
        cached_count = self.db.count_cached_routes()
        clear_layout(self.stats_layout)
        self.stats_layout.addWidget(
            make_stat_card("نقاط ثبت‌شده روی نقشه", str(mapped_count), "#2563EB", "#EFF6FF"),
            0,
            0,
        )
        self.stats_layout.addWidget(
            make_stat_card("مسیرهای ذخیره‌شده", str(cached_count), "#16A34A", "#F0FDF4"),
            0,
            1,
        )

    def _on_map_clicked(self, latitude: float, longitude: float) -> None:
        location_id = self.pin_location_combo.currentData()
        if not location_id:
            show_error(self, "ابتدا نقطه‌ای را برای ثبت موقعیت انتخاب کنید.")
            return
        latitude, longitude = clamp_to_gilan(latitude, longitude)
        try:
            self.db.update_location_coordinates(int(location_id), latitude, longitude)
        except DatabaseError as exc:
            show_error(self, str(exc))
            return
        show_success(self, "موقعیت نقطه روی نقشه ثبت شد.")
        self.refresh()
        self.pin_location_combo.setCurrentIndex(self.pin_location_combo.findData(location_id))

    def calculate_route(self) -> None:
        if self._calculating:
            return
        origin_id = self.origin_combo.currentData()
        destination_id = self.destination_combo.currentData()
        if not origin_id or not destination_id:
            show_error(self, "مبدا و مقصد را انتخاب کنید.")
            return
        if origin_id == destination_id:
            show_error(self, "مبدا و مقصد نمی‌توانند یکسان باشند.")
            return

        origin = self.db.get_location(int(origin_id))
        destination = self.db.get_location(int(destination_id))
        if not origin or not destination:
            show_error(self, "نقطه انتخاب‌شده یافت نشد.")
            return
        if origin["latitude"] is None or origin["longitude"] is None:
            show_error(self, f"موقعیت «{origin['title']}» روی نقشه ثبت نشده است.")
            return
        if destination["latitude"] is None or destination["longitude"] is None:
            show_error(self, f"موقعیت «{destination['title']}» روی نقشه ثبت نشده است.")
            return

        self._calculating = True
        try:
            cached = self.db.get_cached_route(int(origin_id), int(destination_id))
            if cached:
                distance_km = float(cached["distance_km"])
                points = json.loads(cached["route_points"] or "[]")
                mode = "cached"
            else:
                result = estimate_route(
                    float(origin["latitude"]),
                    float(origin["longitude"]),
                    float(destination["latitude"]),
                    float(destination["longitude"]),
                )
                distance_km = float(result["distance_km"])
                points = result["points"]
                mode = str(result["mode"])
                try:
                    self.db.save_route_cache(
                        int(origin_id),
                        int(destination_id),
                        distance_km,
                        json.dumps(points, ensure_ascii=False),
                    )
                except DatabaseError as exc:
                    show_error(self, str(exc))
                    return

            self.map_widget.draw_route([(float(p[0]), float(p[1])) for p in points])
            self.distance_label.setText(f"مسافت: {to_persian_digits(f'{distance_km:.1f}')} کیلومتر")
            mode_text = {
                "road": "مسافت بر اساس مسیر جاده‌ای (آنلاین)",
                "estimated": "مسافت تخمینی (آفلاین)",
                "cached": "مسافت از مسیر ذخیره‌شده",
            }
            self.route_mode_label.setText(mode_text.get(mode, ""))
            self._refresh_stats()
        finally:
            self._calculating = False
