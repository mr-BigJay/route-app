from __future__ import annotations

import json
from enum import Enum

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDoubleSpinBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from database.db import DatabaseError, DatabaseManager
from ui.form_widgets import NoWheelComboBox, configure_combo_field, configure_spin_field
from ui.geo_utils import clamp_to_gilan, estimate_route
from ui.route_map_widget import RouteMapWidget
from ui.utils import Page, clear_layout, make_stat_card, show_error, show_success, to_persian_digits


class PinTarget(Enum):
    ORIGIN = "origin"
    DESTINATION = "destination"


class RoutesPage(Page):
    def __init__(self, db: DatabaseManager) -> None:
        super().__init__("مدیریت مسیر", "ثبت موقعیت مبدا و مقصد روی نقشه و محاسبه مسافت")
        self.setObjectName("routesPage")
        self.db = db
        self._calculating = False
        self._pin_target = PinTarget.ORIGIN
        self._map_ready = False

        self.stats_layout = QGridLayout()
        self.stats_layout.setSpacing(12)
        self.root_layout.addLayout(self.stats_layout)

        body = QHBoxLayout()
        body.setDirection(QHBoxLayout.Direction.RightToLeft)
        body.setSpacing(16)
        panel = self._panel_card()
        map_card = self._map_card()
        body.addWidget(map_card, stretch=7)
        body.addWidget(panel, stretch=3)
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
        self.map_hint = QLabel(self._pin_hint_text())
        self.map_hint.setObjectName("routeMapHint")
        self.map_hint.setWordWrap(True)
        self.map_widget = RouteMapWidget()
        self.map_widget.setMinimumHeight(420)
        self.map_widget.map_clicked.connect(self._on_map_clicked)
        self.map_widget.map_ready.connect(self._on_map_ready)
        layout.addWidget(title)
        layout.addWidget(self.map_hint)
        layout.addWidget(self.map_widget, stretch=1)
        return card

    def _panel_card(self) -> QWidget:
        card = self.card()
        card.setObjectName("routePanelCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(14)

        origin_title = QLabel("مبدا (A)")
        origin_title.setObjectName("sectionTitle")
        self.origin_category_combo = self._category_combo()
        self.origin_location_combo = self._location_combo()
        self.origin_category_combo.currentIndexChanged.connect(
            lambda: self._populate_location_combo(self.origin_category_combo, self.origin_location_combo)
        )
        self.origin_location_combo.currentIndexChanged.connect(self._on_endpoint_changed)
        self.origin_category_combo.currentIndexChanged.connect(self._on_endpoint_changed)

        destination_title = QLabel("مقصد (B)")
        destination_title.setObjectName("sectionTitle")
        self.destination_category_combo = self._category_combo()
        self.destination_location_combo = self._location_combo()
        self.destination_category_combo.currentIndexChanged.connect(
            lambda: self._populate_location_combo(self.destination_category_combo, self.destination_location_combo)
        )
        self.destination_location_combo.currentIndexChanged.connect(self._on_endpoint_changed)
        self.destination_category_combo.currentIndexChanged.connect(self._on_endpoint_changed)

        pin_buttons = QHBoxLayout()
        pin_buttons.setSpacing(8)
        self.origin_pin_button = self._pin_button("ثبت مبدا روی نقشه", PinTarget.ORIGIN)
        self.destination_pin_button = self._pin_button("ثبت مقصد روی نقشه", PinTarget.DESTINATION)
        pin_buttons.addWidget(self.origin_pin_button)
        pin_buttons.addWidget(self.destination_pin_button)

        route_title = QLabel("محاسبه مسافت")
        route_title.setObjectName("sectionTitle")
        calc_button = self.action_button("محاسبه مسیر")
        calc_button.clicked.connect(self.calculate_route)
        self.distance_input = QDoubleSpinBox()
        configure_spin_field(self.distance_input)
        self.distance_input.setRange(0, 1_000_000)
        self.distance_input.setDecimals(1)
        self.distance_input.setSuffix(" km")
        self.distance_input.setReadOnly(True)
        self.distance_input.setButtonSymbols(QDoubleSpinBox.ButtonSymbols.NoButtons)
        self.route_mode_label = QLabel("")
        self.route_mode_label.setObjectName("routeModeHint")
        self.route_mode_label.setWordWrap(True)

        layout.addWidget(origin_title)
        layout.addWidget(self._field_box("دسته‌بندی", self.origin_category_combo))
        layout.addWidget(self._field_box("نقطه", self.origin_location_combo))
        layout.addWidget(destination_title)
        layout.addWidget(self._field_box("دسته‌بندی", self.destination_category_combo))
        layout.addWidget(self._field_box("نقطه", self.destination_location_combo))
        layout.addLayout(pin_buttons)
        layout.addWidget(route_title)
        layout.addWidget(self._field_box("مسافت", self.distance_input))
        layout.addWidget(calc_button)
        layout.addWidget(self.route_mode_label)
        layout.addStretch(1)
        self._update_pin_buttons()
        return card

    def _category_combo(self) -> NoWheelComboBox:
        combo = NoWheelComboBox()
        configure_combo_field(combo)
        combo.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        return combo

    def _location_combo(self) -> NoWheelComboBox:
        combo = NoWheelComboBox()
        configure_combo_field(combo)
        combo.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        return combo

    def _pin_button(self, title: str, target: PinTarget) -> QPushButton:
        button = QPushButton(title)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setProperty("role", "secondary")
        button.setProperty("pinTarget", target.value)
        button.clicked.connect(lambda: self._set_pin_target(target))
        return button

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

    def _set_pin_target(self, target: PinTarget) -> None:
        self._pin_target = target
        self._update_pin_buttons()
        self.map_hint.setText(self._pin_hint_text())

    def _update_pin_buttons(self) -> None:
        for button, target in (
            (self.origin_pin_button, PinTarget.ORIGIN),
            (self.destination_pin_button, PinTarget.DESTINATION),
        ):
            active = self._pin_target == target
            button.setProperty("active", active)
            button.style().unpolish(button)
            button.style().polish(button)

    def _pin_hint_text(self) -> str:
        if self._pin_target == PinTarget.ORIGIN:
            point = self._selected_location_title(self.origin_category_combo, self.origin_location_combo)
            return f"مبدا (A) فعال است. نقطه «{point}» را انتخاب کنید و روی نقشه کلیک کنید."
        point = self._selected_location_title(self.destination_category_combo, self.destination_location_combo)
        return f"مقصد (B) فعال است. نقطه «{point}» را انتخاب کنید و روی نقشه کلیک کنید."

    def _selected_location_title(
        self,
        category_combo: NoWheelComboBox,
        location_combo: NoWheelComboBox,
    ) -> str:
        category_id = category_combo.currentData()
        title = location_combo.currentText().strip()
        if category_id and title:
            return title
        return "—"

    def _populate_category_combos(self) -> None:
        for combo in (self.origin_category_combo, self.destination_category_combo):
            current = combo.currentData()
            combo.blockSignals(True)
            combo.clear()
            for category in self.db.list_categories():
                combo.addItem(category["title"], category["id"])
            index = combo.findData(current)
            combo.setCurrentIndex(index if index >= 0 else 0)
            combo.blockSignals(False)

    def _populate_location_combo(
        self,
        category_combo: NoWheelComboBox,
        location_combo: NoWheelComboBox,
    ) -> None:
        category_id = category_combo.currentData()
        current = location_combo.currentText()
        location_combo.blockSignals(True)
        location_combo.clear()
        for location in self.db.list_locations():
            if category_id is None or location["category_id"] == category_id:
                location_combo.addItem(location["title"], location["id"])
        if current:
            index = location_combo.findText(current)
            if index >= 0:
                location_combo.setCurrentIndex(index)
        location_combo.blockSignals(False)

    def _location_id_from_combos(
        self,
        category_combo: NoWheelComboBox,
        location_combo: NoWheelComboBox,
    ) -> int | None:
        location_id = location_combo.currentData()
        if location_id is not None:
            return int(location_id)
        category_id = category_combo.currentData()
        title = location_combo.currentText().strip()
        if category_id is None or not title:
            return None
        return self.db.find_location_id(int(category_id), title)

    def _marker_payload(self) -> list[dict]:
        origin_id = self._location_id_from_combos(self.origin_category_combo, self.origin_location_combo)
        destination_id = self._location_id_from_combos(
            self.destination_category_combo,
            self.destination_location_combo,
        )
        markers: list[dict] = []
        for location in self.db.list_mapped_locations():
            location_id = int(location["id"])
            role = None
            label = location["title"]
            if location_id == origin_id:
                role = "origin"
                label = f"A — {location['title']}"
            elif location_id == destination_id:
                role = "destination"
                label = f"B — {location['title']}"
            markers.append(
                {
                    "id": location_id,
                    "title": location["title"],
                    "label": label,
                    "lat": float(location["latitude"]),
                    "lng": float(location["longitude"]),
                    "role": role,
                }
            )
        return markers

    def _on_endpoint_changed(self) -> None:
        self.map_hint.setText(self._pin_hint_text())
        self._update_map_markers()

    def _on_map_ready(self) -> None:
        self._map_ready = True
        self._update_map_markers()

    def _update_map_markers(self) -> None:
        if not self._map_ready:
            return
        self.map_widget.set_markers(self._marker_payload())

    def refresh(self) -> None:
        self._populate_category_combos()
        self._populate_location_combo(self.origin_category_combo, self.origin_location_combo)
        self._populate_location_combo(self.destination_category_combo, self.destination_location_combo)
        self._update_map_markers()
        self.map_widget.clear_route()
        self.distance_input.setValue(0)
        self.route_mode_label.setText("")
        self._refresh_stats()
        self.map_hint.setText(self._pin_hint_text())

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
        if self._pin_target == PinTarget.ORIGIN:
            category_combo = self.origin_category_combo
            location_combo = self.origin_location_combo
            label = "مبدا"
        else:
            category_combo = self.destination_category_combo
            location_combo = self.destination_location_combo
            label = "مقصد"

        location_id = self._location_id_from_combos(category_combo, location_combo)
        if not location_id:
            show_error(self, f"ابتدا {label} را از دسته‌بندی و نقطه انتخاب کنید.")
            return

        latitude, longitude = clamp_to_gilan(latitude, longitude)
        try:
            self.db.update_location_coordinates(location_id, latitude, longitude)
        except DatabaseError as exc:
            show_error(self, str(exc))
            return

        show_success(self, f"موقعیت {label} «{location_combo.currentText()}» روی نقشه ثبت شد.")
        self._update_map_markers()
        self._refresh_stats()

        origin_id = self._location_id_from_combos(self.origin_category_combo, self.origin_location_combo)
        destination_id = self._location_id_from_combos(
            self.destination_category_combo,
            self.destination_location_combo,
        )
        if origin_id and destination_id and origin_id != destination_id:
            origin = self.db.get_location(origin_id)
            destination = self.db.get_location(destination_id)
            if (
                origin
                and destination
                and origin["latitude"] is not None
                and origin["longitude"] is not None
                and destination["latitude"] is not None
                and destination["longitude"] is not None
            ):
                self.calculate_route()

        if self._pin_target == PinTarget.ORIGIN:
            self._set_pin_target(PinTarget.DESTINATION)

    def calculate_route(self) -> None:
        if self._calculating:
            return

        origin_id = self._location_id_from_combos(self.origin_category_combo, self.origin_location_combo)
        destination_id = self._location_id_from_combos(
            self.destination_category_combo,
            self.destination_location_combo,
        )
        if not origin_id or not destination_id:
            show_error(self, "مبدا و مقصد را از منوی مدیریت نقاط انتخاب کنید.")
            return
        if origin_id == destination_id:
            show_error(self, "مبدا و مقصد نمی‌توانند یکسان باشند.")
            return

        origin = self.db.get_location(origin_id)
        destination = self.db.get_location(destination_id)
        if not origin or not destination:
            show_error(self, "نقطه انتخاب‌شده یافت نشد.")
            return
        if origin["latitude"] is None or origin["longitude"] is None:
            show_error(self, f"موقعیت مبدا «{origin['title']}» هنوز روی نقشه ثبت نشده است.")
            return
        if destination["latitude"] is None or destination["longitude"] is None:
            show_error(self, f"موقعیت مقصد «{destination['title']}» هنوز روی نقشه ثبت نشده است.")
            return

        self._calculating = True
        try:
            cached = self.db.get_cached_route(origin_id, destination_id)
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
                        origin_id,
                        destination_id,
                        distance_km,
                        json.dumps(points, ensure_ascii=False),
                    )
                except DatabaseError as exc:
                    show_error(self, str(exc))
                    return

            self.map_widget.draw_route([(float(point[0]), float(point[1])) for point in points])
            self.distance_input.setValue(round(distance_km, 1))
            self._update_map_markers()
            mode_text = {
                "road": "مسافت بر اساس مسیر جاده‌ای (آنلاین)",
                "estimated": "مسافت تخمینی (آفلاین)",
                "cached": "مسافت از مسیر ذخیره‌شده",
            }
            self.route_mode_label.setText(mode_text.get(mode, ""))
            self._refresh_stats()
        finally:
            self._calculating = False
