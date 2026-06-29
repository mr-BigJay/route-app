from __future__ import annotations

from enum import Enum

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDoubleSpinBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from database.db import DatabaseError, DatabaseManager
from ui.form_widgets import NoWheelComboBox, configure_combo_field, configure_spin_field
from ui.geo_utils import clamp_to_rudsar
from ui.route_batch_worker import RouteBatchWorker, RouteComputeWorker
from ui.route_map_widget import RouteMapWidget
from ui.utils import Page, clear_layout, make_stat_card, show_error, show_success, to_persian_digits

MODE_LABELS = {
    "road": "مسافت جاده‌ای (آنلاین) — در کش ذخیره شد",
    "estimated": "مسافت تخمینی (آفلاین) — در کش ذخیره شد",
    "cached": "مسافت از کش محلی",
}


class PinTarget(Enum):
    ORIGIN = "origin"
    DESTINATION = "destination"


class RoutesPage(Page):
    def __init__(self, db: DatabaseManager) -> None:
        super().__init__("مدیریت مسیر", "ثبت موقعیت نقاط، محاسبه و ذخیره مسافت در کش محلی")
        self.setObjectName("routesPage")
        self.db = db
        self._pin_target = PinTarget.ORIGIN
        self._map_ready = False
        self._single_worker: RouteComputeWorker | None = None
        self._batch_worker: RouteBatchWorker | None = None

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
        self.root_layout.addWidget(self._batch_card())
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
        header = QHBoxLayout()
        title = QLabel("نقشه شهرستان رودسر")
        title.setObjectName("sectionTitle")
        self.map_mode_label = QLabel("")
        self.map_mode_label.setObjectName("routeMapHint")
        header.addWidget(title)
        header.addStretch(1)
        header.addWidget(self.map_mode_label)
        self.map_hint = QLabel(self._pin_hint_text())
        self.map_hint.setObjectName("routeMapHint")
        self.map_hint.setWordWrap(True)
        self.map_widget = RouteMapWidget()
        self.map_widget.setMinimumHeight(420)
        self.map_widget.map_clicked.connect(self._on_map_clicked)
        self.map_widget.map_ready.connect(self._on_map_ready)
        layout.addLayout(header)
        layout.addWidget(self.map_hint)
        layout.addWidget(self.map_widget, stretch=1)
        return card

    def _panel_card(self) -> QWidget:
        card = self.card()
        card.setObjectName("routePanelCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)

        origin_title = QLabel("مبدا (A)")
        origin_title.setObjectName("routeSectionTitle")
        self.origin_category_combo = self._category_combo()
        self.origin_location_combo = self._location_combo()
        self.origin_category_combo.currentIndexChanged.connect(
            lambda: self._populate_location_combo(self.origin_category_combo, self.origin_location_combo)
        )
        self.origin_location_combo.currentIndexChanged.connect(self._on_endpoint_changed)
        self.origin_category_combo.currentIndexChanged.connect(self._on_endpoint_changed)

        destination_title = QLabel("مقصد (B)")
        destination_title.setObjectName("routeSectionTitle")
        self.destination_category_combo = self._category_combo()
        self.destination_location_combo = self._location_combo()
        self.destination_category_combo.currentIndexChanged.connect(
            lambda: self._populate_location_combo(self.destination_category_combo, self.destination_location_combo)
        )
        self.destination_location_combo.currentIndexChanged.connect(self._on_endpoint_changed)
        self.destination_category_combo.currentIndexChanged.connect(self._on_endpoint_changed)

        pin_buttons = QHBoxLayout()
        pin_buttons.setSpacing(6)
        self.origin_pin_button = self._pin_button("پین مبدا", PinTarget.ORIGIN)
        self.destination_pin_button = self._pin_button("پین مقصد", PinTarget.DESTINATION)
        pin_buttons.addWidget(self.origin_pin_button)
        pin_buttons.addWidget(self.destination_pin_button)

        route_title = QLabel("مسافت")
        route_title.setObjectName("routeSectionTitle")
        self.distance_input = QDoubleSpinBox()
        self.distance_input.setObjectName("routeCompactSpin")
        configure_spin_field(self.distance_input)
        self.distance_input.setRange(0, 1_000_000)
        self.distance_input.setDecimals(1)
        self.distance_input.setSuffix(" km")
        self.distance_input.setReadOnly(True)
        self.distance_input.setButtonSymbols(QDoubleSpinBox.ButtonSymbols.NoButtons)
        self.distance_input.setFixedHeight(30)
        self.route_mode_label = QLabel("")
        self.route_mode_label.setObjectName("routeModeHint")
        self.route_mode_label.setWordWrap(True)

        action_row = QHBoxLayout()
        action_row.setSpacing(6)
        self.calc_button = self._compact_button("محاسبه")
        self.calc_button.clicked.connect(lambda: self.calculate_route(force=True))
        self.cache_button = self._compact_button("از کش", "secondary")
        self.cache_button.clicked.connect(lambda: self.calculate_route(force=False))
        action_row.addWidget(self.calc_button)
        action_row.addWidget(self.cache_button)

        layout.addWidget(origin_title)
        layout.addLayout(self._compact_endpoint_row("دسته", self.origin_category_combo, "نقطه", self.origin_location_combo))
        layout.addWidget(destination_title)
        layout.addLayout(self._compact_endpoint_row("دسته", self.destination_category_combo, "نقطه", self.destination_location_combo))
        layout.addLayout(pin_buttons)
        layout.addWidget(route_title)
        layout.addWidget(self.distance_input)
        layout.addLayout(action_row)
        layout.addWidget(self.route_mode_label)
        self._update_pin_buttons()
        return card

    def _batch_card(self) -> QWidget:
        card = self.card()
        card.setObjectName("routeBatchCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(6)
        batch_title = QLabel("محاسبه دسته‌ای مسیرها (کش)")
        batch_title.setObjectName("routeSectionTitle")
        self.batch_hint = QLabel("مسیرهای ذخیره‌نشده بین نقاط دارای موقعیت، در پس‌زمینه محاسبه می‌شوند.")
        self.batch_hint.setObjectName("routeMapHint")
        self.batch_hint.setWordWrap(True)
        self.batch_progress = QProgressBar()
        self.batch_progress.setRange(0, 100)
        self.batch_progress.setValue(0)
        self.batch_progress.setFixedHeight(10)
        self.batch_status_label = QLabel("آماده")
        self.batch_status_label.setObjectName("routeModeHint")
        batch_buttons = QHBoxLayout()
        batch_buttons.setSpacing(8)
        self.batch_start_button = self._compact_button("محاسبه مسیرهای جدید")
        self.batch_start_button.clicked.connect(self._start_batch_compute)
        self.batch_stop_button = self._compact_button("توقف", "danger")
        self.batch_stop_button.clicked.connect(self._stop_batch_compute)
        self.batch_stop_button.setEnabled(False)
        batch_buttons.addWidget(self.batch_start_button)
        batch_buttons.addWidget(self.batch_stop_button)
        batch_buttons.addStretch(1)
        layout.addWidget(batch_title)
        layout.addWidget(self.batch_hint)
        layout.addWidget(self.batch_progress)
        layout.addWidget(self.batch_status_label)
        layout.addLayout(batch_buttons)
        return card

    def _compact_endpoint_row(
        self,
        cat_label: str,
        cat_combo: NoWheelComboBox,
        loc_label: str,
        loc_combo: NoWheelComboBox,
    ) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(6)
        row.addLayout(self._compact_field(cat_label, cat_combo), stretch=1)
        row.addLayout(self._compact_field(loc_label, loc_combo), stretch=1)
        return row

    def _compact_field(self, label: str, widget: QWidget) -> QVBoxLayout:
        box = QVBoxLayout()
        box.setSpacing(2)
        box.setContentsMargins(0, 0, 0, 0)
        label_widget = QLabel(label)
        label_widget.setObjectName("routeFieldLabel")
        box.addWidget(label_widget)
        box.addWidget(widget)
        return box

    def _compact_button(self, title: str, role: str = "primary") -> QPushButton:
        button = QPushButton(title)
        button.setObjectName("routeCompactButton")
        button.setProperty("role", role)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setFixedHeight(30)
        return button

    def _category_combo(self) -> NoWheelComboBox:
        combo = NoWheelComboBox()
        combo.setObjectName("routeCompactCombo")
        configure_combo_field(combo)
        combo.setFixedHeight(30)
        combo.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        return combo

    def _location_combo(self) -> NoWheelComboBox:
        combo = NoWheelComboBox()
        combo.setObjectName("routeCompactCombo")
        configure_combo_field(combo)
        combo.setFixedHeight(30)
        combo.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        return combo

    def _pin_button(self, title: str, target: PinTarget) -> QPushButton:
        button = self._compact_button(title, "secondary")
        button.setProperty("pinTarget", target.value)
        button.clicked.connect(lambda: self._set_pin_target(target))
        return button

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
            return f"مبدا (A) فعال — «{point}» را انتخاب کنید و روی نقشه کلیک کنید."
        point = self._selected_location_title(self.destination_category_combo, self.destination_location_combo)
        return f"مقصد (B) فعال — «{point}» را انتخاب کنید و روی نقشه کلیک کنید."

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
        current_id = location_combo.currentData()
        location_combo.blockSignals(True)
        location_combo.clear()
        for location in self.db.list_locations():
            if category_id is None or location["category_id"] == category_id:
                location_combo.addItem(location["title"], location["id"])
        if current_id is not None:
            index = location_combo.findData(current_id)
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
        for location_id, role, prefix in (
            (origin_id, "origin", "A"),
            (destination_id, "destination", "B"),
        ):
            if not location_id:
                continue
            location = self.db.get_location(int(location_id))
            if not location or location["latitude"] is None or location["longitude"] is None:
                continue
            markers.append(
                {
                    "id": int(location_id),
                    "title": location["title"],
                    "label": f"{prefix} — {location['title']}",
                    "lat": float(location["latitude"]),
                    "lng": float(location["longitude"]),
                    "role": role,
                }
            )
        return markers

    def _update_map_mode_label(self) -> None:
        if self.map_widget.uses_web_engine():
            self.map_mode_label.setText("نقشه آنلاین")
        else:
            self.map_mode_label.setText("نقشه آفلاین")

    def _on_endpoint_changed(self) -> None:
        self.map_hint.setText(self._pin_hint_text())
        self._update_map_markers()
        self._try_auto_calculate()

    def _on_map_ready(self) -> None:
        self._map_ready = True
        self._update_map_mode_label()
        self._update_map_markers()

    def _update_map_markers(self) -> None:
        if not self._map_ready:
            return
        self.map_widget.set_markers(self._marker_payload())

    def refresh(self) -> None:
        self._populate_category_combos()
        self._populate_location_combo(self.origin_category_combo, self.origin_location_combo)
        self._populate_location_combo(self.destination_category_combo, self.destination_location_combo)
        self._update_map_mode_label()
        self._update_map_markers()
        self._refresh_stats()
        self.map_hint.setText(self._pin_hint_text())
        self._try_auto_calculate()

    def _refresh_stats(self) -> None:
        stats = self.db.route_cache_stats()
        clear_layout(self.stats_layout)
        cards = [
            ("نقاط روی نقشه", stats["mapped_locations"], "#2563EB", "#EFF6FF"),
            ("مسیرهای ذخیره‌شده", stats["cached_routes"], "#16A34A", "#F0FDF4"),
            ("مسیرهای ممکن", stats["possible_routes"], "#7C3AED", "#F5F3FF"),
            ("بدون کش", stats["missing_routes"], "#EA580C", "#FFF7ED"),
        ]
        for index, (title, value, accent, tint) in enumerate(cards):
            self.stats_layout.addWidget(
                make_stat_card(title, str(value), accent, tint),
                0,
                index,
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

        latitude, longitude = clamp_to_rudsar(latitude, longitude)
        try:
            self.db.update_location_coordinates(location_id, latitude, longitude)
        except DatabaseError as exc:
            show_error(self, str(exc))
            return

        show_success(self, f"موقعیت {label} «{location_combo.currentText()}» ثبت شد. مسیرهای مرتبط از کش حذف شدند.")
        self._update_map_markers()
        self._refresh_stats()

        if self._pin_target == PinTarget.ORIGIN:
            self._set_pin_target(PinTarget.DESTINATION)
        self._try_auto_calculate(force=True)

    def _try_auto_calculate(self, *, force: bool = False) -> None:
        origin_id = self._location_id_from_combos(self.origin_category_combo, self.origin_location_combo)
        destination_id = self._location_id_from_combos(
            self.destination_category_combo,
            self.destination_location_combo,
        )
        if not origin_id or not destination_id or origin_id == destination_id:
            self.map_widget.clear_route()
            self.distance_input.setValue(0)
            self.route_mode_label.setText("")
            return
        origin = self.db.get_location(origin_id)
        destination = self.db.get_location(destination_id)
        if not origin or not destination:
            return
        if origin["latitude"] is None or origin["longitude"] is None:
            self.route_mode_label.setText("موقعیت مبدا روی نقشه ثبت نشده است.")
            self.map_widget.clear_route()
            self.distance_input.setValue(0)
            return
        if destination["latitude"] is None or destination["longitude"] is None:
            self.route_mode_label.setText("موقعیت مقصد روی نقشه ثبت نشده است.")
            self.map_widget.clear_route()
            self.distance_input.setValue(0)
            return
        self.calculate_route(force=force)

    def calculate_route(self, *, force: bool = False) -> None:
        origin_id = self._location_id_from_combos(self.origin_category_combo, self.origin_location_combo)
        destination_id = self._location_id_from_combos(
            self.destination_category_combo,
            self.destination_location_combo,
        )
        if not origin_id or not destination_id:
            show_error(self, "مبدا و مقصد را انتخاب کنید.")
            return
        if origin_id == destination_id:
            show_error(self, "مبدا و مقصد نمی‌توانند یکسان باشند.")
            return

        self._stop_single_worker()
        self.calc_button.setEnabled(False)
        self.cache_button.setEnabled(False)
        self.route_mode_label.setText("در حال محاسبه مسافت...")

        worker = RouteComputeWorker(self.db, origin_id, destination_id, force=force, parent=self)
        worker.succeeded.connect(self._on_route_computed)
        worker.failed.connect(self._on_route_failed)
        worker.finished.connect(self._on_single_worker_finished)
        self._single_worker = worker
        worker.start()

    def _stop_single_worker(self) -> None:
        if self._single_worker and self._single_worker.isRunning():
            self._single_worker.wait(2000)
        self._single_worker = None

    def _on_single_worker_finished(self) -> None:
        self.calc_button.setEnabled(True)
        self.cache_button.setEnabled(True)

    def _on_route_computed(self, result: dict) -> None:
        points = result.get("points") or []
        self.map_widget.draw_route([(float(p[0]), float(p[1])) for p in points])
        self.distance_input.setValue(round(float(result["distance_km"]), 1))
        self._update_map_markers()
        mode = str(result.get("mode") or "cached")
        self.route_mode_label.setText(MODE_LABELS.get(mode, mode))
        self._refresh_stats()

    def _on_route_failed(self, message: str) -> None:
        self.route_mode_label.setText("")
        show_error(self, message)

    def _start_batch_compute(self) -> None:
        if self._batch_worker and self._batch_worker.isRunning():
            return
        pairs = self.db.list_uncached_route_pairs()
        if not pairs:
            show_success(self, "همه مسیرهای ممکن بین نقاط دارای موقعیت، قبلاً ذخیره شده‌اند.")
            self._refresh_stats()
            return

        self.batch_progress.setRange(0, len(pairs))
        self.batch_progress.setValue(0)
        self.batch_start_button.setEnabled(False)
        self.batch_stop_button.setEnabled(True)
        self.batch_status_label.setText(f"شروع محاسبه {to_persian_digits(len(pairs))} مسیر...")

        worker = RouteBatchWorker(self.db, pairs, parent=self)
        worker.progress.connect(self._on_batch_progress)
        worker.finished_ok.connect(self._on_batch_finished)
        worker.failed.connect(lambda msg: show_error(self, msg))
        worker.finished.connect(self._on_batch_worker_closed)
        self._batch_worker = worker
        worker.start()

    def _stop_batch_compute(self) -> None:
        if self._batch_worker and self._batch_worker.isRunning():
            self._batch_worker.cancel()
            self.batch_status_label.setText("در حال توقف...")
            self.batch_stop_button.setEnabled(False)

    def _on_batch_progress(self, done: int, total: int, label: str) -> None:
        self.batch_progress.setMaximum(total)
        self.batch_progress.setValue(done)
        self.batch_status_label.setText(
            f"{to_persian_digits(done)} از {to_persian_digits(total)} — {label}"
        )

    def _on_batch_finished(self, success_count: int, failed_count: int) -> None:
        self._refresh_stats()
        self.batch_status_label.setText(
            f"پایان — موفق: {to_persian_digits(success_count)} | ناموفق: {to_persian_digits(failed_count)}"
        )
        if success_count:
            self._try_auto_calculate()

    def _on_batch_worker_closed(self) -> None:
        self.batch_start_button.setEnabled(True)
        self.batch_stop_button.setEnabled(False)
        self._batch_worker = None
