from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QSpinBox,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
)

from database.db import DatabaseError, DatabaseManager
from ui.utils import Page, confirm, make_stat_card, show_error, show_success


PERMANENT_CATEGORY_TITLES = ["ستاد", "بیمارستان", "مرکز درمانی", "خانه بهداشت"]


class LocationsPage(Page):
    def __init__(self, db: DatabaseManager) -> None:
        super().__init__("مدیریت نقاط", "مدیریت دسته‌بندی‌ها و نقاط ماموریت")
        self.db = db
        self.selected_category_id: int | None = None
        self.selected_location_id: int | None = None

        self.stats_layout = QGridLayout()
        self.stats_layout.setSpacing(12)
        self.root_layout.addLayout(self.stats_layout)

        body = QHBoxLayout()
        body.setDirection(QHBoxLayout.Direction.LeftToRight)
        body.setSpacing(16)
        body.addWidget(self._tree_card(), stretch=2)

        forms = QVBoxLayout()
        forms.setSpacing(16)
        forms.addWidget(self._category_form_card())
        forms.addWidget(self._location_form_card())
        body.addLayout(forms, stretch=1)
        self.root_layout.addLayout(body, stretch=1)

    def _category_form_card(self):
        card = self.card()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)
        title = QLabel("دسته‌بندی‌ها")
        title.setObjectName("sectionTitle")
        form = QFormLayout()
        self.category_order_input = QSpinBox()
        self.category_order_input.setRange(1, 999)
        self.category_title_input = QLineEdit()
        self.category_title_input.setPlaceholderText("مثال: اورژانس")
        form.addRow("شماره ترتیب *", self.category_order_input)
        form.addRow("عنوان *", self.category_title_input)

        buttons = QHBoxLayout()
        add_button = self.action_button("ثبت دسته")
        update_button = self.action_button("ویرایش", "secondary")
        delete_button = self.action_button("حذف", "danger")
        add_button.clicked.connect(self.add_category)
        update_button.clicked.connect(self.update_category)
        delete_button.clicked.connect(self.delete_category)
        buttons.addWidget(add_button)
        buttons.addWidget(update_button)
        buttons.addWidget(delete_button)

        layout.addWidget(title)
        layout.addLayout(form)
        layout.addLayout(buttons)
        return card

    def _location_form_card(self):
        card = self.card()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)
        title = QLabel("نقاط")
        title.setObjectName("sectionTitle")
        form = QFormLayout()
        self.location_category_combo = QComboBox()
        self.location_title_input = QLineEdit()
        self.location_title_input.setPlaceholderText("مثال: مرکز کلاچای")
        form.addRow("دسته‌بندی *", self.location_category_combo)
        form.addRow("عنوان نقطه *", self.location_title_input)

        buttons = QHBoxLayout()
        add_button = self.action_button("ثبت نقطه")
        update_button = self.action_button("ویرایش", "secondary")
        delete_button = self.action_button("حذف", "danger")
        add_button.clicked.connect(self.add_location)
        update_button.clicked.connect(self.update_location)
        delete_button.clicked.connect(self.delete_location)
        buttons.addWidget(add_button)
        buttons.addWidget(update_button)
        buttons.addWidget(delete_button)

        layout.addWidget(title)
        layout.addLayout(form)
        layout.addLayout(buttons)
        return card

    def _tree_card(self):
        card = self.card()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 16, 18, 16)
        title = QLabel("ساختار درختی نقاط")
        title.setObjectName("sectionTitle")
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["شماره", "عنوان", "نوع"])
        self.tree.itemSelectionChanged.connect(self.on_tree_selection_changed)
        layout.addWidget(title)
        layout.addWidget(self.tree)
        return card

    def refresh(self) -> None:
        self._refresh_stats()
        self._refresh_category_combo()
        self._refresh_tree()
        if self.selected_category_id is None:
            self._set_next_category_order()

    def _refresh_stats(self) -> None:
        while self.stats_layout.count():
            item = self.stats_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        counts = self.db.category_location_counts()
        colors = ["#2563EB", "#7C3AED", "#F97316", "#22C55E"]
        for col, title in enumerate(PERMANENT_CATEGORY_TITLES):
            self.stats_layout.addWidget(
                make_stat_card(f"نقاط {title}", str(counts.get(title, 0)), colors[col]),
                0,
                col,
            )

    def _refresh_category_combo(self) -> None:
        current = self.location_category_combo.currentData()
        self.location_category_combo.blockSignals(True)
        self.location_category_combo.clear()
        for category in self.db.list_categories():
            label = f"{category['sort_order']} - {category['title']}"
            self.location_category_combo.addItem(label, category["id"])
        index = self.location_category_combo.findData(current)
        if index >= 0:
            self.location_category_combo.setCurrentIndex(index)
        self.location_category_combo.blockSignals(False)

    def _refresh_tree(self) -> None:
        self.tree.clear()
        categories = self.db.list_categories()
        locations = self.db.list_locations()
        for category in categories:
            category_item = QTreeWidgetItem(
                [str(category["sort_order"]), category["title"], "دسته‌بندی"]
            )
            category_item.setData(
                0,
                Qt.ItemDataRole.UserRole,
                ("category", category["id"], category["is_locked"]),
            )
            self.tree.addTopLevelItem(category_item)

            location_index = 1
            for location in locations:
                if location["category_id"] != category["id"]:
                    continue
                location_item = QTreeWidgetItem(
                    [f"{category['sort_order']}.{location_index}", location["title"], "نقطه"]
                )
                location_item.setData(
                    0,
                    Qt.ItemDataRole.UserRole,
                    ("location", location["id"], category["id"]),
                )
                category_item.addChild(location_item)
                location_index += 1
        self.tree.expandAll()
        for column in range(3):
            self.tree.resizeColumnToContents(column)

    def add_category(self) -> None:
        title = self.category_title_input.text().strip()
        sort_order = self.category_order_input.value()
        if not title:
            show_error(self, "عنوان دسته‌بندی را وارد کنید.")
            return
        try:
            self.db.add_category(title, sort_order)
            show_success(self, "دسته‌بندی ثبت شد.")
            self.clear_category_form()
            self.refresh()
        except DatabaseError as exc:
            show_error(self, f"ثبت دسته‌بندی انجام نشد: {exc}")

    def update_category(self) -> None:
        if self.selected_category_id is None:
            show_error(self, "ابتدا یک دسته‌بندی را انتخاب کنید.")
            return
        category = self.db.get_category(self.selected_category_id)
        if category and int(category.get("is_locked", 0)):
            show_error(self, "دسته‌بندی‌های ثابت قابل ویرایش نیستند.")
            return

        title = self.category_title_input.text().strip()
        sort_order = self.category_order_input.value()
        if not title:
            show_error(self, "عنوان دسته‌بندی را وارد کنید.")
            return
        try:
            self.db.update_category(self.selected_category_id, title, sort_order)
            show_success(self, "دسته‌بندی ویرایش شد.")
            self.clear_category_form()
            self.refresh()
        except DatabaseError as exc:
            show_error(self, f"ویرایش دسته‌بندی انجام نشد: {exc}")

    def delete_category(self) -> None:
        if self.selected_category_id is None:
            show_error(self, "ابتدا یک دسته‌بندی را انتخاب کنید.")
            return
        category = self.db.get_category(self.selected_category_id)
        if category and int(category.get("is_locked", 0)):
            show_error(self, "دسته‌بندی‌های ثابت غیرقابل حذف هستند.")
            return
        if not confirm(self, "با حذف دسته‌بندی، نقاط زیرمجموعه نیز حذف می‌شوند. ادامه می‌دهید؟"):
            return
        try:
            self.db.delete_category(self.selected_category_id)
            show_success(self, "دسته‌بندی حذف شد.")
            self.clear_category_form()
            self.clear_location_form()
            self.refresh()
        except DatabaseError as exc:
            show_error(self, f"حذف دسته‌بندی انجام نشد: {exc}")

    def add_location(self) -> None:
        category_id = self.location_category_combo.currentData()
        title = self.location_title_input.text().strip()
        if category_id is None or not title:
            show_error(self, "دسته‌بندی و عنوان نقطه را وارد کنید.")
            return
        try:
            self.db.add_location(int(category_id), title)
            show_success(self, "نقطه ثبت شد.")
            self.clear_location_form()
            self.refresh()
        except DatabaseError as exc:
            show_error(self, f"ثبت نقطه انجام نشد: {exc}")

    def update_location(self) -> None:
        category_id = self.location_category_combo.currentData()
        title = self.location_title_input.text().strip()
        if self.selected_location_id is None:
            show_error(self, "ابتدا یک نقطه را انتخاب کنید.")
            return
        if category_id is None or not title:
            show_error(self, "دسته‌بندی و عنوان نقطه را وارد کنید.")
            return
        try:
            self.db.update_location(self.selected_location_id, int(category_id), title)
            show_success(self, "نقطه ویرایش شد.")
            self.clear_location_form()
            self.refresh()
        except DatabaseError as exc:
            show_error(self, f"ویرایش نقطه انجام نشد: {exc}")

    def delete_location(self) -> None:
        if self.selected_location_id is None:
            show_error(self, "ابتدا یک نقطه را انتخاب کنید.")
            return
        if not confirm(self, "آیا از حذف نقطه انتخاب‌شده مطمئن هستید؟"):
            return
        try:
            self.db.delete_location(self.selected_location_id)
            show_success(self, "نقطه حذف شد.")
            self.clear_location_form()
            self.refresh()
        except DatabaseError as exc:
            show_error(self, f"حذف نقطه انجام نشد: {exc}")

    def on_tree_selection_changed(self) -> None:
        items = self.tree.selectedItems()
        if not items:
            return
        item = items[0]
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if not data:
            return
        if data[0] == "category":
            self.selected_location_id = None
            self.location_title_input.clear()
            self.selected_category_id = int(data[1])
            self.category_order_input.setValue(int(item.text(0)))
            self.category_title_input.setText(item.text(1))
        elif data[0] == "location":
            self.selected_category_id = None
            self.category_title_input.clear()
            self._set_next_category_order()
            self.selected_location_id = int(data[1])
            category_id = int(data[2])
            self.location_title_input.setText(item.text(1))
            index = self.location_category_combo.findData(category_id)
            if index >= 0:
                self.location_category_combo.setCurrentIndex(index)

    def clear_category_form(self) -> None:
        self.selected_category_id = None
        self.category_title_input.clear()
        self._set_next_category_order()

    def clear_location_form(self) -> None:
        self.selected_location_id = None
        self.location_title_input.clear()

    def _set_next_category_order(self) -> None:
        categories = self.db.list_categories()
        next_order = max([int(item["sort_order"]) for item in categories], default=0) + 1
        self.category_order_input.setValue(next_order)
