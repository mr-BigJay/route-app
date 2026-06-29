from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)

from database.db import DatabaseManager
from ui.form_widgets import configure_line_edit_field
from ui.utils import show_error


class LoginDialog(QDialog):
    def __init__(self, db: DatabaseManager, parent=None) -> None:
        super().__init__(parent)
        self.db = db
        self.user: dict | None = None
        self.setWindowTitle("ورود به Route")
        self.setModal(True)
        self.setFixedSize(420, 360)
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.setObjectName("loginDialog")
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        card = QFrame()
        card.setObjectName("loginCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(24, 24, 24, 24)
        card_layout.setSpacing(14)

        title = QLabel("ورود به سیستم")
        title.setObjectName("loginTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle = QLabel("Route v.1 — مدیریت ماموریت خودروها")
        subtitle.setObjectName("loginSubtitle")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.username_input = QLineEdit()
        self.username_input.setObjectName("loginInput")
        self.username_input.setPlaceholderText("نام کاربری")
        configure_line_edit_field(self.username_input)

        self.password_input = QLineEdit()
        self.password_input.setObjectName("loginInput")
        self.password_input.setPlaceholderText("رمز عبور")
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        configure_line_edit_field(self.password_input)
        self.password_input.returnPressed.connect(self._login)

        login_button = QPushButton("ورود")
        login_button.setObjectName("loginButton")
        login_button.setCursor(Qt.CursorShape.PointingHandCursor)
        login_button.clicked.connect(self._login)
        self.username_input.returnPressed.connect(self._login)

        card_layout.addWidget(title)
        card_layout.addWidget(subtitle)
        card_layout.addSpacing(8)
        card_layout.addWidget(self._field("نام کاربری", self.username_input))
        card_layout.addWidget(self._field("رمز عبور", self.password_input))
        card_layout.addSpacing(8)
        card_layout.addWidget(login_button)
        layout.addStretch(1)
        layout.addWidget(card)
        layout.addStretch(1)

    def _field(self, label: str, widget: QLineEdit) -> QFrame:
        box = QFrame()
        box.setObjectName("loginFieldBox")
        field_layout = QVBoxLayout(box)
        field_layout.setContentsMargins(0, 0, 0, 0)
        field_layout.setSpacing(6)
        label_widget = QLabel(label)
        label_widget.setObjectName("fieldLabel")
        label_widget.setAlignment(Qt.AlignmentFlag.AlignRight)
        field_layout.addWidget(label_widget)
        field_layout.addWidget(widget)
        return box

    def _login(self) -> None:
        username = self.username_input.text().strip()
        password = self.password_input.text()
        if not username or not password:
            show_error(self, "نام کاربری و رمز عبور را وارد کنید.")
            return
        user = self.db.authenticate(username, password)
        if not user:
            show_error(self, "نام کاربری یا رمز عبور اشتباه است.")
            self.password_input.clear()
            self.password_input.setFocus()
            return
        self.user = user
        self.accept()
