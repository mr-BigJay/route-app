from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFormLayout,
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
        super().__init__("رانندگان", "ثبت، ویرایش و حذف رانندگان سازمان")
        self.db = db
        self.selected_id: int | None = None

        body = QHBoxLayout()
        body.setSpacing(16)
        body.addWidget(self._table_card(), stretch=2)
        body.addWidget(self._form_card(), stretch=1)
        self.root_layout.addLayout(body, stretch=1)

    def _form_card(self):
        card = self.card()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(14)
        title = QLabel("فرم راننده")
        title.setObjectName("sectionTitle")
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        self.full_name_input = QLineEdit()
        self.full_name_input.setPlaceholderText("نام و نام خانوادگی")
        form.addRow("نام راننده *", self.full_name_input)

        buttons = QHBoxLayout()
        self.save_button = self.action_button("ثبت راننده")
        self.update_button = self.action_button("ویرایش", "secondary")
        self.delete_button = self.action_button("حذف", "danger")
        self.clear_button = self.action_button("پاک کردن", "ghost")
        self.save_button.clicked.connect(self.add_driver)
        self.update_button.clicked.connect(self.update_driver)
        self.delete_button.clicked.connect(self.delete_driver)
        self.clear_button.clicked.connect(self.clear_form)
        buttons.addWidget(self.save_button)
        buttons.addWidget(self.update_button)
        buttons.addWidget(self.delete_button)
        buttons.addWidget(self.clear_button)

        layout.addWidget(title)
        layout.addLayout(form)
        layout.addLayout(buttons)
        layout.addStretch(1)
        return card

    def _table_card(self):
        card = self.card()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 16, 18, 16)
        title = QLabel("لیست رانندگان")
        title.setObjectName("sectionTitle")
        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["شناسه", "نام راننده"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.itemSelectionChanged.connect(self.on_selection_changed)
        layout.addWidget(title)
        layout.addWidget(self.table)
        return card

    def refresh(self) -> None:
        drivers = self.db.list_drivers()
        self.table.setRowCount(len(drivers))
        for row, driver in enumerate(drivers):
            values = [str(driver["id"]), driver["full_name"]]
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(row, col, item)

    def validate(self) -> str | None:
        full_name = self.full_name_input.text().strip()
        if not full_name:
            show_error(self, "نام راننده را وارد کنید.")
            return None
        return full_name

    def add_driver(self) -> None:
        full_name = self.validate()
        if not full_name:
            return
        try:
            self.db.add_driver(full_name)
            show_success(self, "راننده با موفقیت ثبت شد.")
            self.clear_form()
            self.refresh()
        except DatabaseError as exc:
            show_error(self, f"ثبت راننده انجام نشد: {exc}")

    def update_driver(self) -> None:
        if self.selected_id is None:
            show_error(self, "ابتدا یک راننده را انتخاب کنید.")
            return
        full_name = self.validate()
        if not full_name:
            return
        try:
            self.db.update_driver(self.selected_id, full_name)
            show_success(self, "اطلاعات راننده ویرایش شد.")
            self.clear_form()
            self.refresh()
        except DatabaseError as exc:
            show_error(self, f"ویرایش راننده انجام نشد: {exc}")

    def delete_driver(self) -> None:
        if self.selected_id is None:
            show_error(self, "ابتدا یک راننده را انتخاب کنید.")
            return
        if not confirm(self, "آیا از حذف راننده انتخاب‌شده مطمئن هستید؟"):
            return
        try:
            self.db.delete_driver(self.selected_id)
            show_success(self, "راننده حذف شد.")
            self.clear_form()
            self.refresh()
        except DatabaseError as exc:
            show_error(self, f"حذف راننده انجام نشد: {exc}")

    def on_selection_changed(self) -> None:
        row = self.table.currentRow()
        if row < 0:
            return
        self.selected_id = int(self.table.item(row, 0).text())
        self.full_name_input.setText(self.table.item(row, 1).text())

    def clear_form(self) -> None:
        self.selected_id = None
        self.full_name_input.clear()
        self.table.clearSelection()
