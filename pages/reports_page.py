from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from database.db import DatabaseManager
from ui.utils import (
    PRIMARY_COLOR,
    SUCCESS_COLOR,
    Page,
    gregorian_to_jalali,
    make_stat_card,
    show_error,
    show_success,
    to_english_digits,
    to_persian_digits,
)


class ReportsPage(Page):
    def __init__(self, db: DatabaseManager) -> None:
        super().__init__("گزارشات", "گزارش‌گیری ساده و خروجی Excel")
        self.db = db
        self.report_rows: list[dict] = []
        self.total_distance = 0.0
        self.total_fee = 0.0
        self.root_layout.addWidget(self._filters_card())
        self.root_layout.addWidget(self._table_card(), stretch=1)
        self.root_layout.addWidget(self._totals_card())

    def _filters_card(self):
        card = self.card()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(14)
        title = QLabel("فیلتر گزارش")
        title.setObjectName("sectionTitle")

        self.driver_combo = QComboBox()
        self.driver_combo.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.start_date_input = QLineEdit()
        self.end_date_input = QLineEdit()
        for date_input in [self.start_date_input, self.end_date_input]:
            date_input.setPlaceholderText("yyyy/mm/dd")
            date_input.setMaxLength(10)
            date_input.setAlignment(Qt.AlignmentFlag.AlignRight)

        filters_row = QHBoxLayout()
        filters_row.setDirection(QHBoxLayout.Direction.RightToLeft)
        filters_row.setSpacing(12)
        filters_row.addWidget(self._field_box("راننده", self.driver_combo), stretch=30)
        filters_row.addWidget(self._date_range_box(), stretch=70)

        buttons = QHBoxLayout()
        buttons.setDirection(QHBoxLayout.Direction.RightToLeft)
        generate_button = self.action_button("نمایش گزارش")
        export_button = self.action_button("خروجی Excel", "secondary")
        generate_button.clicked.connect(self.generate_report)
        export_button.clicked.connect(self.export_excel)
        buttons.addWidget(generate_button)
        buttons.addWidget(export_button)

        layout.addWidget(title)
        layout.addLayout(filters_row)
        layout.addLayout(buttons)
        return card

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

    def _date_range_box(self) -> QWidget:
        box = QWidget()
        box.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        layout = QVBoxLayout(box)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        title = QLabel("تاریخ گزارش")
        title.setObjectName("fieldLabel")
        title.setAlignment(Qt.AlignmentFlag.AlignRight)
        row = QHBoxLayout()
        row.setDirection(QHBoxLayout.Direction.RightToLeft)
        row.setSpacing(10)
        separator = QLabel("تا")
        separator.setAlignment(Qt.AlignmentFlag.AlignCenter)
        row.addWidget(self.start_date_input, stretch=1)
        row.addWidget(separator)
        row.addWidget(self.end_date_input, stretch=1)
        layout.addWidget(title)
        layout.addLayout(row)
        return box

    def _table_card(self):
        card = self.card()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 16, 18, 16)
        title = QLabel("نتایج گزارش")
        title.setObjectName("sectionTitle")
        self.table = QTableWidget(0, 9)
        self.table.setHorizontalHeaderLabels(
            ["ردیف", "تاریخ", "ساعت", "راننده", "خودرو", "مبدا", "مقصد نهایی", "مسافت", "حق‌الزحمه"]
        )
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(title)
        layout.addWidget(self.table)
        return card

    def _totals_card(self):
        card = self.card()
        layout = QHBoxLayout(card)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)
        self.distance_total_card = make_stat_card("مسافت کل", "۰.۰", PRIMARY_COLOR)
        self.fee_total_card = make_stat_card("حق‌الزحمه راننده", "۰ ریال", SUCCESS_COLOR)
        layout.addWidget(self.distance_total_card)
        layout.addWidget(self.fee_total_card)
        return card

    def refresh(self) -> None:
        self._refresh_driver_combo()
        self._set_default_previous_month()
        self.generate_report()

    def _refresh_driver_combo(self) -> None:
        current = self.driver_combo.currentData()
        self.driver_combo.clear()
        self.driver_combo.addItem("همه راننده‌ها", None)
        for driver in self.db.list_drivers():
            self.driver_combo.addItem(driver["full_name"], driver["id"])
        index = self.driver_combo.findData(current)
        if index >= 0:
            self.driver_combo.setCurrentIndex(index)

    def _set_default_previous_month(self) -> None:
        today = gregorian_to_jalali()
        year, month, _ = [int(part) for part in today.split("/")]
        month -= 1
        if month == 0:
            year -= 1
            month = 12
        last_day = 31 if month <= 6 else 30
        if month == 12:
            last_day = 29
        self.start_date_input.setText(to_persian_digits(f"{year:04d}/{month:02d}/01"))
        self.end_date_input.setText(to_persian_digits(f"{year:04d}/{month:02d}/{last_day:02d}"))

    def generate_report(self) -> None:
        start_date = to_english_digits(self.start_date_input.text().strip())
        end_date = to_english_digits(self.end_date_input.text().strip())
        if not self._valid_date(start_date) or not self._valid_date(end_date):
            show_error(self, "بازه تاریخ را با فرمت yyyy/mm/dd وارد کنید.")
            return

        driver_id = self.driver_combo.currentData()
        rows = self.db.list_missions(filters={"driver_id": driver_id} if driver_id else {})
        self.report_rows = [
            self._report_row(row)
            for row in rows
            if start_date <= row["mission_date"] <= end_date
        ]
        self.total_distance = sum(float(row["distance"] or 0) for row in self.report_rows)
        self.total_fee = sum(float(row["driver_fee"] or 0) for row in self.report_rows)
        self._render_table()
        self._render_totals()

    def _report_row(self, mission: dict) -> dict:
        distance = float(mission["distance"] or 0)
        rate = float(mission.get("driver_distance_rate") or 0)
        return {
            **mission,
            "final_destination": self._final_destination(mission["destination"]),
            "driver_fee": distance * rate,
        }

    def _render_table(self) -> None:
        self.table.setRowCount(len(self.report_rows))
        for row, mission in enumerate(self.report_rows):
            values = [
                to_persian_digits(row + 1),
                to_persian_digits(mission["mission_date"]),
                to_persian_digits(mission["mission_time"]),
                mission["driver_name"],
                mission["vehicle"],
                mission["origin"],
                mission["final_destination"],
                to_persian_digits(f"{float(mission['distance']):.1f}"),
                self._format_rial(mission["driver_fee"]),
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(row, col, item)

    def _render_totals(self) -> None:
        self.distance_total_card.deleteLater()
        self.fee_total_card.deleteLater()
        parent_layout = self.root_layout.itemAt(self.root_layout.count() - 1).widget().layout()
        self.distance_total_card = make_stat_card("مسافت کل", to_persian_digits(f"{self.total_distance:.1f}"), PRIMARY_COLOR)
        self.fee_total_card = make_stat_card("حق‌الزحمه راننده", self._format_rial(self.total_fee), SUCCESS_COLOR)
        parent_layout.addWidget(self.distance_total_card)
        parent_layout.addWidget(self.fee_total_card)

    def export_excel(self) -> None:
        if not self.report_rows:
            show_error(self, "داده‌ای برای خروجی Excel وجود ندارد.")
            return
        try:
            from openpyxl import Workbook
            from openpyxl.styles import Alignment, Font, PatternFill
        except ImportError:
            show_error(self, "کتابخانه openpyxl نصب نیست.")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "ذخیره گزارش",
            str(Path.home() / "route-report.xlsx"),
            "Excel Files (*.xlsx)",
        )
        if not file_path:
            return

        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "Route Report"
        sheet.sheet_view.rightToLeft = True
        headers = ["ردیف", "تاریخ", "ساعت", "راننده", "خودرو", "مبدا", "مقصد نهایی", "مسافت", "حق‌الزحمه"]
        sheet.append(headers)
        for index, mission in enumerate(self.report_rows, start=1):
            sheet.append(
                [
                    index,
                    mission["mission_date"],
                    mission["mission_time"],
                    mission["driver_name"],
                    mission["vehicle"],
                    mission["origin"],
                    mission["final_destination"],
                    float(mission["distance"] or 0),
                    float(mission["driver_fee"] or 0),
                ]
            )
        sheet.append([])
        sheet.append(["", "", "", "", "", "", "جمع", self.total_distance, self.total_fee])

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
        show_success(self, "فایل Excel با موفقیت ذخیره شد.")

    @staticmethod
    def _final_destination(destination: str) -> str:
        parts = [part.strip() for part in destination.replace(",", "،").split("،") if part.strip()]
        return parts[-1] if parts else destination

    @staticmethod
    def _valid_date(value: str) -> bool:
        parts = value.split("/")
        if len(parts) != 3 or not all(part.isdigit() for part in parts):
            return False
        year, month, day = [int(part) for part in parts]
        return 1200 <= year <= 1600 and 1 <= month <= 12 and 1 <= day <= 31

    @staticmethod
    def _format_rial(value: float) -> str:
        return f"{to_persian_digits(f'{int(value):,}')} ریال"
