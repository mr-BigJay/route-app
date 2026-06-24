from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QFrame,
    QGraphicsBlurEffect,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from database.db import DatabaseError, DatabaseManager
from ui.locations_tree_delegate import LocationsTreeDelegate
from ui.utils import Page, confirm, make_stat_card, show_error, show_success, to_english_digits, to_persian_digits


PERMANENT_CATEGORY_TITLES = ["ستاد", "بیمارستان", "مرکز درمانی", "خانه بهداشت"]

CATEGORY_STAT_LABELS = {
    "ستاد": "ستادها",
    "بیمارستان": "بیمارستان ها",
    "مرکز درمانی": "مراکز درمانی",
    "خانه بهداشت": "خانه های بهداشت",
}


class LocationsPage(Page):
    def __init__(self, db: DatabaseManager) -> None:
        super().__init__("مدیریت نقاط", "مدیریت دسته‌بندی‌ها و نقاط ماموریت")
        self.setObjectName("locationsPage")
        self.db = db
        self.selected_category_id: int | None = None
        self.selected_location_id: int | None = None
        self._tree_icons = self._load_tree_icons()

        self.page_content = QWidget()
        page_content_layout = QVBoxLayout(self.page_content)
        page_content_layout.setContentsMargins(0, 0, 0, 0)
        page_content_layout.setSpacing(16)

        self.stats_layout = QGridLayout()
        self.stats_layout.setSpacing(12)
        page_content_layout.addLayout(self.stats_layout)

        body = QHBoxLayout()
        body.setDirection(QHBoxLayout.Direction.LeftToRight)
        body.setSpacing(16)
        body.addLayout(self._action_buttons_column(), stretch=1)
        body.addWidget(self._tree_card(), stretch=2)
        page_content_layout.addLayout(body, stretch=1)

        self.root_layout.addWidget(self.page_content, stretch=1)
        self._build_category_overlay()
        self._build_location_overlay()
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

    def _action_buttons_column(self) -> QVBoxLayout:
        column = QVBoxLayout()
        column.setSpacing(14)

        category_button = self._page_action_button("ثبت دسته بندی", "category")
        location_button = self._page_action_button("ثبت نقاط", "location")
        category_button.clicked.connect(self.open_category_overlay)
        location_button.clicked.connect(self.open_location_overlay)

        column.addWidget(category_button)
        column.addWidget(location_button)
        column.addStretch(1)
        return column

    def _page_action_button(self, title: str, variant: str) -> QPushButton:
        button = QPushButton(title)
        button.setObjectName("locationPageButton")
        button.setProperty("variant", variant)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setMinimumHeight(92)
        return button

    def _load_tree_icons(self) -> dict[str, QIcon]:
        icons_dir = Path(__file__).resolve().parent.parent / "assets" / "icons"
        return {
            "chevron_down": QIcon(str(icons_dir / "chevron-down.svg")),
            "chevron_left": QIcon(str(icons_dir / "chevron-left.svg")),
            "folder": QIcon(str(icons_dir / "tree-folder.svg")),
            "pin": QIcon(str(icons_dir / "tree-pin.svg")),
        }

    def _tree_card(self) -> QFrame:
        card = self.card()
        card.setObjectName("locationsTreeCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QFrame()
        header.setObjectName("locationsTreeHeader")
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(18, 16, 18, 14)
        header_layout.setSpacing(4)
        title = QLabel("ساختار درختی نقاط")
        title.setObjectName("locationsTreeTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle = QLabel("دسته‌بندی‌ها و نقاط ثبت‌شده را مشاهده و مدیریت کنید")
        subtitle.setObjectName("locationsTreeSubtitle")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_layout.addWidget(title, alignment=Qt.AlignmentFlag.AlignHCenter)
        header_layout.addWidget(subtitle, alignment=Qt.AlignmentFlag.AlignHCenter)

        tree_wrap = QFrame()
        tree_wrap.setObjectName("locationsTreeWrap")
        tree_layout = QVBoxLayout(tree_wrap)
        tree_layout.setContentsMargins(14, 14, 14, 14)
        tree_layout.setSpacing(0)

        self.tree = QTreeWidget()
        self.tree.setObjectName("locationsTree")
        self.tree.setColumnCount(1)
        self.tree.setHeaderHidden(True)
        self.tree.setRootIsDecorated(False)
        self.tree.setIndentation(28)
        self.tree.setUniformRowHeights(False)
        self.tree.setAnimated(True)
        self.tree.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.tree.setItemDelegate(LocationsTreeDelegate(self.tree, self._tree_icons, self.tree))
        self.tree.itemSelectionChanged.connect(self.on_tree_selection_changed)
        self.tree.itemClicked.connect(self._on_tree_item_clicked)
        self.tree.itemExpanded.connect(self._on_category_toggle)
        self.tree.itemCollapsed.connect(self._on_category_toggle)
        tree_layout.addWidget(self.tree)

        layout.addWidget(header)
        layout.addWidget(tree_wrap, stretch=1)
        return card

    def _build_category_overlay(self) -> None:
        self.category_overlay = QFrame(self)
        self.category_overlay.setObjectName("formOverlay")
        self.category_overlay.hide()

        overlay_layout = QVBoxLayout(self.category_overlay)
        overlay_layout.setContentsMargins(24, 24, 24, 24)
        overlay_layout.addStretch(1)

        card = QFrame()
        card.setObjectName("formModalCard")
        card.setFixedWidth(460)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(24, 22, 24, 22)
        card_layout.setSpacing(14)

        title = QLabel("ثبت دسته بندی")
        title.setObjectName("formModalTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        self.category_order_input = QSpinBox()
        self.category_order_input.setRange(1, 999)
        self.category_title_input = QLineEdit()
        self.category_title_input.setPlaceholderText("مثال: اورژانس")
        self.category_title_input.setAlignment(Qt.AlignmentFlag.AlignRight)
        form.addRow("شماره ترتیب *", self.category_order_input)
        form.addRow("عنوان *", self.category_title_input)

        buttons = QHBoxLayout()
        buttons.setSpacing(10)
        add_button = self.action_button("ثبت")
        update_button = self.action_button("ویرایش", "secondary")
        delete_button = self.action_button("حذف", "danger")
        back_button = self.action_button("بازگشت", "ghost")
        add_button.clicked.connect(self.add_category)
        update_button.clicked.connect(self.update_category)
        delete_button.clicked.connect(self.delete_category)
        back_button.clicked.connect(self.close_category_overlay)
        buttons.addStretch(1)
        buttons.addWidget(add_button)
        buttons.addWidget(update_button)
        buttons.addWidget(delete_button)
        buttons.addWidget(back_button)
        buttons.addStretch(1)

        card_layout.addWidget(title)
        card_layout.addLayout(form)
        card_layout.addLayout(buttons)
        overlay_layout.addWidget(card, alignment=Qt.AlignmentFlag.AlignCenter)
        overlay_layout.addStretch(1)

    def _build_location_overlay(self) -> None:
        self.location_overlay = QFrame(self)
        self.location_overlay.setObjectName("formOverlay")
        self.location_overlay.hide()

        overlay_layout = QVBoxLayout(self.location_overlay)
        overlay_layout.setContentsMargins(24, 24, 24, 24)
        overlay_layout.addStretch(1)

        card = QFrame()
        card.setObjectName("formModalCard")
        card.setFixedWidth(460)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(24, 22, 24, 22)
        card_layout.setSpacing(14)

        title = QLabel("ثبت نقاط")
        title.setObjectName("formModalTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        self.location_category_combo = QComboBox()
        self.location_category_combo.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.location_title_input = QLineEdit()
        self.location_title_input.setPlaceholderText("مثال: مرکز کلاچای")
        self.location_title_input.setAlignment(Qt.AlignmentFlag.AlignRight)
        form.addRow("دسته‌بندی *", self.location_category_combo)
        form.addRow("عنوان نقطه *", self.location_title_input)

        buttons = QHBoxLayout()
        buttons.setSpacing(10)
        add_button = self.action_button("ثبت")
        update_button = self.action_button("ویرایش", "secondary")
        delete_button = self.action_button("حذف", "danger")
        back_button = self.action_button("بازگشت", "ghost")
        add_button.clicked.connect(self.add_location)
        update_button.clicked.connect(self.update_location)
        delete_button.clicked.connect(self.delete_location)
        back_button.clicked.connect(self.close_location_overlay)
        buttons.addStretch(1)
        buttons.addWidget(add_button)
        buttons.addWidget(update_button)
        buttons.addWidget(delete_button)
        buttons.addWidget(back_button)
        buttons.addStretch(1)

        card_layout.addWidget(title)
        card_layout.addLayout(form)
        card_layout.addLayout(buttons)
        overlay_layout.addWidget(card, alignment=Qt.AlignmentFlag.AlignCenter)
        overlay_layout.addStretch(1)

    def open_category_overlay(self) -> None:
        self._refresh_category_combo()
        if self.selected_category_id is None:
            self.clear_category_form()
        else:
            self._populate_category_form_from_selection()
        self._show_overlay(self.category_overlay)

    def open_location_overlay(self) -> None:
        self._refresh_category_combo()
        if self.selected_location_id is None:
            self.clear_location_form()
        else:
            self._populate_location_form_from_selection()
        self._show_overlay(self.location_overlay)

    def close_category_overlay(self) -> None:
        self._hide_overlay(self.category_overlay)

    def close_location_overlay(self) -> None:
        self._hide_overlay(self.location_overlay)

    def _show_overlay(self, overlay: QFrame) -> None:
        blur = QGraphicsBlurEffect(self.page_content)
        blur.setBlurRadius(8)
        self.page_content.setGraphicsEffect(blur)
        overlay.setGeometry(self.rect())
        overlay.raise_()
        overlay.show()

    def _hide_overlay(self, overlay: QFrame) -> None:
        self.page_content.setGraphicsEffect(None)
        overlay.hide()

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
            label = CATEGORY_STAT_LABELS.get(title, title)
            self.stats_layout.addWidget(
                make_stat_card(label, str(counts.get(title, 0)), colors[col]),
                0,
                col,
            )

    def _refresh_category_combo(self) -> None:
        current = self.location_category_combo.currentData()
        self.location_category_combo.blockSignals(True)
        self.location_category_combo.clear()
        for category in self.db.list_categories():
            combo_label = f"{to_persian_digits(category['sort_order'])} - {category['title']}"
            self.location_category_combo.addItem(combo_label, category["id"])
        index = self.location_category_combo.findData(current)
        if index >= 0:
            self.location_category_combo.setCurrentIndex(index)
        self.location_category_combo.blockSignals(False)

    def _refresh_tree(self) -> None:
        self.tree.blockSignals(True)
        self.tree.clear()
        categories = self.db.list_categories()
        locations = self.db.list_locations()
        for category in categories:
            category_locations = [
                location for location in locations if location["category_id"] == category["id"]
            ]
            category_item = QTreeWidgetItem([""])
            category_item.setData(
                0,
                Qt.ItemDataRole.UserRole,
                ("category", category["id"], category["is_locked"], category["title"]),
            )
            self.tree.addTopLevelItem(category_item)

            for location in category_locations:
                location_item = QTreeWidgetItem([""])
                location_item.setData(
                    0,
                    Qt.ItemDataRole.UserRole,
                    ("location", location["id"], category["id"], location["title"]),
                )
                category_item.addChild(location_item)

            category_item.setExpanded(False)
        self.tree.blockSignals(False)

    def _on_tree_item_clicked(self, item: QTreeWidgetItem, _column: int) -> None:
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if data and data[0] == "category" and item.childCount() > 0:
            item.setExpanded(not item.isExpanded())

    def _on_category_toggle(self, _item: QTreeWidgetItem) -> None:
        self.tree.viewport().update()

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
            self.close_category_overlay()
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
            self.close_category_overlay()
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
            self.close_category_overlay()
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
            self.close_location_overlay()
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
            self.close_location_overlay()
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
            self.close_location_overlay()
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
            self.selected_category_id = int(data[1])
        elif data[0] == "location":
            self.selected_category_id = None
            self.selected_location_id = int(data[1])

    def _populate_category_form_from_selection(self) -> None:
        if self.selected_category_id is None:
            return
        category = self.db.get_category(self.selected_category_id)
        if not category:
            return
        self.category_order_input.setValue(int(category["sort_order"]))
        self.category_title_input.setText(category["title"])

    def _populate_location_form_from_selection(self) -> None:
        if self.selected_location_id is None:
            return
        items = self.tree.selectedItems()
        if not items:
            return
        data = items[0].data(0, Qt.ItemDataRole.UserRole)
        if not data or data[0] != "location":
            return
        self.location_title_input.setText(data[3])
        index = self.location_category_combo.findData(int(data[2]))
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

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if hasattr(self, "category_overlay"):
            self.category_overlay.setGeometry(self.rect())
        if hasattr(self, "location_overlay"):
            self.location_overlay.setGeometry(self.rect())
