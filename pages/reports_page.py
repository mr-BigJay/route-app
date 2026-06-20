from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
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
        super().__init__("گزارشات", "گزارش‌گیری و خروجی Excel")
        self.db = db
        self.report_rows: list[dict] = []
        self.root_layout.addWidget(self._filters_card())
        self.summary_layout = QGridLayout()
        self.summary_layout.setSpacing(14)
        self.root_layout.addLayout(self.summary_layout)
        self.root_layout.addWidget(self._table_card(), stretch=1)

    def _filters_card(self):
        card = self.card()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 16, 18, 16)
        title = QLabel("فیلتر گزارش")
        title.setObjectName("sectionTitle")
        form = QFormLayout()
        self.report_type_combo = QComboBox()
        self.report_type_combo.addItems(
            ["گزارش روزانه", "گزارش ماهانه", "گزارش راننده", "گزارش مقصد", "همه ماموریت‌ها"]
        )
        self.date_input = QLineEdit(to_persian_digits(gregorian_to_jalali()))
        self.date_input.setPlaceholderText("1403/11/20")
        self.month_input = QLineEdit(to_persian_digits(gregorian_to_jalali()[:7]))
        self.month_input.setPlaceholderText("1403/11")
        self.driver_combo = QComboBox()
        self.destination_combo = QComboBox()
        form.addRow("نوع گزارش", self.report_type_combo)
        form.addRow("تاریخ", self.date_input)
        form.addRow("ماه", self.month_input)
        form.addRow("راننده", self.driver_combo)
        form.addRow("مقصد", self.destination_combo)

        buttons = QHBoxLayout()
        generate_button = self.action_button("نمایش گزارش")
        export_button = self.action_button("خروجی Excel", "secondary")
        generate_button.clicked.connect(self.generate_report)
        export_button.clicked.connect(self.export_excel)
        buttons.addWidget(generate_button)
        buttons.addWidget(export_button)

        layout.addWidget(title)
        layout.addLayout(form)
        layout.addLayout(buttons)
        return card

    def _table_card(self):
        card = self.card()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 16, 18, 16)
        title = QLabel("نتایج گزارش")
        title.setObjectName("sectionTitle")
        self.table = QTableWidget(0, 9)
        self.table.setHorizontalHeaderLabels(
            ["ردیف", "تاریخ", "ساعت", "راننده", "خودرو", "مبدا", "مقصد", "مسافت", "توضیحات"]
        )
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(title)
        layout.addWidget(self.table)
        return card

    def refresh(self) -> None:
        self._refresh_combos()
        self.generate_report()

    def _refresh_combos(self) -> None:
        current_driver = self.driver_combo.currentData()
        self.driver_combo.clear()
        for driver in self.db.list_drivers():
            self.driver_combo.addItem(driver["full_name"], driver["id"])
        driver_index = self.driver_combo.findData(current_driver)
        if driver_index >= 0:
            self.driver_combo.setCurrentIndex(driver_index)

        current_destination = self.destination_combo.currentText()
        self.destination_combo.clear()
        destinations = sorted({location["title"] for location in self.db.list_locations()})
        self.destination_combo.addItems(destinations)
        if current_destination:
            self.destination_combo.setCurrentText(current_destination)

    def _filters(self) -> dict:
        report_type = self.report_type_combo.currentText()
        filters: dict = {}
        if report_type == "گزارش روزانه":
            filters["mission_date"] = to_english_digits(self.date_input.text().strip())
        elif report_type == "گزارش ماهانه":
            filters["month"] = to_english_digits(self.month_input.text().strip())
        elif report_type == "گزارش راننده":
            filters["driver_id"] = self.driver_combo.currentData()
        elif report_type == "گزارش مقصد":
            filters["destination"] = self.destination_combo.currentText().strip()
        return {key: value for key, value in filters.items() if value not in (None, "")}

    def generate_report(self) -> None:
        filters = self._filters()
        self.report_rows = self.db.list_missions(filters=filters)
        totals = self.db.report_totals(filters=filters)
        self._render_summary(totals)
        self._render_table()

    def _render_summary(self, totals: dict) -> None:
        while self.summary_layout.count():
            item = self.summary_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        self.summary_layout.addWidget(
            make_stat_card("جمع کل ماموریت‌ها", str(totals["missions"]), PRIMARY_COLOR),
            0,
            0,
        )
        self.summary_layout.addWidget(
            make_stat_card("جمع کل کیلومتر", f"{totals['distance']:.1f}", SUCCESS_COLOR),
            0,
            1,
        )

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
                mission["destination"],
                to_persian_digits(f"{float(mission['distance']):.1f}"),
                mission["description"] or "",
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(to_persian_digits(value))
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(row, col, item)

    def export_excel(self) -> None:
        if not self.report_rows:
            show_error(self, "داده‌ای برای خروجی Excel وجود ندارد.")
            return
        try:
            from openpyxl import Workbook
            from openpyxl.styles import Alignment, Font, PatternFill
        except ImportError:
            show_error(self, "کتابخانه openpyxl نصب نیست. ابتدا وابستگی‌های پروژه را نصب کنید.")
            return

        default_name = f"route-report-{gregorian_to_jalali().replace('/', '-')}.xlsx"
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "ذخیره گزارش",
            str(Path.home() / default_name),
            "Excel Files (*.xlsx)",
        )
        if not file_path:
            return

        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "Route Report"
        sheet.sheet_view.rightToLeft = True
        headers = ["ردیف", "تاریخ", "ساعت", "راننده", "خودرو", "مبدا", "مقصد", "مسافت", "سرنشینان", "توضیحات"]
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
                    mission["destination"],
                    float(mission["distance"] or 0),
                    mission["passengers"] or "",
                    mission["description"] or "",
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
        sheet.freeze_panes = "A2"
        workbook.save(file_path)
        show_success(self, "فایل Excel با موفقیت ذخیره شد.")
