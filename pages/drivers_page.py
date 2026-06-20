from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from database.db import DatabaseError, DatabaseManager
from ui.utils import Page, confirm, show_error, show_success


class DriversPage(Page):
    def __init__(self, db: DatabaseManager) -> None:
        super().__init__("مدیریت رانندگان", "لیست رانندگان ثبت‌شده و ثبت راننده جدید")
        self.db = db

        body = QHBoxLayout()
        body.setSpacing(16)
        body.addWidget(self._table_card(), stretch=3)
        body.addWidget(self._form_card(), stretch=2)
        self.root_layout.addLayout(body, stretch=1)

    def _form_card(self):
        card = self.card()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(14)
        title = QLabel("ثبت راننده جدید")
        title.setObjectName("sectionTitle")

        personal_group = QGroupBox("اطلاعات فردی")
        personal_form = QFormLayout(personal_group)
        personal_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        self.first_name_input = QLineEdit()
        self.first_name_input.setPlaceholderText("نام")
        self.last_name_input = QLineEdit()
        self.last_name_input.setPlaceholderText("نام خانوادگی")
        self.mobile_input = QLineEdit()
        self.mobile_input.setPlaceholderText("مثال: 09123456789")
        self.national_id_input = QLineEdit()
        self.national_id_input.setPlaceholderText("کد ملی")
        self.birth_date_input = QLineEdit()
        self.birth_date_input.setPlaceholderText("مثال: 1368/05/21")
        personal_form.addRow("نام *", self.first_name_input)
        personal_form.addRow("نام خانوادگی *", self.last_name_input)
        personal_form.addRow("شماره موبایل راننده *", self.mobile_input)
        personal_form.addRow("شماره ملی راننده *", self.national_id_input)
        personal_form.addRow("تاریخ تولد", self.birth_date_input)

        vehicle_group = QGroupBox("اطلاعات خودرو")
        vehicle_form = QFormLayout(vehicle_group)
        vehicle_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        self.car_model_input = QLineEdit()
        self.car_model_input.setPlaceholderText("مثال: سمند")
        self.car_year_input = QLineEdit()
        self.car_year_input.setPlaceholderText("مثال: 1398")
        self.car_color_input = QLineEdit()
        self.car_color_input.setPlaceholderText("مثال: سفید")
        self.distance_rate_input = QDoubleSpinBox()
        self.distance_rate_input.setRange(0, 1_000_000_000)
        self.distance_rate_input.setDecimals(0)
        self.distance_rate_input.setSuffix(" ریال")
        vehicle_form.addRow("مدل ماشین *", self.car_model_input)
        vehicle_form.addRow("سال تولید ماشین", self.car_year_input)
        vehicle_form.addRow("رنگ ماشین", self.car_color_input)
        vehicle_form.addRow("نرخ محاسبه مسافت مبتنی بر کیلومتر", self.distance_rate_input)

        buttons = QHBoxLayout()
        self.save_button = self.action_button("ثبت")
        self.back_button = self.action_button("بازگشت", "ghost")
        self.save_button.clicked.connect(self.add_driver)
        self.back_button.clicked.connect(self.clear_form)
        buttons.addWidget(self.save_button)
        buttons.addWidget(self.back_button)

        layout.addWidget(title)
        layout.addWidget(personal_group)
        layout.addWidget(vehicle_group)
        layout.addLayout(buttons)
        layout.addStretch(1)
        return card

    def _table_card(self):
        card = self.card()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 16, 18, 16)
        title = QLabel("لیست رانندگان")
        title.setObjectName("sectionTitle")
        self.table = QTableWidget(0, 9)
        self.table.setHorizontalHeaderLabels(
            [
                "شناسه",
                "نام",
                "نام خانوادگی",
                "موبایل",
                "کد ملی",
                "تاریخ تولد",
                "مدل خودرو",
                "رنگ",
                "نرخ هر کیلومتر",
            ]
        )
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(title)
        layout.addWidget(self.table)
        return card

    def refresh(self) -> None:
        drivers = self.db.list_drivers()
        self.table.setRowCount(len(drivers))
        for row, driver in enumerate(drivers):
            values = [
                driver["id"],
                driver["first_name"],
                driver["last_name"],
                driver["mobile"],
                driver["national_id"],
                driver["birth_date"],
                driver["car_model"],
                driver["car_color"],
                f"{float(driver['distance_rate'] or 0):.0f}",
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(row, col, item)

    def collect_form_data(self) -> dict | None:
        data = {
            "first_name": self.first_name_input.text().strip(),
            "last_name": self.last_name_input.text().strip(),
            "mobile": self.mobile_input.text().strip(),
            "national_id": self.national_id_input.text().strip(),
            "birth_date": self.birth_date_input.text().strip(),
            "car_model": self.car_model_input.text().strip(),
            "car_year": self.car_year_input.text().strip(),
            "car_color": self.car_color_input.text().strip(),
            "distance_rate": self.distance_rate_input.value(),
        }
        required_fields = [
            data["first_name"],
            data["last_name"],
            data["mobile"],
            data["national_id"],
            data["car_model"],
        ]
        if any(not value for value in required_fields):
            show_error(self, "نام، نام خانوادگی، شماره موبایل، شماره ملی و مدل ماشین را وارد کنید.")
            return None
        if data["mobile"] and not data["mobile"].isdigit():
            show_error(self, "شماره موبایل باید فقط شامل عدد باشد.")
            return None
        if data["national_id"] and not data["national_id"].isdigit():
            show_error(self, "شماره ملی باید فقط شامل عدد باشد.")
            return None
        return data

    def add_driver(self) -> None:
        data = self.collect_form_data()
        if data is None:
            return
        full_name = f"{data['first_name']} {data['last_name']}"
        if not confirm(self, f"آیا ثبت راننده «{full_name}» تایید می‌شود؟"):
            return
        try:
            self.db.add_driver(data)
            show_success(self, "راننده با موفقیت ثبت شد.")
            self.clear_form()
            self.refresh()
        except DatabaseError as exc:
            show_error(self, f"ثبت راننده انجام نشد: {exc}")

    def clear_form(self) -> None:
        self.first_name_input.clear()
        self.last_name_input.clear()
        self.mobile_input.clear()
        self.national_id_input.clear()
        self.birth_date_input.clear()
        self.car_model_input.clear()
        self.car_year_input.clear()
        self.car_color_input.clear()
        self.distance_rate_input.setValue(0)
        self.table.clearSelection()
