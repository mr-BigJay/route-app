from __future__ import annotations

import re

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QTextOption
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from database.db import DatabaseError, DatabaseManager
from ui.form_widgets import (
    NoWheelComboBox,
    NoWheelDoubleSpinBox,
    FORM_FIELD_HEIGHT,
    apply_form_field_font,
    configure_combo_field,
    configure_line_edit_field,
    configure_spin_field,
)
from ui.utils import confirm, current_time_text, gregorian_to_jalali, show_error, show_success, to_english_digits, to_persian_digits


DATE_RE = re.compile(r"^\d{4}/\d{2}/\d{2}$")
TIME_RE = re.compile(r"^\d{2}:\d{2}$")


class MissionFormWidget(QWidget):
    saved = Signal()
    cancelled = Signal()

    MAX_DESTINATIONS = 10

    def __init__(self, db: DatabaseManager, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.db = db
        self.selected_id: int | None = None
        self.destination_rows: list[tuple[QWidget, NoWheelComboBox, NoWheelComboBox]] = []
        self._formatting_date = False
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.setObjectName("missionFormWidget")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(4, 4, 4, 4)
        root.setSpacing(0)

        container = QWidget()
        container.setObjectName("missionFormContainer")
        container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        title_bar = QFrame()
        title_bar.setObjectName("missionFormHeader")
        title_layout = QVBoxLayout(title_bar)
        title_layout.setContentsMargins(18, 16, 18, 14)
        title_layout.setSpacing(4)
        self.form_title = QLabel("ثبت ماموریت جدید")
        self.form_title.setObjectName("missionFormTitle")
        self.form_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.form_title.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.form_subtitle = QLabel("اطلاعات ماموریت را تکمیل کنید")
        self.form_subtitle.setObjectName("missionFormSubtitle")
        self.form_subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.form_subtitle.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        title_layout.addWidget(self.form_title)
        title_layout.addWidget(self.form_subtitle)

        form_body = QWidget()
        form_body.setObjectName("missionFormBody")
        body_layout = QVBoxLayout(form_body)
        body_layout.setContentsMargins(14, 14, 14, 14)
        body_layout.setSpacing(12)

        self.driver_combo = NoWheelComboBox()
        self._prepare_combo(self.driver_combo)
        self.driver_combo.currentIndexChanged.connect(self._update_driver_profile)
        self.driver_profile_label = QLabel("پروفایل راننده و خودرو پس از انتخاب راننده نمایش داده می‌شود.")
        self.driver_profile_label.setObjectName("profileInfo")
        apply_form_field_font(self.driver_profile_label)
        self.driver_profile_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.driver_profile_label.setMinimumHeight(FORM_FIELD_HEIGHT)
        self.driver_profile_label.setMaximumHeight(FORM_FIELD_HEIGHT)
        self.date_input = QLineEdit()
        self._prepare_input(self.date_input)
        self.date_input.setPlaceholderText("yyyy/mm/dd")
        self.date_input.setMaxLength(10)
        self.date_input.textEdited.connect(self._format_date)
        self.time_input = QLineEdit()
        self._prepare_input(self.time_input)
        self.time_input.setPlaceholderText("HH:MM")
        self.passengers_input = QLineEdit()
        self._prepare_input(self.passengers_input)
        self.passengers_input.setPlaceholderText("مثال: علی احمدی و رضا محمدی")
        body_layout.addWidget(self._driver_section())

        self.origin_category_combo = NoWheelComboBox()
        self.origin_location_combo = NoWheelComboBox()
        self._prepare_combo(self.origin_category_combo)
        self._prepare_combo(self.origin_location_combo)
        self.origin_category_combo.currentIndexChanged.connect(
            lambda: self._populate_location_combo(self.origin_category_combo, self.origin_location_combo)
        )
        origin_group = self._section_group("مبدا")
        origin_layout = origin_group.layout()
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
        body_layout.addWidget(origin_group)

        destinations_group = self._section_group("مقصدها")
        destinations_layout = destinations_group.layout()
        self.destinations_container = QVBoxLayout()
        self.destinations_container.setDirection(QVBoxLayout.Direction.TopToBottom)
        self.destinations_container.setSpacing(6)
        self.destinations_container.setContentsMargins(0, 0, 0, 0)
        destinations_layout.addLayout(self.destinations_container)
        body_layout.addWidget(destinations_group)

        self.distance_input = NoWheelDoubleSpinBox()
        self._prepare_spin(self.distance_input)
        self.distance_input.setRange(0, 1_000_000)
        self.distance_input.setDecimals(1)
        self.distance_input.setSuffix(" km")
        self.description_input = QPlainTextEdit()
        self._prepare_text_area(self.description_input)
        self.description_input.setFixedHeight(56)
        body_layout.addWidget(self._labeled_row("مسافت *", self.distance_input))
        body_layout.addWidget(self._labeled_row("توضیحات", self.description_input))

        buttons = QHBoxLayout()
        buttons.setSpacing(10)
        self.save_button = self._action_button("ثبت", "primary")
        back_button = self._action_button("بازگشت", "ghost")
        self.save_button.clicked.connect(self.save_mission)
        back_button.clicked.connect(self.cancelled.emit)
        buttons.addStretch(1)
        buttons.addWidget(self.save_button)
        buttons.addWidget(back_button)
        buttons.addStretch(1)
        body_layout.addLayout(buttons)

        layout.addWidget(title_bar)
        layout.addWidget(form_body)

        root.addWidget(container, 1)

    def _driver_section(self) -> QWidget:
        section = QWidget()
        section.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        grid = QGridLayout(section)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(12)

        date_time_column = QWidget()
        date_time_column.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        date_time_layout = QHBoxLayout(date_time_column)
        date_time_layout.setDirection(QHBoxLayout.Direction.LeftToRight)
        date_time_layout.setContentsMargins(0, 0, 0, 0)
        date_time_layout.setSpacing(8)
        date_time_layout.addWidget(self._field_box("ساعت *", self.time_input), stretch=2)
        date_time_layout.addWidget(self._field_box("تاریخ *", self.date_input), stretch=3)

        grid.addWidget(self._field_box("پروفایل راننده و خودرو", self.driver_profile_label), 0, 0)
        grid.addWidget(self._field_box("راننده *", self.driver_combo), 0, 1)
        grid.addWidget(self._field_box("سرنشینان", self.passengers_input), 1, 0)
        grid.addWidget(date_time_column, 1, 1)
        grid.setColumnStretch(0, 65)
        grid.setColumnStretch(1, 35)
        return section

    def _section_group(self, title: str) -> QFrame:
        group = QFrame()
        group.setObjectName("missionFormGroup")
        group.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        layout = QVBoxLayout(group)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(6)
        layout.addWidget(self._right_label_row(title, "missionSectionTitle"))
        return group

    def _right_label_row(self, text: str, object_name: str) -> QWidget:
        row = QWidget()
        row.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        label = QLabel(text)
        label.setObjectName(object_name)
        label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        layout.addWidget(label)
        layout.addStretch(1)
        return row

    def _action_button(self, text: str, role: str) -> QPushButton:
        button = QPushButton(text)
        button.setObjectName("missionFormActionButton")
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setProperty("role", role)
        button.setFixedSize(132, 51)
        return button

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
        row.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        layout = QHBoxLayout(row)
        layout.setDirection(QHBoxLayout.Direction.LeftToRight)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(self._field_box(label_b, widget_b), stretch=stretch_b)
        layout.addWidget(self._field_box(label_a, widget_a), stretch=stretch_a)
        return row

    def _field_box(self, label: str, widget: QWidget) -> QFrame:
        box = QFrame()
        box.setObjectName("missionFieldBox")
        box.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        layout = QVBoxLayout(box)
        layout.setContentsMargins(8, 6, 8, 8)
        layout.setSpacing(4)
        layout.addWidget(self._right_label_row(label, "fieldLabel"))
        widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        layout.addWidget(widget)
        return box

    def _prepare_input(self, widget: QLineEdit) -> None:
        widget.setObjectName("missionFormInput")
        widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        configure_line_edit_field(widget)
        self._ensure_line_edit_alignment(widget)

    def _ensure_line_edit_alignment(self, widget: QLineEdit) -> None:
        widget.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        widget.setAttribute(Qt.WidgetAttribute.WA_RightToLeft, True)
        placeholder = widget.placeholderText()
        if placeholder:
            widget.setPlaceholderText("")
            widget.setPlaceholderText(placeholder)
        apply_form_field_font(widget)
        widget.setAlignment(Qt.AlignmentFlag.AlignCenter)

    def _prepare_text_area(self, widget: QPlainTextEdit) -> None:
        widget.setObjectName("missionFormInput")
        widget.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        widget.setAttribute(Qt.WidgetAttribute.WA_RightToLeft, True)
        text_option = widget.document().defaultTextOption()
        text_option.setAlignment(Qt.AlignmentFlag.AlignCenter)
        widget.document().setDefaultTextOption(text_option)
        apply_form_field_font(widget)

    def _prepare_combo(self, combo: NoWheelComboBox) -> None:
        combo.setObjectName("missionFormInput")
        combo.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        combo.setAttribute(Qt.WidgetAttribute.WA_RightToLeft, True)
        combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        combo.setEditable(True)
        combo.currentTextChanged.connect(lambda _text: self._ensure_combo_alignment(combo))
        self._ensure_combo_alignment(combo)
        combo.view().setLayoutDirection(Qt.LayoutDirection.RightToLeft)

    def _ensure_combo_alignment(self, combo: NoWheelComboBox) -> None:
        line_edit = combo.lineEdit()
        if line_edit is None:
            return
        line_edit.setReadOnly(True)
        line_edit.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        line_edit.setAttribute(Qt.WidgetAttribute.WA_RightToLeft, True)
        configure_combo_field(combo)
        line_edit.setAlignment(Qt.AlignmentFlag.AlignCenter)

    def _prepare_spin(self, widget: NoWheelDoubleSpinBox) -> None:
        widget.setObjectName("missionFormInput")
        widget.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        configure_spin_field(widget)
        widget.setAlignment(Qt.AlignmentFlag.AlignCenter)

    def refresh_combos(self) -> None:
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

    def _populate_category_combo(self, combo: NoWheelComboBox) -> None:
        current = combo.currentData()
        combo.blockSignals(True)
        combo.clear()
        for category in self.db.list_categories():
            combo.addItem(category["title"], category["id"])
        index = combo.findData(current)
        if index >= 0:
            combo.setCurrentIndex(index)
        combo.blockSignals(False)
        self._ensure_combo_alignment(combo)

    def _populate_location_combo(self, category_combo: NoWheelComboBox, location_combo: NoWheelComboBox) -> None:
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
        self._ensure_combo_alignment(location_combo)

    def add_destination_row(self, selected_category_id: int | None = None, selected_location: str = "") -> None:
        if len(self.destination_rows) >= self.MAX_DESTINATIONS:
            show_error(self, "حداکثر 10 مقصد قابل ثبت است.")
            return
        row = QWidget()
        row.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        layout = QHBoxLayout(row)
        layout.setDirection(QHBoxLayout.Direction.LeftToRight)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        category_combo = NoWheelComboBox()
        location_combo = NoWheelComboBox()
        self._prepare_combo(category_combo)
        self._prepare_combo(location_combo)
        add_button = QPushButton("+")
        add_button.setObjectName("destinationActionButton")
        add_button.setProperty("role", "secondary")
        add_button.setFixedSize(24, 24)
        add_button.setCursor(Qt.CursorShape.PointingHandCursor)
        add_button.clicked.connect(lambda: self.add_destination_row())
        remove_button = QPushButton("×")
        remove_button.setObjectName("destinationActionButton")
        remove_button.setProperty("role", "danger")
        remove_button.setFixedSize(24, 24)
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
        actions.setFixedWidth(28)
        actions_layout = QVBoxLayout(actions)
        actions_layout.setDirection(QVBoxLayout.Direction.TopToBottom)
        actions_layout.setContentsMargins(0, 24, 0, 0)
        actions_layout.setSpacing(4)
        actions_layout.addWidget(add_button, alignment=Qt.AlignmentFlag.AlignHCenter)
        actions_layout.addWidget(remove_button, alignment=Qt.AlignmentFlag.AlignHCenter)
        actions_layout.addStretch(1)
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

    def prepare_new(self) -> None:
        self.selected_id = None
        self.form_title.setText("ثبت ماموریت جدید")
        self.save_button.setText("ثبت")
        self.clear_form()
        self.refresh_combos()

    def load_mission(self, mission: dict) -> None:
        self.selected_id = int(mission["id"])
        self.form_title.setText("ویرایش ماموریت")
        self.save_button.setText("ذخیره تغییرات")
        self.refresh_combos()
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
            self.saved.emit()
        except DatabaseError as exc:
            show_error(self, f"ثبت ماموریت انجام نشد: {exc}")

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

    def _category_id_for_location(self, title: str) -> int | None:
        for location in self.db.list_locations():
            if location["title"] == title:
                return int(location["category_id"])
        return None

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
        self._ensure_line_edit_alignment(self.date_input)
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
