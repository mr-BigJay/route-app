from __future__ import annotations

import re
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from database.db import DatabaseError, DatabaseManager
from ui.utils import Page, confirm, show_error, show_success


PERSIAN_TEXT_RE = re.compile(r"^[\u0600-\u06FF\s‌]+$")
DATE_RE = re.compile(r"^\d{4}/\d{2}/\d{2}$")


class DriversPage(Page):
    OPTION_VIEW = 0
    FORM_VIEW = 1
    LIST_VIEW = 2

    def __init__(self, db: DatabaseManager) -> None:
        super().__init__("مدیریت رانندگان", "ثبت راننده جدید و مدیریت لیست رانندگان")
        self.db = db
        self.drivers_cache: list[dict] = []
        self.editing_driver_id: int | None = None
        self._formatting_birth_date = False
        self._formatting_distance_rate = False

        self.stack = QStackedWidget()
        self.stack.addWidget(self._build_options_view())
        self.stack.addWidget(self._build_form_view())
        self.stack.addWidget(self._build_list_view())
        self.root_layout.addWidget(self.stack, stretch=1)

    def _build_options_view(self) -> QFrame:
        card = self.card()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(26, 24, 26, 24)
        layout.setSpacing(18)

        title = QLabel("لطفاً یکی از گزینه‌های زیر را انتخاب کنید")
        title.setObjectName("sectionTitle")
        layout.addWidget(title, alignment=Qt.AlignmentFlag.AlignRight)

        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(18)
        new_driver = self._option_button(
            "ثبت راننده جدید",
            "ورود اطلاعات فردی و خودرو برای راننده جدید",
        )
        drivers_list = self._option_button(
            "لیست رانندگان",
            "مشاهده جدول رانندگان و انجام عملیات مدیریتی",
        )
        new_driver.clicked.connect(self.open_new_driver_form)
        drivers_list.clicked.connect(self.open_drivers_list)
        buttons_layout.addWidget(new_driver)
        buttons_layout.addWidget(drivers_list)
        layout.addLayout(buttons_layout)
        layout.addStretch(1)
        return card

    def _option_button(self, title: str, subtitle: str) -> QPushButton:
        button = QPushButton(f"{title}\n{subtitle}")
        button.setObjectName("optionButton")
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setMinimumHeight(130)
        return button

    def _build_form_view(self) -> QFrame:
        card = self.card()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(14)

        self.form_title = QLabel("ثبت راننده جدید")
        self.form_title.setObjectName("sectionTitle")

        personal_group = QGroupBox("اطلاعات فردی")
        personal_form = QFormLayout(personal_group)
        personal_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        self.first_name_input = QLineEdit()
        self.first_name_input.setPlaceholderText("فقط حروف فارسی")
        self.last_name_input = QLineEdit()
        self.last_name_input.setPlaceholderText("فقط حروف فارسی")
        self.mobile_input = QLineEdit()
        self.mobile_input.setPlaceholderText("مثال: 0912345678")
        self.mobile_input.setMaxLength(10)
        self.national_id_input = QLineEdit()
        self.national_id_input.setPlaceholderText("۱۰ رقم")
        self.national_id_input.setMaxLength(10)
        self.birth_date_input = QLineEdit()
        self.birth_date_input.setPlaceholderText("yyyy/mm/dd")
        self.birth_date_input.setMaxLength(10)
        self.birth_date_input.textEdited.connect(self._format_birth_date)

        personal_form.addRow("نام *", self.first_name_input)
        personal_form.addRow("نام خانوادگی *", self.last_name_input)
        personal_form.addRow("شماره موبایل راننده *", self.mobile_input)
        personal_form.addRow("شماره ملی راننده *", self.national_id_input)
        personal_form.addRow("تاریخ تولد *", self.birth_date_input)

        vehicle_group = QGroupBox("اطلاعات خودرو")
        vehicle_form = QFormLayout(vehicle_group)
        vehicle_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        self.car_model_input = QLineEdit()
        self.car_model_input.setPlaceholderText("مثال: سمند")
        self.car_year_input = QLineEdit()
        self.car_year_input.setPlaceholderText("۴ رقم")
        self.car_year_input.setMaxLength(4)
        self.car_color_input = QLineEdit()
        self.car_color_input.setPlaceholderText("مثال: سفید")
        self.distance_rate_input = QLineEdit()
        self.distance_rate_input.setPlaceholderText("مثال: 230,000")
        self.distance_rate_input.textEdited.connect(self._format_distance_rate)

        vehicle_form.addRow("مدل ماشین *", self.car_model_input)
        vehicle_form.addRow("سال تولید ماشین *", self.car_year_input)
        vehicle_form.addRow("رنگ ماشین *", self.car_color_input)
        vehicle_form.addRow("نرخ محاسبه به ریال *", self.distance_rate_input)

        buttons = QHBoxLayout()
        self.save_button = self.action_button("ثبت")
        back_button = self.action_button("بازگشت", "ghost")
        self.save_button.clicked.connect(self.save_driver)
        back_button.clicked.connect(self.back_to_options)
        buttons.addWidget(self.save_button)
        buttons.addWidget(back_button)

        layout.addWidget(self.form_title)
        layout.addWidget(personal_group)
        layout.addWidget(vehicle_group)
        layout.addLayout(buttons)
        layout.addStretch(1)
        return card

    def _build_list_view(self) -> QFrame:
        card = self.card()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)

        header = QHBoxLayout()
        title = QLabel("لیست رانندگان")
        title.setObjectName("sectionTitle")
        back_button = self.action_button("بازگشت", "ghost")
        back_button.clicked.connect(self.back_to_options)
        header.addWidget(title)
        header.addStretch(1)
        header.addWidget(back_button)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)
        edit_button = self.action_button("ویرایش", "secondary")
        delete_button = self.action_button("حذف", "danger")
        active_button = self.action_button("فعال", "secondary")
        inactive_button = self.action_button("غیرفعال", "danger")
        report_button = self.action_button("گزارش از لیست", "secondary")
        edit_button.clicked.connect(self.edit_selected_driver)
        delete_button.clicked.connect(self.delete_selected_drivers)
        active_button.clicked.connect(self.activate_selected_drivers)
        inactive_button.clicked.connect(self.deactivate_selected_drivers)
        report_button.clicked.connect(self.report_from_list)
        for button in [edit_button, delete_button, active_button, inactive_button, report_button]:
            toolbar.addWidget(button)
        toolbar.addStretch(1)

        self.table = QTableWidget(0, 11)
        self.table.setHorizontalHeaderLabels(
            [
                "انتخاب",
                "نام",
                "نام خانوادگی",
                "شماره موبایل",
                "شماره ملی",
                "تاریخ تولد",
                "مدل ماشین",
                "سال تولید ماشین",
                "رنگ ماشین",
                "نرخ محاسبه",
                "وضعیت",
            ]
        )
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)

        layout.addLayout(header)
        layout.addLayout(toolbar)
        layout.addWidget(self.table)
        return card

    def refresh(self) -> None:
        if hasattr(self, "table"):
            self.refresh_table()

    def open_new_driver_form(self) -> None:
        self.editing_driver_id = None
        self.form_title.setText("ثبت راننده جدید")
        self.save_button.setText("ثبت")
        self.clear_form()
        self.stack.setCurrentIndex(self.FORM_VIEW)

    def open_drivers_list(self) -> None:
        self.refresh_table()
        self.stack.setCurrentIndex(self.LIST_VIEW)

    def back_to_options(self) -> None:
        self.editing_driver_id = None
        self.clear_form()
        self.stack.setCurrentIndex(self.OPTION_VIEW)

    def refresh_table(self) -> None:
        self.drivers_cache = self.db.list_drivers()
        self.table.setRowCount(len(self.drivers_cache))
        for row, driver in enumerate(self.drivers_cache):
            check_item = QTableWidgetItem()
            check_item.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
            check_item.setCheckState(Qt.CheckState.Unchecked)
            check_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 0, check_item)

            values = [
                driver["first_name"],
                driver["last_name"],
                driver["mobile"],
                driver["national_id"],
                driver["birth_date"],
                driver["car_model"],
                driver["car_year"],
                driver["car_color"],
                self._format_rial(driver["distance_rate"]),
                "فعال" if int(driver.get("is_active", 1)) else "غیرفعال",
            ]
            for col, value in enumerate(values, start=1):
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
            "distance_rate": self._plain_number(self.distance_rate_input.text()),
        }

        if any(not data[key] for key in data):
            show_error(self, "همه فیلدهای فرم ثبت راننده را کامل کنید.")
            return None
        if not self._is_persian_text(data["first_name"]):
            show_error(self, "نام فقط باید شامل حروف فارسی باشد.")
            return None
        if not self._is_persian_text(data["last_name"]):
            show_error(self, "نام خانوادگی فقط باید شامل حروف فارسی باشد.")
            return None
        if not re.fullmatch(r"09\d{8}", data["mobile"]):
            show_error(self, "شماره موبایل باید با 09 شروع شود و 10 رقم باشد.")
            return None
        if not re.fullmatch(r"\d{10}", data["national_id"]):
            show_error(self, "شماره ملی باید دقیقاً 10 رقم باشد.")
            return None
        if not self._is_valid_date(data["birth_date"]):
            show_error(self, "تاریخ تولد باید با فرمت yyyy/mm/dd وارد شود.")
            return None
        if not re.fullmatch(r"\d{4}", data["car_year"]):
            show_error(self, "سال تولید ماشین باید دقیقاً 4 رقم باشد.")
            return None
        if data["distance_rate"] <= 0:
            show_error(self, "نرخ محاسبه به ریال را وارد کنید.")
            return None

        if self.editing_driver_id is not None:
            current = self._driver_by_id(self.editing_driver_id)
            if current:
                data["is_active"] = int(current.get("is_active", 1))
                data["inactive_reason"] = current.get("inactive_reason", "")
        return data

    def save_driver(self) -> None:
        data = self.collect_form_data()
        if data is None:
            return
        full_name = f"{data['first_name']} {data['last_name']}"
        action_text = "ویرایش" if self.editing_driver_id is not None else "ثبت"
        if not confirm(self, f"آیا {action_text} راننده «{full_name}» تایید می‌شود؟"):
            return
        try:
            if self.editing_driver_id is None:
                self.db.add_driver(data)
                show_success(self, "راننده با موفقیت ثبت شد.")
            else:
                self.db.update_driver(self.editing_driver_id, data)
                show_success(self, "اطلاعات راننده ویرایش شد.")
            self.clear_form()
            self.open_drivers_list()
        except DatabaseError as exc:
            show_error(self, f"ذخیره راننده انجام نشد: {exc}")

    def edit_selected_driver(self) -> None:
        selected = self.selected_drivers()
        if len(selected) != 1:
            show_error(self, "برای ویرایش، دقیقاً یک راننده را انتخاب کنید.")
            return
        driver = selected[0]
        self.editing_driver_id = int(driver["id"])
        self.form_title.setText("ویرایش راننده")
        self.save_button.setText("ذخیره تغییرات")
        self.first_name_input.setText(driver["first_name"])
        self.last_name_input.setText(driver["last_name"])
        self.mobile_input.setText(driver["mobile"])
        self.national_id_input.setText(driver["national_id"])
        self.birth_date_input.setText(driver["birth_date"])
        self.car_model_input.setText(driver["car_model"])
        self.car_year_input.setText(driver["car_year"])
        self.car_color_input.setText(driver["car_color"])
        self.distance_rate_input.setText(self._format_number(driver["distance_rate"]))
        self.stack.setCurrentIndex(self.FORM_VIEW)

    def delete_selected_drivers(self) -> None:
        selected = self.selected_drivers()
        if not selected:
            show_error(self, "ابتدا راننده‌های مورد نظر را انتخاب کنید.")
            return
        if not confirm(self, f"آیا حذف {len(selected)} راننده انتخاب‌شده تایید می‌شود؟"):
            return
        try:
            for driver in selected:
                self.db.delete_driver(int(driver["id"]))
            show_success(self, "راننده‌های انتخاب‌شده حذف شدند.")
            self.refresh_table()
        except DatabaseError as exc:
            show_error(self, f"حذف راننده انجام نشد: {exc}")

    def activate_selected_drivers(self) -> None:
        selected = self.selected_drivers()
        if not selected:
            show_error(self, "ابتدا راننده‌های مورد نظر را انتخاب کنید.")
            return
        try:
            for driver in selected:
                self.db.set_driver_active(int(driver["id"]), True)
            show_success(self, "راننده‌های انتخاب‌شده فعال شدند.")
            self.refresh_table()
        except DatabaseError as exc:
            show_error(self, f"فعال‌سازی راننده انجام نشد: {exc}")

    def deactivate_selected_drivers(self) -> None:
        selected = self.selected_drivers()
        if not selected:
            show_error(self, "ابتدا راننده‌های مورد نظر را انتخاب کنید.")
            return

        reason_box = QMessageBox(self)
        reason_box.setWindowTitle("علت غیرفعال‌سازی")
        reason_box.setText("علت غیرفعال‌سازی راننده چیست؟")
        settlement = reason_box.addButton("تسویه حساب کرده", QMessageBox.ButtonRole.AcceptRole)
        retired = reason_box.addButton("بازنشست شده", QMessageBox.ButtonRole.AcceptRole)
        reason_box.addButton("انصراف", QMessageBox.ButtonRole.RejectRole)
        reason_box.exec()
        clicked = reason_box.clickedButton()
        if clicked not in (settlement, retired):
            return
        reason = clicked.text()

        try:
            for driver in selected:
                self.db.set_driver_active(int(driver["id"]), False, reason)
            show_success(self, "راننده‌های انتخاب‌شده غیرفعال شدند.")
            self.refresh_table()
        except DatabaseError as exc:
            show_error(self, f"غیرفعال‌سازی راننده انجام نشد: {exc}")

    def report_from_list(self) -> None:
        report_box = QMessageBox(self)
        report_box.setWindowTitle("گزارش از لیست")
        report_box.setText("نوع گزارش را انتخاب کنید.")
        all_button = report_box.addButton("انتخاب همه", QMessageBox.ButtonRole.AcceptRole)
        selected_button = report_box.addButton("انتخاب راننده", QMessageBox.ButtonRole.AcceptRole)
        report_box.addButton("انصراف", QMessageBox.ButtonRole.RejectRole)
        report_box.exec()
        clicked = report_box.clickedButton()
        if clicked == all_button:
            rows = self.drivers_cache
        elif clicked == selected_button:
            rows = self.selected_drivers()
            if not rows:
                show_error(self, "برای گزارش انتخاب راننده، ابتدا چک‌باکس کنار راننده‌ها را بزنید.")
                return
        else:
            return
        self.export_drivers_excel(rows)

    def export_drivers_excel(self, drivers: list[dict]) -> None:
        if not drivers:
            show_error(self, "داده‌ای برای گزارش وجود ندارد.")
            return
        try:
            from openpyxl import Workbook
            from openpyxl.styles import Alignment, Font, PatternFill
        except ImportError:
            show_error(self, "کتابخانه openpyxl نصب نیست.")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "ذخیره گزارش رانندگان",
            str(Path.home() / "route-drivers-report.xlsx"),
            "Excel Files (*.xlsx)",
        )
        if not file_path:
            return

        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "Drivers"
        sheet.sheet_view.rightToLeft = True
        headers = [
            "نام",
            "نام خانوادگی",
            "شماره موبایل",
            "شماره ملی",
            "تاریخ تولد",
            "مدل ماشین",
            "سال تولید ماشین",
            "رنگ ماشین",
            "نرخ محاسبه",
            "وضعیت",
        ]
        sheet.append(headers)
        for driver in drivers:
            sheet.append(
                [
                    driver["first_name"],
                    driver["last_name"],
                    driver["mobile"],
                    driver["national_id"],
                    driver["birth_date"],
                    driver["car_model"],
                    driver["car_year"],
                    driver["car_color"],
                    self._format_rial(driver["distance_rate"]),
                    "فعال" if int(driver.get("is_active", 1)) else "غیرفعال",
                ]
            )

        header_fill = PatternFill("solid", fgColor="2563EB")
        header_font = Font(color="FFFFFF", bold=True)
        for cell in sheet[1]:
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal="center")
        for row in sheet.iter_rows(min_row=2):
            for cell in row:
                cell.alignment = Alignment(horizontal="center", vertical="center")
        for column in sheet.columns:
            max_length = max(len(str(cell.value or "")) for cell in column)
            sheet.column_dimensions[column[0].column_letter].width = min(max_length + 4, 45)
        workbook.save(file_path)
        show_success(self, "گزارش Excel رانندگان با موفقیت ذخیره شد.")

    def selected_drivers(self) -> list[dict]:
        selected: list[dict] = []
        for row, driver in enumerate(self.drivers_cache):
            item = self.table.item(row, 0)
            if item and item.checkState() == Qt.CheckState.Checked:
                selected.append(driver)
        return selected

    def clear_form(self) -> None:
        for line_edit in [
            self.first_name_input,
            self.last_name_input,
            self.mobile_input,
            self.national_id_input,
            self.birth_date_input,
            self.car_model_input,
            self.car_year_input,
            self.car_color_input,
            self.distance_rate_input,
        ]:
            line_edit.clear()

    def _format_birth_date(self, text: str) -> None:
        if self._formatting_birth_date:
            return
        self._formatting_birth_date = True
        digits = "".join(ch for ch in text if ch.isdigit())[:8]
        if len(digits) <= 4:
            formatted = digits
        elif len(digits) <= 6:
            formatted = f"{digits[:4]}/{digits[4:]}"
        else:
            formatted = f"{digits[:4]}/{digits[4:6]}/{digits[6:]}"
        self.birth_date_input.setText(formatted)
        self.birth_date_input.setCursorPosition(len(formatted))
        self._formatting_birth_date = False

    def _format_distance_rate(self, text: str) -> None:
        if self._formatting_distance_rate:
            return
        self._formatting_distance_rate = True
        number = self._plain_number(text)
        formatted = self._format_number(number) if number else ""
        self.distance_rate_input.setText(formatted)
        self.distance_rate_input.setCursorPosition(len(formatted))
        self._formatting_distance_rate = False

    def _driver_by_id(self, driver_id: int) -> dict | None:
        for driver in self.db.list_drivers():
            if int(driver["id"]) == driver_id:
                return driver
        return None

    @staticmethod
    def _is_persian_text(value: str) -> bool:
        return bool(value and PERSIAN_TEXT_RE.fullmatch(value)) and not any(ch.isdigit() for ch in value)

    @staticmethod
    def _is_valid_date(value: str) -> bool:
        if not DATE_RE.fullmatch(value):
            return False
        _, month, day = (int(part) for part in value.split("/"))
        return 1 <= month <= 12 and 1 <= day <= 31

    @staticmethod
    def _plain_number(value: int | float | str) -> int:
        if isinstance(value, (int, float)):
            return int(value)
        digits = "".join(ch for ch in str(value) if ch.isdigit())
        return int(digits) if digits else 0

    @staticmethod
    def _format_number(value: int | float | str) -> str:
        number = DriversPage._plain_number(str(value))
        return f"{number:,}" if number else ""

    @staticmethod
    def _format_rial(value: int | float | str) -> str:
        number = DriversPage._plain_number(str(value))
        return f"{number:,} ریال" if number else "0 ریال"
