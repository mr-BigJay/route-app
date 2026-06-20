from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from database.db import DatabaseError, DatabaseManager
from ui.utils import Page, confirm, current_time_text, gregorian_to_jalali, show_error, show_success


class MissionsPage(Page):
    def __init__(self, db: DatabaseManager) -> None:
        super().__init__("ماموریت‌ها", "ثبت و مدیریت ماموریت خودروهای سازمانی")
        self.db = db
        self.selected_id: int | None = None
        self.missions_cache: list[dict] = []

        self.root_layout.addWidget(self._form_card())
        self.root_layout.addWidget(self._table_card(), stretch=1)

    def _form_card(self):
        card = self.card()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)
        title = QLabel("فرم ثبت ماموریت")
        title.setObjectName("sectionTitle")

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        self.driver_combo = QComboBox()
        self.vehicle_input = QLineEdit()
        self.vehicle_input.setPlaceholderText("مثال: سمند - ۱۲۳۴۵")
        self.date_input = QLineEdit(gregorian_to_jalali())
        self.date_input.setPlaceholderText("1403/11/20")
        self.time_input = QLineEdit(current_time_text()[:5])
        self.time_input.setPlaceholderText("08:30")
        self.origin_combo = QComboBox()
        self.origin_combo.setEditable(True)
        self.destination_combo = QComboBox()
        self.destination_combo.setEditable(True)
        self.distance_input = QDoubleSpinBox()
        self.distance_input.setRange(0, 1_000_000)
        self.distance_input.setDecimals(1)
        self.distance_input.setSuffix(" km")
        self.passengers_input = QLineEdit()
        self.passengers_input.setPlaceholderText("نام سرنشینان")
        self.description_input = QPlainTextEdit()
        self.description_input.setFixedHeight(70)

        form.addRow("راننده *", self.driver_combo)
        form.addRow("خودرو *", self.vehicle_input)
        form.addRow("تاریخ *", self.date_input)
        form.addRow("ساعت *", self.time_input)
        form.addRow("مبدا *", self.origin_combo)
        form.addRow("مقصد *", self.destination_combo)
        form.addRow("مسافت *", self.distance_input)
        form.addRow("سرنشینان", self.passengers_input)
        form.addRow("توضیحات", self.description_input)

        buttons = QHBoxLayout()
        save_button = self.action_button("ثبت ماموریت")
        update_button = self.action_button("ویرایش", "secondary")
        delete_button = self.action_button("حذف", "danger")
        clear_button = self.action_button("پاک کردن", "ghost")
        save_button.clicked.connect(self.add_mission)
        update_button.clicked.connect(self.update_mission)
        delete_button.clicked.connect(self.delete_mission)
        clear_button.clicked.connect(self.clear_form)
        buttons.addWidget(save_button)
        buttons.addWidget(update_button)
        buttons.addWidget(delete_button)
        buttons.addWidget(clear_button)

        layout.addWidget(title)
        layout.addLayout(form)
        layout.addLayout(buttons)
        return card

    def _table_card(self):
        card = self.card()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)
        header = QHBoxLayout()
        title = QLabel("لیست ماموریت‌ها")
        title.setObjectName("sectionTitle")
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("جستجو در راننده، خودرو، تاریخ، مسیر و توضیحات")
        self.search_input.textChanged.connect(self.refresh)
        header.addWidget(title)
        header.addWidget(self.search_input, stretch=1)

        self.table = QTableWidget(0, 10)
        self.table.setHorizontalHeaderLabels(
            [
                "شناسه",
                "تاریخ",
                "ساعت",
                "راننده",
                "خودرو",
                "مبدا",
                "مقصد",
                "مسافت",
                "سرنشینان",
                "توضیحات",
            ]
        )
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.itemSelectionChanged.connect(self.on_selection_changed)
        layout.addLayout(header)
        layout.addWidget(self.table)
        return card

    def refresh(self) -> None:
        self._refresh_combos()
        self.missions_cache = self.db.list_missions(search=self.search_input.text())
        self.table.setRowCount(len(self.missions_cache))
        for row, mission in enumerate(self.missions_cache):
            values = [
                mission["id"],
                mission["mission_date"],
                mission["mission_time"],
                mission["driver_name"],
                mission["vehicle"],
                mission["origin"],
                mission["destination"],
                f"{float(mission['distance']):.1f}",
                mission["passengers"] or "",
                mission["description"] or "",
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(row, col, item)

    def _refresh_combos(self) -> None:
        current_driver = self.driver_combo.currentData()
        self.driver_combo.blockSignals(True)
        self.driver_combo.clear()
        for driver in self.db.list_drivers():
            self.driver_combo.addItem(driver["full_name"], driver["id"])
        driver_index = self.driver_combo.findData(current_driver)
        if driver_index >= 0:
            self.driver_combo.setCurrentIndex(driver_index)
        self.driver_combo.blockSignals(False)

        current_origin = self.origin_combo.currentText()
        current_destination = self.destination_combo.currentText()
        self.origin_combo.blockSignals(True)
        self.destination_combo.blockSignals(True)
        self.origin_combo.clear()
        self.destination_combo.clear()
        for location in self.db.list_locations():
            label = location["title"]
            self.origin_combo.addItem(label)
            self.destination_combo.addItem(label)
        self.origin_combo.setCurrentText(current_origin)
        self.destination_combo.setCurrentText(current_destination)
        self.origin_combo.blockSignals(False)
        self.destination_combo.blockSignals(False)

    def collect_form_data(self) -> dict | None:
        driver_id = self.driver_combo.currentData()
        data = {
            "driver_id": driver_id,
            "vehicle": self.vehicle_input.text().strip(),
            "mission_date": self.date_input.text().strip(),
            "mission_time": self.time_input.text().strip(),
            "origin": self.origin_combo.currentText().strip(),
            "destination": self.destination_combo.currentText().strip(),
            "distance": self.distance_input.value(),
            "passengers": self.passengers_input.text().strip(),
            "description": self.description_input.toPlainText().strip(),
        }
        required = [
            data["driver_id"],
            data["vehicle"],
            data["mission_date"],
            data["mission_time"],
            data["origin"],
            data["destination"],
        ]
        if any(value in (None, "") for value in required):
            show_error(self, "فیلدهای ضروری ماموریت را کامل کنید.")
            return None
        return data

    def add_mission(self) -> None:
        data = self.collect_form_data()
        if data is None:
            return
        try:
            self.db.add_mission(data)
            show_success(self, "ماموریت ثبت شد.")
            self.clear_form()
            self.refresh()
        except DatabaseError as exc:
            show_error(self, f"ثبت ماموریت انجام نشد: {exc}")

    def update_mission(self) -> None:
        if self.selected_id is None:
            show_error(self, "ابتدا یک ماموریت را انتخاب کنید.")
            return
        data = self.collect_form_data()
        if data is None:
            return
        try:
            self.db.update_mission(self.selected_id, data)
            show_success(self, "ماموریت ویرایش شد.")
            self.clear_form()
            self.refresh()
        except DatabaseError as exc:
            show_error(self, f"ویرایش ماموریت انجام نشد: {exc}")

    def delete_mission(self) -> None:
        if self.selected_id is None:
            show_error(self, "ابتدا یک ماموریت را انتخاب کنید.")
            return
        if not confirm(self, "آیا از حذف ماموریت انتخاب‌شده مطمئن هستید؟"):
            return
        try:
            self.db.delete_mission(self.selected_id)
            show_success(self, "ماموریت حذف شد.")
            self.clear_form()
            self.refresh()
        except DatabaseError as exc:
            show_error(self, f"حذف ماموریت انجام نشد: {exc}")

    def on_selection_changed(self) -> None:
        row = self.table.currentRow()
        if row < 0 or row >= len(self.missions_cache):
            return
        mission = self.missions_cache[row]
        self.selected_id = int(mission["id"])
        driver_index = self.driver_combo.findData(mission["driver_id"])
        if driver_index >= 0:
            self.driver_combo.setCurrentIndex(driver_index)
        self.vehicle_input.setText(mission["vehicle"])
        self.date_input.setText(mission["mission_date"])
        self.time_input.setText(mission["mission_time"])
        self.origin_combo.setCurrentText(mission["origin"])
        self.destination_combo.setCurrentText(mission["destination"])
        self.distance_input.setValue(float(mission["distance"] or 0))
        self.passengers_input.setText(mission["passengers"] or "")
        self.description_input.setPlainText(mission["description"] or "")

    def clear_form(self) -> None:
        self.selected_id = None
        if self.driver_combo.count():
            self.driver_combo.setCurrentIndex(0)
        self.vehicle_input.clear()
        self.date_input.setText(gregorian_to_jalali())
        self.time_input.setText(current_time_text()[:5])
        self.origin_combo.setCurrentIndex(0 if self.origin_combo.count() else -1)
        self.destination_combo.setCurrentIndex(0 if self.destination_combo.count() else -1)
        self.distance_input.setValue(0)
        self.passengers_input.clear()
        self.description_input.clear()
        self.table.clearSelection()
