from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)

from database.db import DatabaseManager
from ui.form_widgets import configure_line_edit_field
from ui.utils import APP_PRODUCT_NAME, APP_VERSION, show_error, to_persian_digits


class LoginDialog(QDialog):
    def __init__(self, db: DatabaseManager, parent=None) -> None:
        super().__init__(parent)
        self.db = db
        self.user: dict | None = None
        self.setWindowTitle(f"ورود به {APP_PRODUCT_NAME}")
        self.setModal(True)
        self.setFixedSize(860, 500)
        self.setObjectName("loginDialog")
        self._build_ui()

    def _build_ui(self) -> None:
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._build_form_panel(), stretch=1)
        root.addWidget(self._build_brand_panel(), stretch=1)

    def _build_form_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("loginFormPanel")
        panel.setLayoutDirection(Qt.LayoutDirection.RightToLeft)

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(56, 48, 56, 48)
        layout.setSpacing(0)
        layout.addStretch(1)

        title = QLabel("ورود به سیستم")
        title.setObjectName("loginTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignRight)
        subtitle = QLabel(f"{APP_PRODUCT_NAME} — مدیریت ماموریت خودروها")
        subtitle.setObjectName("loginSubtitle")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignRight)

        self.username_input = QLineEdit()
        self.username_input.setObjectName("loginInput")
        self.username_input.setPlaceholderText("نام کاربری را وارد کنید")
        configure_line_edit_field(self.username_input)

        self.password_input = QLineEdit()
        self.password_input.setObjectName("loginInput")
        self.password_input.setPlaceholderText("رمز عبور را وارد کنید")
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        configure_line_edit_field(self.password_input)
        self.password_input.returnPressed.connect(self._login)
        self.username_input.returnPressed.connect(self._login)

        login_button = QPushButton("ورود")
        login_button.setObjectName("loginButton")
        login_button.setCursor(Qt.CursorShape.PointingHandCursor)
        login_button.clicked.connect(self._login)

        version_label = QLabel(f"نسخه {to_persian_digits(APP_VERSION)}")
        version_label.setObjectName("loginVersionLabel")
        version_label.setAlignment(Qt.AlignmentFlag.AlignRight)

        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addSpacing(28)
        layout.addWidget(self._field("نام کاربری", self.username_input))
        layout.addSpacing(14)
        layout.addWidget(self._field("رمز عبور", self.password_input))
        layout.addSpacing(24)
        layout.addWidget(login_button)
        layout.addSpacing(12)
        layout.addWidget(version_label)
        layout.addStretch(1)
        return panel

    def _build_brand_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("loginBrandPanel")
        panel.setLayoutDirection(Qt.LayoutDirection.RightToLeft)

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(40, 42, 40, 28)
        layout.setSpacing(10)

        logo = QLabel(APP_PRODUCT_NAME)
        logo.setObjectName("loginBrandLogo")
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)

        tagline = QLabel("مدیریت ماموریت خودروها")
        tagline.setObjectName("loginBrandTagline")
        tagline.setAlignment(Qt.AlignmentFlag.AlignCenter)

        network = QLabel("شبکه بهداشت و درمان شهرستان")
        network.setObjectName("loginBrandNetwork")
        network.setAlignment(Qt.AlignmentFlag.AlignCenter)
        network.setWordWrap(True)

        city = QLabel("رودسر")
        city.setObjectName("loginBrandCity")
        city.setAlignment(Qt.AlignmentFlag.AlignCenter)

        decor = QFrame()
        decor.setObjectName("loginBrandDecor")
        decor.setFixedHeight(2)

        layout.addStretch(1)
        layout.addWidget(logo)
        layout.addWidget(tagline)
        layout.addSpacing(8)
        layout.addWidget(network)
        layout.addWidget(city)
        layout.addSpacing(24)
        layout.addWidget(decor)
        layout.addStretch(2)

        credits = QLabel(
            "توسط صادق جعفری و با همکاری علیرضا محمد رضایی\nطراحی و توسعه داده شده"
        )
        credits.setObjectName("loginBrandCredits")
        credits.setAlignment(Qt.AlignmentFlag.AlignCenter)
        credits.setWordWrap(True)
        layout.addWidget(credits)
        return panel

    def _field(self, label: str, widget: QLineEdit) -> QFrame:
        box = QFrame()
        box.setObjectName("loginFieldBox")
        box.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        field_layout = QVBoxLayout(box)
        field_layout.setContentsMargins(0, 0, 0, 0)
        field_layout.setSpacing(8)
        label_widget = QLabel(label)
        label_widget.setObjectName("loginFieldLabel")
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
