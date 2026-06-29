from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QFormLayout,
    QFrame,
    QGraphicsBlurEffect,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QTabWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from database.db import DatabaseError, DatabaseManager
from ui.form_widgets import NoWheelComboBox, NoWheelSpinBox
from ui.location_quick_add_widget import LocationQuickAddWidget
from ui.locations_tree_delegate import LocationsTreeDelegate
from ui.utils import Page, confirm, make_stat_card, show_error, show_success, to_persian_digits


PERMANENT_CATEGORY_TITLES = ["ستاد", "بیمارستان", "مرکز درمانی", "خانه بهداشت"]

CATEGORY_STAT_LABELS = {
    "ستاد": "ستادها",
    "بیمارستان": "بیمارستان ها",
    "مرکز درمانی": "مراکز درمانی",
    "خانه بهداشت": "خانه های بهداشت",
}

MODAL_WARNING_TEXT = (
    "توجه: در ویرایش یا حذف موارد دقت کنید. این تغییرات ممکن است بر فرم‌های "
    "در حال استفاده اثر بگذارد. ماموریت‌های ثبت‌شده قبلی با همان متن ذخیره‌شده "
    "باقی می‌مانند و تغییر نمی‌کنند."
)


class LocationsPage(Page):
    def __init__(self, db: DatabaseManager) -> None:
        super().__init__("مدیریت نقاط", "مدیریت دسته‌بندی‌ها و نقاط ماموریت")
        self.setObjectName("locationsPage")
        self.db = db
        self.selected_category_id: int | None = None
        self.selected_location_id: int | None = None
        self._modal_mode = "register"
        self._quick_add_item: QTreeWidgetItem | None = None
        self._quick_add_add_item: QTreeWidgetItem | None = None
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
        self._build_management_overlay()
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

        register_button = self._page_action_button("ثبت", "register")
        edit_button = self._page_action_button("ویرایش", "edit")
        delete_button = self._page_action_button("حذف", "delete")
        register_button.clicked.connect(self.open_register_modal)
        edit_button.clicked.connect(self.open_edit_modal)
        delete_button.clicked.connect(self.open_delete_modal)

        column.addWidget(register_button)
        column.addWidget(edit_button)
        column.addWidget(delete_button)
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
            "chevron_right": QIcon(str(icons_dir / "chevron-right.svg")),
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
        title.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        subtitle = QLabel("دسته‌بندی‌ها و نقاط ثبت‌شده را مشاهده و مدیریت کنید")
        subtitle.setObjectName("locationsTreeSubtitle")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        header_layout.addWidget(title)
        header_layout.addWidget(subtitle)

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
        self.tree.setIndentation(34)
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

    def _build_management_overlay(self) -> None:
        self.management_overlay = QFrame(self)
        self.management_overlay.setObjectName("formOverlay")
        self.management_overlay.hide()

        overlay_layout = QVBoxLayout(self.management_overlay)
        overlay_layout.setContentsMargins(24, 24, 24, 24)
        overlay_layout.addStretch(1)

        card = QFrame()
        card.setObjectName("formModalCard")
        card.setFixedWidth(520)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(24, 22, 24, 22)
        card_layout.setSpacing(14)

        self.modal_title = QLabel("ثبت")
        self.modal_title.setObjectName("formModalTitle")
        self.modal_title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.modal_warning = QLabel(MODAL_WARNING_TEXT)
        self.modal_warning.setObjectName("formModalWarning")
        self.modal_warning.setWordWrap(True)
        self.modal_warning.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.modal_warning.hide()

        self.management_tabs = QTabWidget()
        self.management_tabs.setObjectName("locationsManageTabs")
        self.management_tabs.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.management_tabs.addTab(self._build_category_tab(), "دسته‌بندی‌ها")
        self.management_tabs.addTab(self._build_location_tab(), "نقاط")
        self.management_tabs.currentChanged.connect(self._update_modal_title)

        buttons = QHBoxLayout()
        buttons.setSpacing(10)
        self.modal_primary_button = self.action_button("ثبت")
        back_button = self.action_button("بازگشت", "ghost")
        self.modal_primary_button.clicked.connect(self._on_modal_primary_action)
        back_button.clicked.connect(self.close_management_overlay)
        buttons.addStretch(1)
        buttons.addWidget(self.modal_primary_button)
        buttons.addWidget(back_button)
        buttons.addStretch(1)

        card_layout.addWidget(self.modal_title)
        card_layout.addWidget(self.modal_warning)
        card_layout.addWidget(self.management_tabs)
        card_layout.addLayout(buttons)
        overlay_layout.addWidget(card, alignment=Qt.AlignmentFlag.AlignCenter)
        overlay_layout.addStretch(1)

    def _build_category_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(8, 12, 8, 8)
        layout.setSpacing(12)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        self.category_pick_label = QLabel("انتخاب دسته‌بندی *")
        self.category_pick_combo = NoWheelComboBox()
        self.category_pick_combo.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.category_pick_combo.currentIndexChanged.connect(self._on_category_pick_changed)
        self.category_order_input = NoWheelSpinBox()
        self.category_order_input.setRange(1, 999)
        self.category_title_input = QLineEdit()
        self.category_title_input.setPlaceholderText("مثال: اورژانس")
        self.category_title_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        form.addRow(self.category_pick_label, self.category_pick_combo)
        self.category_order_label = QLabel("شماره ترتیب *")
        form.addRow(self.category_order_label, self.category_order_input)
        self.category_title_label = QLabel("عنوان *")
        form.addRow(self.category_title_label, self.category_title_input)
        layout.addLayout(form)
        layout.addStretch(1)
        return tab

    def _build_location_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(8, 12, 8, 8)
        layout.setSpacing(12)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        self.location_pick_label = QLabel("انتخاب نقطه *")
        self.location_pick_combo = NoWheelComboBox()
        self.location_pick_combo.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.location_pick_combo.currentIndexChanged.connect(self._on_location_pick_changed)
        self.location_category_label = QLabel("انتخاب دسته‌بندی *")
        self.location_category_combo = NoWheelComboBox()
        self.location_category_combo.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.location_category_combo.currentIndexChanged.connect(self._on_location_category_changed)
        self.location_title_label = QLabel("عنوان نقطه *")
        self.location_title_input = QLineEdit()
        self.location_title_input.setPlaceholderText("مثال: مرکز کلاچای")
        self.location_title_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        form.addRow(self.location_category_label, self.location_category_combo)
        form.addRow(self.location_pick_label, self.location_pick_combo)
        form.addRow(self.location_title_label, self.location_title_input)
        layout.addLayout(form)
        layout.addStretch(1)
        return tab

    def open_register_modal(self) -> None:
        self._modal_mode = "register"
        preset_category_id: int | None = None
        items = self.tree.selectedItems()
        if items:
            data = items[0].data(0, Qt.ItemDataRole.UserRole)
            if data and data[0] == "location":
                preset_category_id = int(data[2])
            elif data and data[0] == "category":
                preset_category_id = int(data[1])

        self.clear_category_form()
        self.clear_location_form()
        if preset_category_id is not None:
            self.management_tabs.setCurrentIndex(1)
            self._preset_location_category(preset_category_id)
        else:
            self.management_tabs.setCurrentIndex(0)
        self._apply_modal_mode()
        self._show_overlay(self.management_overlay)

    def open_edit_modal(self) -> None:
        self._modal_mode = "edit"
        self._prepare_management_modal_from_tree()
        self._apply_modal_mode()
        self._show_overlay(self.management_overlay)

    def open_delete_modal(self) -> None:
        self._modal_mode = "delete"
        self._prepare_management_modal_from_tree()
        self._apply_modal_mode()
        self._show_overlay(self.management_overlay)

    def _prepare_management_modal_from_tree(self) -> None:
        preset_category_id = self.selected_category_id
        preset_location_id = self.selected_location_id
        items = self.tree.selectedItems()
        if items:
            data = items[0].data(0, Qt.ItemDataRole.UserRole)
            if data and data[0] == "location":
                preset_location_id = int(data[1])
                preset_category_id = None
            elif data and data[0] == "category":
                preset_category_id = int(data[1])
                preset_location_id = None

        self._refresh_management_combos()
        self.clear_category_form()
        self.clear_location_form()

        if preset_location_id is not None:
            self.management_tabs.setCurrentIndex(1)
            location = self._get_location_by_id(preset_location_id)
            if location is not None:
                category_index = self.location_category_combo.findData(int(location["category_id"]))
                if category_index >= 0:
                    self.location_category_combo.setCurrentIndex(category_index)
            self._refresh_location_pick_combo()
            index = self.location_pick_combo.findData(preset_location_id)
            if index >= 0:
                self.location_pick_combo.setCurrentIndex(index)
        elif preset_category_id is not None:
            index = self.category_pick_combo.findData(preset_category_id)
            if index >= 0:
                self.management_tabs.setCurrentIndex(0)
                self.category_pick_combo.setCurrentIndex(index)
            elif self._modal_mode in ("edit", "delete"):
                self._open_locations_tab_for_management(preset_category_id)
            else:
                self.management_tabs.setCurrentIndex(0)
        else:
            if self._modal_mode in ("edit", "delete") and self.category_pick_combo.count() == 0:
                self._open_locations_tab_for_management()
            else:
                self.management_tabs.setCurrentIndex(0)
                if self.category_pick_combo.count():
                    self.category_pick_combo.setCurrentIndex(0)
                if self.location_pick_combo.count():
                    self.location_pick_combo.setCurrentIndex(0)

    def _open_locations_tab_for_management(self, category_id: int | None = None) -> None:
        self.management_tabs.setCurrentIndex(1)
        if category_id is not None:
            category_index = self.location_category_combo.findData(category_id)
            if category_index >= 0:
                self.location_category_combo.setCurrentIndex(category_index)
        elif self.location_category_combo.count():
            self.location_category_combo.setCurrentIndex(0)
        self._refresh_location_pick_combo()
        if self.location_pick_combo.count():
            self.location_pick_combo.setCurrentIndex(0)

    def _open_register_modal_for_category(self, category_id: int) -> None:
        self._modal_mode = "register"
        self.clear_category_form()
        self.clear_location_form()
        self.management_tabs.setCurrentIndex(1)
        self._preset_location_category(category_id)
        self._apply_modal_mode()
        self._show_overlay(self.management_overlay)

    def close_management_overlay(self) -> None:
        self._hide_overlay(self.management_overlay)

    def _apply_modal_mode(self) -> None:
        is_register = self._modal_mode == "register"
        is_edit = self._modal_mode == "edit"
        is_delete = self._modal_mode == "delete"
        self.modal_warning.setVisible(is_edit or is_delete)
        self._update_modal_title()

        self.category_pick_label.setVisible(is_edit or is_delete)
        self.category_pick_combo.setVisible(is_edit or is_delete)
        self.category_order_label.setVisible(is_register or is_edit)
        self.category_order_input.setVisible(is_register or is_edit)
        self.category_title_label.setVisible(is_register or is_edit)
        self.category_title_input.setVisible(is_register or is_edit)

        self.location_category_label.setVisible(True)
        self.location_category_combo.setVisible(True)
        self.location_pick_label.setVisible(is_edit or is_delete)
        self.location_pick_combo.setVisible(is_edit or is_delete)
        self.location_title_label.setVisible(is_register or is_edit)
        self.location_title_input.setVisible(is_register or is_edit)

        if is_delete:
            self.location_category_label.setText("انتخاب دسته‌بندی *")
            self.category_title_label.setText("عنوان *")
            self.location_title_label.setText("عنوان نقطه *")
            self.category_title_input.setPlaceholderText("مثال: اورژانس")
            self.location_title_input.setPlaceholderText("مثال: مرکز کلاچای")
        elif is_edit:
            self.location_category_label.setText("انتخاب دسته‌بندی *")
            self.category_title_label.setText("عنوان جدید *")
            self.location_title_label.setText("عنوان جدید *")
            self.category_title_input.setPlaceholderText("عنوان جدید دسته‌بندی")
            self.location_title_input.setPlaceholderText("عنوان جدید نقطه")
        elif is_register:
            self.location_category_label.setText("دسته‌بندی *")
            self.category_title_label.setText("عنوان *")
            self.location_title_label.setText("عنوان نقطه *")
            self.category_title_input.setPlaceholderText("مثال: اورژانس")
            self.location_title_input.setPlaceholderText("مثال: مرکز کلاچای")

        if self._modal_mode == "register":
            self.modal_primary_button.setText("ثبت")
            self.modal_primary_button.setProperty("role", "primary")
        elif self._modal_mode == "edit":
            self.modal_primary_button.setText("ذخیره ویرایش")
            self.modal_primary_button.setProperty("role", "secondary")
        else:
            self.modal_primary_button.setText("حذف")
            self.modal_primary_button.setProperty("role", "danger")

        read_only = is_delete
        self.category_pick_combo.setEnabled(is_edit or is_delete)
        self.location_pick_combo.setEnabled(is_edit or is_delete)
        self.category_order_input.setReadOnly(read_only)
        self.category_title_input.setReadOnly(read_only)
        self.location_category_combo.setEnabled(not read_only or is_delete)
        self.location_title_input.setReadOnly(read_only)

        self.modal_primary_button.style().unpolish(self.modal_primary_button)
        self.modal_primary_button.style().polish(self.modal_primary_button)

    def _update_modal_title(self) -> None:
        is_category_tab = self.management_tabs.currentIndex() == 0
        titles = {
            ("register", True): "ثبت دسته‌بندی",
            ("register", False): "ثبت نقطه",
            ("edit", True): "ویرایش دسته‌بندی",
            ("edit", False): "ویرایش نقطه",
            ("delete", True): "حذف دسته‌بندی",
            ("delete", False): "حذف نقطه",
        }
        self.modal_title.setText(titles[(self._modal_mode, is_category_tab)])

    def _on_modal_primary_action(self) -> None:
        is_category_tab = self.management_tabs.currentIndex() == 0
        if self._modal_mode == "register":
            if is_category_tab:
                self.add_category()
            else:
                self.add_location()
        elif self._modal_mode == "edit":
            if is_category_tab:
                self.update_category()
            else:
                self.update_location()
        else:
            if is_category_tab:
                self.delete_category()
            else:
                self.delete_location()

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
        self._refresh_management_combos()
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

    def _refresh_management_combos(self) -> None:
        self._refresh_category_pick_combo()
        self._refresh_location_pick_combo()
        if self._modal_mode == "edit":
            self._on_category_pick_changed()
            self._on_location_pick_changed()

    def _refresh_category_pick_combo(self) -> None:
        current_category = self.category_pick_combo.currentData()
        self.category_pick_combo.blockSignals(True)
        self.category_pick_combo.clear()
        categories = self.db.list_categories()
        if self._modal_mode in ("delete", "edit"):
            categories = [category for category in categories if not int(category.get("is_locked", 0))]
        for category in categories:
            label = f"{to_persian_digits(category['sort_order'])} - {category['title']}"
            self.category_pick_combo.addItem(label, category["id"])
        category_index = self.category_pick_combo.findData(current_category)
        if category_index >= 0:
            self.category_pick_combo.setCurrentIndex(category_index)
        elif self.category_pick_combo.count():
            self.category_pick_combo.setCurrentIndex(0)
        self.category_pick_combo.blockSignals(False)

    def _refresh_location_pick_combo(self) -> None:
        current_location = self.location_pick_combo.currentData()
        self.location_pick_combo.blockSignals(True)
        self.location_pick_combo.clear()
        locations = self.db.list_locations()
        if self._modal_mode in ("delete", "edit"):
            category_id = self.location_category_combo.currentData()
            if category_id is not None:
                locations = [
                    location
                    for location in locations
                    if int(location["category_id"]) == int(category_id)
                ]
                for location in locations:
                    self.location_pick_combo.addItem(location["title"], location["id"])
        location_index = self.location_pick_combo.findData(current_location)
        if location_index >= 0:
            self.location_pick_combo.setCurrentIndex(location_index)
        elif self.location_pick_combo.count():
            self.location_pick_combo.setCurrentIndex(0)
        self.location_pick_combo.blockSignals(False)

    def _refresh_tree(self) -> None:
        self._cancel_quick_add_location()

        expanded_ids: set[int] = set()
        for index in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(index)
            data = item.data(0, Qt.ItemDataRole.UserRole)
            if data and data[0] == "category" and item.isExpanded():
                expanded_ids.add(int(data[1]))

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

            add_item = QTreeWidgetItem([""])
            add_item.setData(
                0,
                Qt.ItemDataRole.UserRole,
                ("add_location", category["id"], category["title"], ""),
            )
            category_item.addChild(add_item)
            category_item.setExpanded(int(category["id"]) in expanded_ids)

        self.tree.blockSignals(False)

    def _on_tree_item_clicked(self, item: QTreeWidgetItem, _column: int) -> None:
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if not data:
            return
        if data[0] == "add_location":
            self._start_quick_add_location(int(data[1]))
            return
        if data[0] == "quick_add_location":
            widget = self.tree.itemWidget(item, 0)
            if isinstance(widget, LocationQuickAddWidget):
                widget.focus_input()
            return
        if data[0] == "category":
            item.setExpanded(not item.isExpanded())

    def _start_quick_add_location(self, category_id: int) -> None:
        self._cancel_quick_add_location()

        category_item: QTreeWidgetItem | None = None
        add_item: QTreeWidgetItem | None = None
        for index in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(index)
            data = item.data(0, Qt.ItemDataRole.UserRole)
            if not data or data[0] != "category" or int(data[1]) != category_id:
                continue
            category_item = item
            for child_index in range(item.childCount()):
                child = item.child(child_index)
                child_data = child.data(0, Qt.ItemDataRole.UserRole)
                if child_data and child_data[0] == "add_location":
                    add_item = child
                    break
            break

        if category_item is None or add_item is None:
            return

        category_data = category_item.data(0, Qt.ItemDataRole.UserRole)
        category_title = str(category_data[3]) if category_data else ""
        sort_order = self.db.next_free_location_sort_order(category_id)

        quick_item = QTreeWidgetItem([""])
        quick_item.setData(
            0,
            Qt.ItemDataRole.UserRole,
            ("quick_add_location", category_id, category_title, sort_order),
        )
        category_item.insertChild(category_item.indexOfChild(add_item), quick_item)
        add_item.setHidden(True)
        self._quick_add_add_item = add_item

        widget = LocationQuickAddWidget(sort_order, self.tree)
        widget.confirmed.connect(
            lambda title, cid=category_id, order=sort_order: self._confirm_quick_add_location(
                cid, title, order
            )
        )
        widget.cancelled.connect(self._cancel_quick_add_location)
        self.tree.setItemWidget(quick_item, 0, widget)
        self._quick_add_item = quick_item
        category_item.setExpanded(True)
        widget.focus_input()

    def _cancel_quick_add_location(self) -> None:
        if self._quick_add_item is None:
            return
        widget = self.tree.itemWidget(self._quick_add_item, 0)
        if widget is not None:
            self.tree.removeItemWidget(self._quick_add_item, 0)
            widget.deleteLater()
        parent = self._quick_add_item.parent()
        if parent is not None:
            parent.removeChild(self._quick_add_item)
        if self._quick_add_add_item is not None:
            self._quick_add_add_item.setHidden(False)
            self._quick_add_add_item = None
        self._quick_add_item = None

    def _confirm_quick_add_location(self, category_id: int, title: str, sort_order: int) -> None:
        try:
            self.db.add_location(category_id, title, sort_order)
            self._quick_add_item = None
            self._quick_add_add_item = None
            self.refresh()
        except DatabaseError as exc:
            show_error(self, f"ثبت نقطه انجام نشد: {exc}")
            if self._quick_add_item is not None:
                widget = self.tree.itemWidget(self._quick_add_item, 0)
                if isinstance(widget, LocationQuickAddWidget):
                    widget.focus_input()

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
            self.close_management_overlay()
            self.refresh()
        except DatabaseError as exc:
            show_error(self, f"ثبت دسته‌بندی انجام نشد: {exc}")

    def update_category(self) -> None:
        category_id = self.category_pick_combo.currentData()
        if category_id is None:
            show_error(self, "دسته‌بندی مورد نظر را از منو انتخاب کنید.")
            return
        category = self.db.get_category(int(category_id))
        if not category:
            show_error(self, "دسته‌بندی انتخاب‌شده یافت نشد.")
            return
        if int(category.get("is_locked", 0)):
            show_error(self, "دسته‌بندی‌های پیش‌فرض (ستاد، بیمارستان، مرکز درمانی، خانه بهداشت) قابل ویرایش نیستند.")
            return

        new_title = self.category_title_input.text().strip()
        sort_order = self.category_order_input.value()
        if not new_title:
            show_error(self, "عنوان جدید دسته‌بندی را وارد کنید.")
            return
        old_title = category["title"]
        if not confirm(
            self,
            f"آیا از ویرایش دسته‌بندی «{old_title}» به «{new_title}» مطمئن هستید؟ "
            "با تغییر دسته‌بندی، دسته‌بندی تمام نقاط زیرمجموعه نیز تغییر می‌کند و "
            "ممکن است بر فرم‌های نرم‌افزار اثر بگذارد.",
        ):
            return
        try:
            self.db.update_category(int(category_id), new_title, sort_order)
            show_success(self, "دسته‌بندی ویرایش شد.")
            self.clear_category_form()
            self.close_management_overlay()
            self.refresh()
        except DatabaseError as exc:
            show_error(self, f"ویرایش دسته‌بندی انجام نشد: {exc}")

    def delete_category(self) -> None:
        category_id = self.category_pick_combo.currentData()
        if category_id is None:
            show_error(self, "دسته‌بندی مورد نظر را از منو انتخاب کنید.")
            return
        category = self.db.get_category(int(category_id))
        if not category:
            show_error(self, "دسته‌بندی انتخاب‌شده یافت نشد.")
            return
        if int(category.get("is_locked", 0)):
            show_error(self, "دسته‌بندی‌های پیش‌فرض (ستاد، بیمارستان، مرکز درمانی، خانه بهداشت) قابل حذف نیستند.")
            return
        category_title = category["title"]
        if not confirm(
            self,
            f"آیا از حذف دسته‌بندی «{category_title}» مطمئن هستید؟ با حذف این مورد، تمام نقاط زیرمجموعه آن نیز حذف می‌شوند.",
        ):
            return
        try:
            self.db.delete_category(int(category_id))
            show_success(self, "دسته‌بندی حذف شد.")
            self.clear_category_form()
            self.clear_location_form()
            self.close_management_overlay()
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
            self.close_management_overlay()
            self.refresh()
        except DatabaseError as exc:
            show_error(self, f"ثبت نقطه انجام نشد: {exc}")

    def update_location(self) -> None:
        category_id = self.location_category_combo.currentData()
        location_id = self.location_pick_combo.currentData()
        new_title = self.location_title_input.text().strip()
        if category_id is None:
            show_error(self, "دسته‌بندی مورد نظر را از منو انتخاب کنید.")
            return
        if location_id is None:
            show_error(self, "نقطه مورد نظر را از منو انتخاب کنید.")
            return
        if not new_title:
            show_error(self, "عنوان جدید نقطه را وارد کنید.")
            return
        location = self._get_location_by_id(int(location_id))
        if not location:
            show_error(self, "نقطه انتخاب‌شده یافت نشد.")
            return
        old_title = location["title"]
        if not confirm(self, f"آیا از ویرایش نقطه «{old_title}» به «{new_title}» مطمئن هستید؟"):
            return
        try:
            self.db.update_location(int(location_id), int(category_id), new_title)
            show_success(self, "نقطه ویرایش شد.")
            self.clear_location_form()
            self.close_management_overlay()
            self.refresh()
        except DatabaseError as exc:
            show_error(self, f"ویرایش نقطه انجام نشد: {exc}")

    def delete_location(self) -> None:
        category_id = self.location_category_combo.currentData()
        location_id = self.location_pick_combo.currentData()
        if category_id is None:
            show_error(self, "دسته‌بندی مورد نظر را از منو انتخاب کنید.")
            return
        if location_id is None:
            show_error(self, "نقطه مورد نظر را از منو انتخاب کنید.")
            return
        location_title = self.location_pick_combo.currentText().strip()
        if not confirm(self, f"آیا از حذف نقطه «{location_title}» مطمئن هستید؟"):
            return
        try:
            self.db.delete_location(int(location_id))
            show_success(self, "نقطه حذف شد.")
            self.clear_location_form()
            self.close_management_overlay()
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
        if data[0] == "add_location" or data[0] == "quick_add_location":
            return
        if data[0] == "category":
            self.selected_location_id = None
            self.selected_category_id = int(data[1])
        elif data[0] == "location":
            self.selected_category_id = None
            self.selected_location_id = int(data[1])

    def _on_location_category_changed(self) -> None:
        if self._modal_mode in ("delete", "edit"):
            self._refresh_location_pick_combo()
            if self._modal_mode == "edit":
                self._on_location_pick_changed()

    def _on_category_pick_changed(self) -> None:
        if self._modal_mode != "edit":
            return
        category_id = self.category_pick_combo.currentData()
        if category_id is None:
            return
        category = self.db.get_category(int(category_id))
        if not category:
            return
        self.category_order_input.setValue(int(category["sort_order"]))
        self.category_title_input.setText(category["title"])

    def _on_location_pick_changed(self) -> None:
        if self._modal_mode != "edit":
            return
        location_id = self.location_pick_combo.currentData()
        if location_id is None:
            return
        location = self._get_location_by_id(int(location_id))
        if not location:
            return
        self.location_title_input.setText(location["title"])
        index = self.location_category_combo.findData(int(location["category_id"]))
        if index >= 0:
            self.location_category_combo.setCurrentIndex(index)

    def _get_location_by_id(self, location_id: int) -> dict | None:
        for location in self.db.list_locations():
            if int(location["id"]) == int(location_id):
                return location
        return None

    def _preset_location_category(self, category_id: int) -> None:
        index = self.location_category_combo.findData(category_id)
        if index >= 0:
            self.location_category_combo.setCurrentIndex(index)

    def clear_category_form(self) -> None:
        self.category_title_input.clear()
        self._set_next_category_order()

    def clear_location_form(self) -> None:
        self.location_title_input.clear()

    def _set_next_category_order(self) -> None:
        categories = self.db.list_categories()
        next_order = max([int(item["sort_order"]) for item in categories], default=0) + 1
        self.category_order_input.setValue(next_order)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if hasattr(self, "management_overlay"):
            self.management_overlay.setGeometry(self.rect())
