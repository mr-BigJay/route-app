from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from database.db import ROLE_SUPER_ADMIN, ROLE_USER, DatabaseError, DatabaseManager
from ui.form_widgets import NoWheelComboBox, configure_combo_field, configure_line_edit_field
from ui.utils import Page, confirm, show_error, show_success, to_persian_digits


class UsersPage(Page):
    def __init__(self, db: DatabaseManager, current_user: dict) -> None:
        super().__init__("مدیریت کاربران", "تعریف و مدیریت کاربران سیستم")
        self.setObjectName("usersPage")
        self.db = db
        self.current_user = current_user
        self.editing_user_id: int | None = None

        self.root_layout.addWidget(self._users_table_card(), stretch=1)
        self.root_layout.addWidget(self._form_card())
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

    def _users_table_card(self) -> QWidget:
        card = self.card()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)
        title = QLabel("لیست کاربران سیستم")
        title.setObjectName("sectionTitle")
        self.table = QTableWidget(0, 5)
        self.table.setObjectName("missionsTable")
        self.table.setHorizontalHeaderLabels(["ردیف", "نام کاربری", "نام نمایشی", "نقش", "وضعیت"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.itemSelectionChanged.connect(self._on_row_selected)
        layout.addWidget(title)
        layout.addWidget(self.table, stretch=1)
        return card

    def _form_card(self) -> QWidget:
        card = self.card()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)
        self.form_title = QLabel("ثبت کاربر جدید")
        self.form_title.setObjectName("sectionTitle")

        form = QFormLayout()
        form.setSpacing(10)
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("مثال: operator1")
        configure_line_edit_field(self.username_input)
        self.full_name_input = QLineEdit()
        self.full_name_input.setPlaceholderText("مثال: علی محمدی")
        configure_line_edit_field(self.full_name_input)
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.setPlaceholderText("حداقل ۶ کاراکتر")
        configure_line_edit_field(self.password_input)
        self.role_combo = NoWheelComboBox()
        configure_combo_field(self.role_combo)
        self.role_combo.addItem("کاربر سیستم", ROLE_USER)
        self.role_combo.addItem("سوپر ادمین", ROLE_SUPER_ADMIN)
        self.active_checkbox = QCheckBox("کاربر فعال")
        self.active_checkbox.setChecked(True)

        form.addRow("نام کاربری *", self.username_input)
        form.addRow("نام نمایشی", self.full_name_input)
        form.addRow("رمز عبور *", self.password_input)
        form.addRow("نقش", self.role_combo)
        form.addRow("", self.active_checkbox)

        buttons = QHBoxLayout()
        buttons.setSpacing(8)
        self.save_button = self.action_button("ثبت کاربر")
        self.save_button.clicked.connect(self.save_user)
        update_button = self.action_button("ویرایش", "secondary")
        update_button.clicked.connect(self.save_user)
        delete_button = self.action_button("حذف", "danger")
        delete_button.clicked.connect(self.delete_user)
        clear_button = self.action_button("پاک‌سازی فرم", "ghost")
        clear_button.clicked.connect(self.clear_form)
        buttons.addWidget(self.save_button)
        buttons.addWidget(update_button)
        buttons.addWidget(delete_button)
        buttons.addWidget(clear_button)

        layout.addWidget(self.form_title)
        layout.addLayout(form)
        layout.addLayout(buttons)
        return card

    def refresh(self) -> None:
        users = self.db.list_users()
        self.table.setRowCount(len(users))
        for row_index, user in enumerate(users):
            role_label = "سوپر ادمین" if user["role"] == ROLE_SUPER_ADMIN else "کاربر سیستم"
            status_label = "فعال" if int(user["is_active"]) else "غیرفعال"
            values = [
                to_persian_digits(row_index + 1),
                user["username"],
                user["full_name"] or "—",
                role_label,
                status_label,
            ]
            for col_index, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                item.setData(Qt.ItemDataRole.UserRole, int(user["id"]))
                self.table.setItem(row_index, col_index, item)

    def _on_row_selected(self) -> None:
        row = self.table.currentRow()
        if row < 0:
            return
        user_id_item = self.table.item(row, 0)
        if user_id_item is None:
            return
        user_id = user_id_item.data(Qt.ItemDataRole.UserRole)
        user = self.db.get_user(int(user_id))
        if not user:
            return
        self.editing_user_id = int(user["id"])
        self.form_title.setText("ویرایش کاربر")
        self.save_button.setText("ذخیره تغییرات")
        self.username_input.setText(user["username"])
        self.username_input.setReadOnly(True)
        self.full_name_input.setText(user["full_name"] or "")
        self.password_input.clear()
        self.password_input.setPlaceholderText("برای تغییر رمز، مقدار جدید وارد کنید")
        role_index = self.role_combo.findData(user["role"])
        if role_index >= 0:
            self.role_combo.setCurrentIndex(role_index)
        self.active_checkbox.setChecked(bool(int(user["is_active"])))

    def clear_form(self) -> None:
        self.editing_user_id = None
        self.form_title.setText("ثبت کاربر جدید")
        self.save_button.setText("ثبت کاربر")
        self.username_input.clear()
        self.username_input.setReadOnly(False)
        self.full_name_input.clear()
        self.password_input.clear()
        self.password_input.setPlaceholderText("حداقل ۶ کاراکتر")
        self.role_combo.setCurrentIndex(0)
        self.active_checkbox.setChecked(True)
        self.table.clearSelection()

    def save_user(self) -> None:
        username = self.username_input.text().strip()
        full_name = self.full_name_input.text().strip()
        password = self.password_input.text()
        role = self.role_combo.currentData()
        is_active = self.active_checkbox.isChecked()
        try:
            if self.editing_user_id is None:
                if not username:
                    show_error(self, "نام کاربری الزامی است.")
                    return
                if not password:
                    show_error(self, "رمز عبور الزامی است.")
                    return
                self.db.add_user(username, password, full_name, str(role))
                show_success(self, "کاربر جدید ثبت شد.")
            else:
                self.db.update_user(
                    self.editing_user_id,
                    full_name=full_name,
                    role=str(role),
                    is_active=is_active,
                    password=password or None,
                )
                show_success(self, "اطلاعات کاربر به‌روزرسانی شد.")
        except DatabaseError as exc:
            show_error(self, str(exc))
            return
        self.clear_form()
        self.refresh()

    def delete_user(self) -> None:
        if self.editing_user_id is None:
            show_error(self, "ابتدا یک کاربر را از جدول انتخاب کنید.")
            return
        if self.editing_user_id == int(self.current_user["id"]):
            show_error(self, "نمی‌توانید حساب کاربری فعال خود را حذف کنید.")
            return
        if not confirm(self, "آیا از حذف این کاربر اطمینان دارید؟"):
            return
        try:
            self.db.delete_user(self.editing_user_id)
        except DatabaseError as exc:
            show_error(self, str(exc))
            return
        show_success(self, "کاربر حذف شد.")
        self.clear_form()
        self.refresh()
