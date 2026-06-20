from __future__ import annotations

import re
from datetime import date, timedelta
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QTextDocument
from PySide6.QtPrintSupport import QPrinter
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QScrollArea,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from database.db import DatabaseError, DatabaseManager
from ui.utils import (
    Page,
    confirm,
    current_time_text,
    gregorian_to_jalali,
    make_stat_card,
    show_error,
    show_success,
    to_english_digits,
    to_persian_digits,
)


DATE_RE = re.compile(r"^\d{4}/\d{2}/\d{2}$")
TIME_RE = re.compile(r"^\d{2}:\d{2}$")


class MissionsPage(Page):
    HOME_VIEW = 0
    FORM_VIEW = 1
    LIST_VIEW = 2
    MAX_DESTINATIONS = 10

    def __init__(self, db: DatabaseManager) -> None:
        super().__init__("ماموریت‌ها", "ثبت و مدیریت ماموریت خودروهای سازمانی")
        self.db = db
        self.selected_id: int | None = None
        self.missions_cache: list[dict] = []
        self.destination_rows: list[tuple[QWidget, QComboBox, QComboBox]] = []
        self._formatting_date = False

        self.stack = QStackedWidget()
        self.stack.addWidget(self._build_home_view())
        self.stack.addWidget(self._build_form_view())
        self.stack.addWidget(self._build_list_view())
        self.root_layout.addWidget(self.stack, stretch=1)

    def _build_home_view(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        self.stats_layout = QGridLayout()
        self.stats_layout.setSpacing(12)
        layout.addLayout(self.stats_layout)

        options_card = self.card()
        options_layout = QHBoxLayout(options_card)
        options_layout.setContentsMargins(24, 24, 24, 24)
        options_layout.setSpacing(18)
        new_button = self._option_button("ثبت ماموریت جدید", "success")
        list_button = self._option_button("لیست ماموریت‌ها", "default")
        new_button.clicked.connect(self.open_new_mission_form)
        list_button.clicked.connect(self.open_missions_list)
        options_layout.addWidget(new_button)
        options_layout.addWidget(list_button)
        layout.addWidget(options_card)

        today_card = self.card()
        today_layout = QVBoxLayout(today_card)
        today_layout.setContentsMargins(18, 16, 18, 16)
        title = QLabel("لیست ماموریت‌های امروز")
        title.setObjectName("sectionTitle")
        self.today_table = QTableWidget(0, 7)
        self.today_table.setHorizontalHeaderLabels(
            ["ردیف", "ساعت", "راننده", "خودرو", "مبدا", "مقصد", "مسافت"]
        )
        self._setup_table(self.today_table)
        today_layout.addWidget(title)
        today_layout.addWidget(self.today_table)
        layout.addWidget(today_card, stretch=1)
        return page

    def _option_button(self, title: str, variant: str) -> QPushButton:
        button = QPushButton(title)
        button.setObjectName("optionButton")
        button.setProperty("variant", variant)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setMinimumHeight(90)
        return button

    def _build_form_view(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        page = QWidget()
        page.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        card = self.card()
        card.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        form_layout = QVBoxLayout(card)
        form_layout.setContentsMargins(18, 16, 18, 16)
        form_layout.setSpacing(12)

        self.form_title = QLabel("ثبت ماموریت جدید")
        self.form_title.setObjectName("sectionTitle")
        form_layout.addWidget(self.form_title)

        self.driver_combo = QComboBox()
        self._prepare_input(self.driver_combo)
        self.driver_combo.currentIndexChanged.connect(self._update_driver_profile)
        self.driver_profile_label = QLabel("پروفایل راننده و خودرو پس از انتخاب راننده نمایش داده می‌شود.")
        self.driver_profile_label.setObjectName("profileInfo")
        self.driver_profile_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.driver_profile_label.setMinimumHeight(38)
        form_layout.addWidget(
            self._two_field_row(
                "راننده *",
                self.driver_combo,
                "پروفایل راننده و خودرو",
                self.driver_profile_label,
                35,
                65,
            )
        )

        self.date_input = QLineEdit()
        self._prepare_input(self.date_input)
        self.date_input.setPlaceholderText("yyyy/mm/dd")
        self.date_input.setMaxLength(10)
        self.date_input.textEdited.connect(self._format_date)
        self.time_input = QLineEdit()
        self._prepare_input(self.time_input)
        self.time_input.setPlaceholderText("HH:MM")
        form_layout.addWidget(
            self._two_field_row("تاریخ *", self.date_input, "ساعت *", self.time_input, 1, 1)
        )

        self.origin_category_combo = QComboBox()
        self.origin_location_combo = QComboBox()
        self._prepare_input(self.origin_category_combo)
        self._prepare_input(self.origin_location_combo)
        self.origin_category_combo.currentIndexChanged.connect(
            lambda: self._populate_location_combo(
                self.origin_category_combo,
                self.origin_location_combo,
            )
        )
        origin_group = QGroupBox("مبدا")
        origin_group.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        origin_layout = QVBoxLayout(origin_group)
        origin_layout.setContentsMargins(12, 14, 12, 12)
        origin_layout.setSpacing(10)
        origin_layout.addWidget(
            self._two_field_row(
                "دسته‌بندی مبدا *",
                self.origin_category_combo,
                "نقطه مبدا *",
                self.origin_location_combo,
                35,
                65,
            )
        )
        form_layout.addWidget(origin_group)

        destinations_group = QGroupBox("مقصدها")
        destinations_group.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        destinations_layout = QVBoxLayout(destinations_group)
        self.destinations_container = QVBoxLayout()
        self.destinations_container.setDirection(QVBoxLayout.Direction.TopToBottom)
        destinations_layout.addLayout(self.destinations_container)
        form_layout.addWidget(destinations_group)

        self.distance_input = QDoubleSpinBox()
        self._prepare_input(self.distance_input)
        self.distance_input.setRange(0, 1_000_000)
        self.distance_input.setDecimals(1)
        self.distance_input.setSuffix(" km")
        self.passengers_input = QLineEdit()
        self._prepare_input(self.passengers_input)
        self.passengers_input.setPlaceholderText("مثال: علی احمدی و رضا محمدی")
        self.description_input = QPlainTextEdit()
        self._prepare_input(self.description_input)
        self.description_input.setFixedHeight(76)
        form_layout.addWidget(self._labeled_row("مسافت *", self.distance_input))
        form_layout.addWidget(self._labeled_row("سرنشینان", self.passengers_input))
        form_layout.addWidget(self._labeled_row("توضیحات", self.description_input))

        buttons = QHBoxLayout()
        buttons.setDirection(QHBoxLayout.Direction.RightToLeft)
        self.save_button = self.action_button("ثبت")
        back_button = self.action_button("بازگشت", "ghost")
        self.save_button.clicked.connect(self.save_mission)
        back_button.clicked.connect(self.back_to_home)
        buttons.addWidget(self.save_button)
        buttons.addWidget(back_button)
        form_layout.addLayout(buttons)

        layout.addWidget(card)
        layout.addStretch(1)
        scroll.setWidget(page)
        return scroll

    def _build_list_view(self) -> QWidget:
        card = self.card()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)

        header = QHBoxLayout()
        title = QLabel("لیست ماموریت‌ها")
        title.setObjectName("sectionTitle")
        back_button = self.action_button("بازگشت", "ghost")
        back_button.clicked.connect(self.back_to_home)
        header.addWidget(title)
        header.addStretch(1)
        header.addWidget(back_button)

        toolbar = QHBoxLayout()
        report_button = self.action_button("گزارش‌گیری", "secondary")
        edit_button = self.action_button("ویرایش", "secondary")
        delete_button = self.action_button("حذف", "danger")
        report_button.clicked.connect(self.report_missions)
        edit_button.clicked.connect(self.edit_selected_mission)
        delete_button.clicked.connect(self.delete_selected_mission)
        toolbar.addWidget(report_button)
        toolbar.addWidget(edit_button)
        toolbar.addWidget(delete_button)
        toolbar.addStretch(1)

        self.list_table = QTableWidget(0, 9)
        self.list_table.setHorizontalHeaderLabels(
            ["شناسه", "تاریخ", "ساعت", "راننده", "خودرو", "مبدا", "مقصد", "مسافت", "توضیحات"]
        )
        self._setup_table(self.list_table)

        layout.addLayout(header)
        layout.addLayout(toolbar)
        layout.addWidget(self.list_table)
        return card

    def _setup_table(self, table: QTableWidget) -> None:
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        table.verticalHeader().setVisible(False)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)

    def _labeled_row(self, label: str, widget: QWidget) -> QWidget:
        return self._field_box(label, widget)

    def _two_field_row(
        self,
        label_a: str,
        widget_a: QWidget,
        label_b: str,
        widget_b: QWidget,
        stretch_a: int,
        stretch_b: int,
    ) -> QWidget:
        row = QWidget()
        row.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        layout = QHBoxLayout(row)
        # Use a physical LTR layout and add the right-side field last so the
        # visible order stays stable even when Qt mirrors RTL widgets.
        layout.setDirection(QHBoxLayout.Direction.LeftToRight)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        layout.addWidget(self._field_box(label_b, widget_b), stretch=stretch_b)
        layout.addWidget(self._field_box(label_a, widget_a), stretch=stretch_a)
        return row

    def _field_box(self, label: str, widget: QWidget) -> QFrame:
        box = QFrame()
        box.setObjectName("fieldBox")
        box.setProperty("missionFormControl", True)
        box.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        layout = QVBoxLayout(box)
        layout.setContentsMargins(12, 10, 12, 12)
        layout.setSpacing(8)
        label_widget = QLabel(label)
        label_widget.setObjectName("fieldLabel")
        label_widget.setProperty("missionFormControl", True)
        label_widget.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(label_widget)
        layout.addWidget(widget)
        return box

    def _prepare_input(self, widget: QWidget) -> None:
        widget.setProperty("missionFormControl", True)
        widget.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        widget.setMinimumHeight(38)
        if isinstance(widget, QLineEdit):
            widget.setAlignment(Qt.AlignmentFlag.AlignRight)
        elif isinstance(widget, QPlainTextEdit):
            widget.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
            widget.setMinimumHeight(76)
        elif isinstance(widget, QDoubleSpinBox):
            widget.setAlignment(Qt.AlignmentFlag.AlignRight)
        elif isinstance(widget, QComboBox):
            # Non-editable QComboBox text alignment is style-dependent in Qt.
            # A read-only line edit gives stable RTL text while preserving dropdown behavior.
            widget.setEditable(True)
            widget.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
            widget.lineEdit().setReadOnly(True)
            widget.lineEdit().setProperty("missionFormControl", True)
            widget.lineEdit().setMinimumHeight(38)
            widget.lineEdit().setAlignment(Qt.AlignmentFlag.AlignRight)
            widget.lineEdit().setLayoutDirection(Qt.LayoutDirection.RightToLeft)
            widget.lineEdit().setFocusPolicy(Qt.FocusPolicy.NoFocus)
            widget.view().setLayoutDirection(Qt.LayoutDirection.RightToLeft)

    def refresh(self) -> None:
        self._refresh_home()
        if hasattr(self, "driver_combo"):
            self._refresh_form_combos()
        if hasattr(self, "list_table"):
            self._refresh_list_table()

    def _refresh_home(self) -> None:
        self._refresh_stats()
        self._refresh_today_table()

    def _refresh_stats(self) -> None:
        while self.stats_layout.count():
            item = self.stats_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        stats = self._mission_period_stats()
        cards = [
            ("ماموریت‌های امروز", stats["today"], "#2563EB"),
            ("این هفته", stats["week"], "#7C3AED"),
            ("این ماه", stats["month"], "#F97316"),
            ("امسال", stats["year"], "#22C55E"),
            ("همه ماموریت‌ها", stats["all"], "#0F172A"),
        ]
        for col, (title, value, color) in enumerate(cards):
            self.stats_layout.addWidget(make_stat_card(title, str(value), color), 0, col)

    def _refresh_today_table(self) -> None:
        today = gregorian_to_jalali()
        rows = self.db.list_missions(filters={"mission_date": today})
        self._populate_table(
            self.today_table,
            rows,
            include_id=False,
            columns=["row", "mission_time", "driver_name", "vehicle", "origin", "destination", "distance"],
        )

    def _refresh_list_table(self) -> None:
        self.missions_cache = self.db.list_missions()
        self._populate_table(
            self.list_table,
            self.missions_cache,
            include_id=True,
            columns=[
                "id",
                "mission_date",
                "mission_time",
                "driver_name",
                "vehicle",
                "origin",
                "destination",
                "distance",
                "description",
            ],
        )

    def _populate_table(
        self,
        table: QTableWidget,
        rows: list[dict],
        include_id: bool,
        columns: list[str],
    ) -> None:
        table.setRowCount(len(rows))
        for row_index, mission in enumerate(rows):
            values: list[str] = []
            for column in columns:
                if column == "row":
                    values.append(to_persian_digits(row_index + 1))
                elif column == "distance":
                    values.append(to_persian_digits(f"{float(mission['distance'] or 0):.1f}"))
                else:
                    values.append(to_persian_digits(mission.get(column) or ""))
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                table.setItem(row_index, col, item)

    def _refresh_form_combos(self) -> None:
        current_driver = self.driver_combo.currentData()
        self.driver_combo.blockSignals(True)
        self.driver_combo.clear()
        for driver in self.db.list_drivers():
            self.driver_combo.addItem(driver["full_name"], driver["id"])
        index = self.driver_combo.findData(current_driver)
        if index >= 0:
            self.driver_combo.setCurrentIndex(index)
        self.driver_combo.blockSignals(False)
        self._populate_category_combo(self.origin_category_combo)
        self._populate_location_combo(self.origin_category_combo, self.origin_location_combo)
        for _, category_combo, location_combo in self.destination_rows:
            self._populate_category_combo(category_combo)
            self._populate_location_combo(category_combo, location_combo)
        self._update_driver_profile()

    def _populate_category_combo(self, combo: QComboBox) -> None:
        current = combo.currentData()
        combo.blockSignals(True)
        combo.clear()
        for category in self.db.list_categories():
            combo.addItem(f"{to_persian_digits(category['sort_order'])} - {category['title']}", category["id"])
        index = combo.findData(current)
        if index >= 0:
            combo.setCurrentIndex(index)
        combo.blockSignals(False)

    def _populate_location_combo(self, category_combo: QComboBox, location_combo: QComboBox) -> None:
        category_id = category_combo.currentData()
        current = location_combo.currentText()
        location_combo.blockSignals(True)
        location_combo.clear()
        for location in self.db.list_locations():
            if category_id is None or location["category_id"] == category_id:
                location_combo.addItem(location["title"])
        if current:
            location_combo.setCurrentText(current)
        location_combo.blockSignals(False)

    def add_destination_row(self, selected_category_id: int | None = None, selected_location: str = "") -> None:
        if len(self.destination_rows) >= self.MAX_DESTINATIONS:
            show_error(self, "حداکثر 10 مقصد قابل ثبت است.")
            return
        row = QWidget()
        row.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        layout = QHBoxLayout(row)
        # Physical order: actions on the left, point in the middle, category on
        # the right. Field contents themselves remain RTL.
        layout.setDirection(QHBoxLayout.Direction.LeftToRight)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        category_combo = QComboBox()
        location_combo = QComboBox()
        self._prepare_input(category_combo)
        self._prepare_input(location_combo)
        add_button = QPushButton("+")
        add_button.setObjectName("destinationActionButton")
        add_button.setProperty("role", "secondary")
        add_button.setFixedSize(42, 42)
        add_button.setCursor(Qt.CursorShape.PointingHandCursor)
        add_button.clicked.connect(lambda: self.add_destination_row())
        remove_button = QPushButton("×")
        remove_button.setObjectName("destinationActionButton")
        remove_button.setProperty("role", "danger")
        remove_button.setFixedSize(42, 42)
        remove_button.setCursor(Qt.CursorShape.PointingHandCursor)
        remove_button.clicked.connect(lambda: self.remove_destination_row(row))
        category_combo.currentIndexChanged.connect(
            lambda: self._populate_location_combo(category_combo, location_combo)
        )
        self._populate_category_combo(category_combo)
        if selected_category_id is not None:
            index = category_combo.findData(selected_category_id)
            if index >= 0:
                category_combo.setCurrentIndex(index)
        self._populate_location_combo(category_combo, location_combo)
        if selected_location:
            location_combo.setCurrentText(selected_location)
        actions = QWidget()
        actions.setObjectName("destinationActions")
        actions_layout = QHBoxLayout(actions)
        actions_layout.setDirection(QHBoxLayout.Direction.LeftToRight)
        actions_layout.setContentsMargins(0, 0, 0, 0)
        actions_layout.setSpacing(8)
        actions_layout.addWidget(add_button)
        actions_layout.addWidget(remove_button)

        layout.addWidget(actions)
        layout.addWidget(self._field_box("نقطه مقصد *", location_combo), stretch=65)
        layout.addWidget(self._field_box("دسته‌بندی مقصد *", category_combo), stretch=35)
        self.destinations_container.addWidget(row)
        self.destination_rows.append((row, category_combo, location_combo))
        self._sync_destination_action_buttons()

    def remove_destination_row(self, row: QWidget) -> None:
        if len(self.destination_rows) <= 1:
            return
        for index, (widget, _, _) in enumerate(self.destination_rows):
            if widget is row:
                self.destination_rows.pop(index)
                widget.deleteLater()
                break
        self._sync_destination_action_buttons()

    def _sync_destination_action_buttons(self) -> None:
        single_row = len(self.destination_rows) <= 1
        at_limit = len(self.destination_rows) >= self.MAX_DESTINATIONS
        for row, _, _ in self.destination_rows:
            buttons = row.findChildren(QPushButton, "destinationActionButton")
            for button in buttons:
                if button.text() == "×":
                    button.setEnabled(not single_row)
                elif button.text() == "+":
                    button.setEnabled(not at_limit)

    def open_new_mission_form(self) -> None:
        self.selected_id = None
        self.form_title.setText("ثبت ماموریت جدید")
        self.save_button.setText("ثبت")
        self.clear_form()
        self._refresh_form_combos()
        self.stack.setCurrentIndex(self.FORM_VIEW)

    def open_missions_list(self) -> None:
        self._refresh_list_table()
        self.stack.setCurrentIndex(self.LIST_VIEW)

    def back_to_home(self) -> None:
        self.selected_id = None
        self.clear_form()
        self._refresh_home()
        self.stack.setCurrentIndex(self.HOME_VIEW)

    def collect_form_data(self) -> dict | None:
        driver = self._selected_driver()
        destinations = [combo.currentText().strip() for _, _, combo in self.destination_rows if combo.currentText().strip()]
        data = {
            "driver_id": self.driver_combo.currentData(),
            "vehicle": self._driver_vehicle_text(driver),
            "mission_date": to_english_digits(self.date_input.text().strip()),
            "mission_time": to_english_digits(self.time_input.text().strip()),
            "origin": self.origin_location_combo.currentText().strip(),
            "destination": "، ".join(destinations),
            "distance": self.distance_input.value(),
            "passengers": self.passengers_input.text().strip(),
            "description": self.description_input.toPlainText().strip(),
        }
        if data["driver_id"] is None:
            show_error(self, "راننده را انتخاب کنید.")
            return None
        if not self._is_valid_date(data["mission_date"]):
            show_error(self, "تاریخ باید با فرمت yyyy/mm/dd وارد شود.")
            return None
        if not self._is_valid_time(data["mission_time"]):
            show_error(self, "ساعت باید با فرمت 24 ساعته HH:MM وارد شود.")
            return None
        if not data["origin"] or not destinations:
            show_error(self, "مبدا و حداقل یک مقصد را انتخاب کنید.")
            return None
        if float(data["distance"]) <= 0:
            show_error(self, "مسافت را به صورت دستی وارد کنید.")
            return None
        return data

    def save_mission(self) -> None:
        data = self.collect_form_data()
        if data is None:
            return
        action_text = "ویرایش" if self.selected_id is not None else "ثبت"
        if not confirm(self, f"آیا از {action_text} ماموریت مطمئن هستید؟"):
            return
        try:
            if self.selected_id is None:
                self.db.add_mission(data)
            else:
                self.db.update_mission(self.selected_id, data)
            show_success(self, "ماموریت با موفقیت ثبت شد.")
            self.back_to_home()
        except DatabaseError as exc:
            show_error(self, f"ثبت ماموریت انجام نشد: {exc}")

    def edit_selected_mission(self) -> None:
        mission = self._current_list_mission()
        if not mission:
            show_error(self, "ابتدا یک ماموریت را انتخاب کنید.")
            return
        self.selected_id = int(mission["id"])
        self.form_title.setText("ویرایش ماموریت")
        self.save_button.setText("ذخیره تغییرات")
        self._refresh_form_combos()
        driver_index = self.driver_combo.findData(mission["driver_id"])
        if driver_index >= 0:
            self.driver_combo.setCurrentIndex(driver_index)
        self.date_input.setText(to_persian_digits(mission["mission_date"]))
        self.time_input.setText(to_persian_digits(mission["mission_time"]))
        origin_category_id = self._category_id_for_location(mission["origin"])
        if origin_category_id is not None:
            origin_category_index = self.origin_category_combo.findData(origin_category_id)
            if origin_category_index >= 0:
                self.origin_category_combo.setCurrentIndex(origin_category_index)
                self._populate_location_combo(self.origin_category_combo, self.origin_location_combo)
        self.origin_location_combo.setCurrentText(mission["origin"])
        self._clear_destination_rows()
        for destination in [item.strip() for item in mission["destination"].split("،") if item.strip()]:
            self.add_destination_row(
                selected_category_id=self._category_id_for_location(destination),
                selected_location=destination,
            )
        if not self.destination_rows:
            self.add_destination_row()
        self.distance_input.setValue(float(mission["distance"] or 0))
        self.passengers_input.setText(mission["passengers"] or "")
        self.description_input.setPlainText(mission["description"] or "")
        self.stack.setCurrentIndex(self.FORM_VIEW)

    def delete_selected_mission(self) -> None:
        mission = self._current_list_mission()
        if not mission:
            show_error(self, "ابتدا یک ماموریت را انتخاب کنید.")
            return
        if not confirm(self, "آیا از حذف ماموریت انتخاب‌شده مطمئن هستید؟"):
            return
        try:
            self.db.delete_mission(int(mission["id"]))
            show_success(self, "ماموریت حذف شد.")
            self._refresh_list_table()
            self._refresh_home()
        except DatabaseError as exc:
            show_error(self, f"حذف ماموریت انجام نشد: {exc}")

    def report_missions(self) -> None:
        period_box = QMessageBox(self)
        period_box.setWindowTitle("نوع گزارش")
        period_box.setText("کدام گزارش را می‌خواهید؟")
        today_button = period_box.addButton("گزارش امروز", QMessageBox.ButtonRole.AcceptRole)
        week_button = period_box.addButton("گزارش هفته گذشته", QMessageBox.ButtonRole.AcceptRole)
        month_button = period_box.addButton("گزارش ماه گذشته", QMessageBox.ButtonRole.AcceptRole)
        period_box.addButton("انصراف", QMessageBox.ButtonRole.RejectRole)
        period_box.exec()
        clicked_period = period_box.clickedButton()
        if clicked_period == today_button:
            rows = self._missions_for_last_days(1)
            title = "گزارش امروز"
        elif clicked_period == week_button:
            rows = self._missions_for_last_days(7)
            title = "گزارش هفته گذشته"
        elif clicked_period == month_button:
            rows = self._missions_for_last_days(30)
            title = "گزارش ماه گذشته"
        else:
            return
        if not rows:
            show_error(self, "داده‌ای برای گزارش انتخاب‌شده وجود ندارد.")
            return

        format_box = QMessageBox(self)
        format_box.setWindowTitle("فرمت خروجی")
        format_box.setText("فرمت خروجی را انتخاب کنید.")
        excel_button = format_box.addButton("Excel", QMessageBox.ButtonRole.AcceptRole)
        pdf_button = format_box.addButton("PDF", QMessageBox.ButtonRole.AcceptRole)
        format_box.addButton("انصراف", QMessageBox.ButtonRole.RejectRole)
        format_box.exec()
        clicked_format = format_box.clickedButton()
        if clicked_format == excel_button:
            self.export_excel(rows, title)
        elif clicked_format == pdf_button:
            self.export_pdf(rows, title)

    def export_excel(self, rows: list[dict], title: str) -> None:
        try:
            from openpyxl import Workbook
            from openpyxl.styles import Alignment, Font, PatternFill
        except ImportError:
            show_error(self, "کتابخانه openpyxl نصب نیست.")
            return
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "ذخیره گزارش ماموریت",
            str(Path.home() / "route-missions-report.xlsx"),
            "Excel Files (*.xlsx)",
        )
        if not file_path:
            return
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "Missions"
        sheet.sheet_view.rightToLeft = True
        headers = ["ردیف", "تاریخ", "ساعت", "راننده", "خودرو", "مبدا", "مقصد", "مسافت", "سرنشینان", "توضیحات"]
        sheet.append([title])
        sheet.append(headers)
        for index, mission in enumerate(rows, start=1):
            sheet.append(
                [
                    index,
                    to_persian_digits(mission["mission_date"]),
                    to_persian_digits(mission["mission_time"]),
                    mission["driver_name"],
                    mission["vehicle"],
                    mission["origin"],
                    mission["destination"],
                    to_persian_digits(f"{float(mission['distance'] or 0):.1f}"),
                    mission["passengers"] or "",
                    mission["description"] or "",
                ]
            )
        sheet.merge_cells(start_row=1, start_column=1, end_row=1, end_column=len(headers))
        sheet.cell(1, 1).font = Font(bold=True, size=14)
        sheet.cell(1, 1).alignment = Alignment(horizontal="center")
        header_fill = PatternFill("solid", fgColor="2563EB")
        header_font = Font(color="FFFFFF", bold=True)
        for cell in sheet[2]:
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal="center")
        for row in sheet.iter_rows(min_row=3):
            for cell in row:
                cell.alignment = Alignment(horizontal="center", vertical="center")
        for column in sheet.columns:
            max_length = max(len(str(cell.value or "")) for cell in column)
            sheet.column_dimensions[column[0].column_letter].width = min(max_length + 4, 48)
        workbook.save(file_path)
        show_success(self, "گزارش Excel با موفقیت ذخیره شد.")

    def export_pdf(self, rows: list[dict], title: str) -> None:
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "ذخیره گزارش PDF",
            str(Path.home() / "route-missions-report.pdf"),
            "PDF Files (*.pdf)",
        )
        if not file_path:
            return
        html_rows = ""
        for index, mission in enumerate(rows, start=1):
            distance_text = to_persian_digits(f"{float(mission['distance'] or 0):.1f}")
            html_rows += (
                "<tr>"
                f"<td>{to_persian_digits(index)}</td><td>{to_persian_digits(mission['mission_date'])}</td><td>{to_persian_digits(mission['mission_time'])}</td>"
                f"<td>{mission['driver_name']}</td><td>{mission['vehicle']}</td>"
                f"<td>{mission['origin']}</td><td>{mission['destination']}</td>"
                f"<td>{distance_text}</td>"
                "</tr>"
            )
        html = f"""
        <html dir="rtl">
        <head>
        <meta charset="utf-8">
        <style>
            body {{ font-family: Tahoma; direction: rtl; }}
            table {{ border-collapse: collapse; width: 100%; }}
            th, td {{ border: 1px solid #cccccc; padding: 6px; text-align: center; }}
            th {{ background: #2563EB; color: white; }}
        </style>
        </head>
        <body>
            <h2>{title}</h2>
            <table>
                <tr>
                    <th>ردیف</th><th>تاریخ</th><th>ساعت</th><th>راننده</th>
                    <th>خودرو</th><th>مبدا</th><th>مقصد</th><th>مسافت</th>
                </tr>
                {html_rows}
            </table>
        </body>
        </html>
        """
        document = QTextDocument()
        document.setHtml(html)
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
        printer.setOutputFileName(file_path)
        document.print_(printer)
        show_success(self, "گزارش PDF با موفقیت ذخیره شد.")

    def clear_form(self) -> None:
        self.date_input.setText(to_persian_digits(gregorian_to_jalali()))
        self.time_input.setText(to_persian_digits(current_time_text()[:5]))
        self.distance_input.setValue(0)
        self.passengers_input.clear()
        self.description_input.clear()
        self._clear_destination_rows()
        self.add_destination_row()
        if self.origin_category_combo.count():
            self.origin_category_combo.setCurrentIndex(0)
        self._populate_location_combo(self.origin_category_combo, self.origin_location_combo)

    def _clear_destination_rows(self) -> None:
        for row, _, _ in self.destination_rows:
            row.deleteLater()
        self.destination_rows.clear()

    def _selected_driver(self) -> dict | None:
        driver_id = self.driver_combo.currentData()
        if driver_id is None:
            return None
        for driver in self.db.list_drivers():
            if int(driver["id"]) == int(driver_id):
                return driver
        return None

    def _update_driver_profile(self) -> None:
        driver = self._selected_driver()
        if not driver:
            self.driver_profile_label.setText("پروفایل راننده و خودرو پس از انتخاب راننده نمایش داده می‌شود.")
            return
        self.driver_profile_label.setText(
            " | ".join(
                [
                    f"راننده: {driver['full_name']}",
                    f"خودرو: {self._driver_vehicle_text(driver)}",
                    f"موبایل: {to_persian_digits(driver.get('mobile') or '-')}",
                ]
            )
        )

    @staticmethod
    def _driver_vehicle_text(driver: dict | None) -> str:
        if not driver:
            return ""
        parts = [driver.get("car_model", ""), driver.get("car_year", ""), driver.get("car_color", "")]
        return " - ".join(part for part in parts if part).strip()

    def _current_list_mission(self) -> dict | None:
        row = self.list_table.currentRow()
        if row < 0 or row >= len(self.missions_cache):
            return None
        return self.missions_cache[row]

    def _category_id_for_location(self, title: str) -> int | None:
        for location in self.db.list_locations():
            if location["title"] == title:
                return int(location["category_id"])
        return None

    def _mission_period_stats(self) -> dict[str, int]:
        rows = self.db.list_missions()
        today = gregorian_to_jalali()
        week_dates = set(self._jalali_dates_for_last_days(7))
        month_prefix = today[:7]
        year_prefix = today[:4]
        return {
            "today": sum(1 for row in rows if row["mission_date"] == today),
            "week": sum(1 for row in rows if row["mission_date"] in week_dates),
            "month": sum(1 for row in rows if row["mission_date"].startswith(month_prefix)),
            "year": sum(1 for row in rows if row["mission_date"].startswith(year_prefix)),
            "all": len(rows),
        }

    def _missions_for_last_days(self, days: int) -> list[dict]:
        dates = set(self._jalali_dates_for_last_days(days))
        return [mission for mission in self.db.list_missions() if mission["mission_date"] in dates]

    @staticmethod
    def _jalali_dates_for_last_days(days: int) -> list[str]:
        return [gregorian_to_jalali(date.today() - timedelta(days=offset)) for offset in range(days)]

    def _format_date(self, text: str) -> None:
        if self._formatting_date:
            return
        self._formatting_date = True
        digits = "".join(ch for ch in to_english_digits(text) if ch.isdigit())[:8]
        if len(digits) <= 4:
            formatted = digits
        elif len(digits) <= 6:
            formatted = f"{digits[:4]}/{digits[4:]}"
        else:
            formatted = f"{digits[:4]}/{digits[4:6]}/{digits[6:]}"
        self.date_input.setText(to_persian_digits(formatted))
        self.date_input.setCursorPosition(len(formatted))
        self._formatting_date = False

    @staticmethod
    def _is_valid_date(value: str) -> bool:
        value = to_english_digits(value)
        if not DATE_RE.fullmatch(value):
            return False
        _, month, day = (int(part) for part in value.split("/"))
        return 1 <= month <= 12 and 1 <= day <= 31

    @staticmethod
    def _is_valid_time(value: str) -> bool:
        value = to_english_digits(value)
        if not TIME_RE.fullmatch(value):
            return False
        hour, minute = (int(part) for part in value.split(":"))
        return 0 <= hour <= 23 and 0 <= minute <= 59
