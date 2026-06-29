from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from database.db import DatabaseManager
from ui.utils import APP_PRODUCT_NAME, APP_VERSION, gregorian_to_jalali, show_error, to_persian_digits

LOGIN_ASSETS = Path(__file__).resolve().parent.parent / "assets" / "login"


class LoginDialog(QDialog):
    def __init__(self, db: DatabaseManager, parent=None) -> None:
        super().__init__(parent)
        self.db = db
        self.user: dict | None = None
        self._password_visible = False
        self.setWindowTitle(APP_PRODUCT_NAME)
        self.setModal(True)
        self.setFixedSize(920, 580)
        self.setObjectName("loginDialog")
        self._build_ui()

    def _build_ui(self) -> None:
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._build_form_panel(), stretch=11)
        root.addWidget(self._build_brand_panel(), stretch=10)

    def _build_form_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("loginFormPanel")
        panel.setLayoutDirection(Qt.LayoutDirection.RightToLeft)

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(72, 56, 72, 28)
        layout.setSpacing(0)

        title = QLabel("ورود به سیستم")
        title.setObjectName("loginTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignRight)

        subtitle = QLabel("لطفاً نام کاربری و رمز عبور خود را وارد کنید")
        subtitle.setObjectName("loginSubtitle")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignRight)
        subtitle.setWordWrap(True)

        self.username_field = self._icon_input(
            "نام کاربری خود را وارد کنید",
            LOGIN_ASSETS / "icon-user.svg",
            password=False,
        )
        self.password_field = self._icon_input(
            "رمز عبور خود را وارد کنید",
            LOGIN_ASSETS / "icon-lock.svg",
            password=True,
        )
        self._unwrap_input(self.password_field).returnPressed.connect(self._login)
        self._unwrap_input(self.username_field).returnPressed.connect(self._login)

        login_button = QPushButton("ورود")
        login_button.setObjectName("loginButton")
        login_button.setCursor(Qt.CursorShape.PointingHandCursor)
        login_button.clicked.connect(self._login)

        forgot_button = QPushButton("رمز عبور خود را فراموش کرده‌اید؟")
        forgot_button.setObjectName("loginForgotLink")
        forgot_button.setCursor(Qt.CursorShape.PointingHandCursor)
        forgot_button.clicked.connect(
            lambda: show_error(self, "برای بازیابی رمز عبور با مدیر سیستم تماس بگیرید.")
        )

        content = QVBoxLayout()
        content.setSpacing(0)
        content.addWidget(title)
        content.addSpacing(8)
        content.addWidget(subtitle)
        content.addSpacing(34)
        content.addWidget(self._field("نام کاربری", self.username_field))
        content.addSpacing(18)
        content.addWidget(self._field("رمز عبور", self.password_field))
        content.addSpacing(28)
        content.addWidget(login_button)
        content.addSpacing(14)
        content.addWidget(forgot_button, alignment=Qt.AlignmentFlag.AlignHCenter)

        layout.addStretch(1)
        layout.addLayout(content)
        layout.addStretch(1)

        footer_line = QFrame()
        footer_line.setObjectName("loginFooterLine")
        footer_line.setFixedHeight(1)

        footer_row = QHBoxLayout()
        footer_row.setContentsMargins(0, 14, 0, 0)
        footer_row.setSpacing(8)
        footer_logo = QLabel()
        footer_logo.setObjectName("loginFooterLogo")
        footer_logo.setPixmap(QIcon(str(LOGIN_ASSETS / "logo-small.svg")).pixmap(22, 22))
        footer_logo.setFixedSize(22, 22)
        footer_text = QLabel(
            f"{APP_PRODUCT_NAME}   نسخه {to_persian_digits(APP_VERSION)} | {to_persian_digits(gregorian_to_jalali())}"
        )
        footer_text.setObjectName("loginFooterText")
        footer_row.addStretch(1)
        footer_row.addWidget(footer_logo)
        footer_row.addWidget(footer_text)
        footer_row.addStretch(1)

        layout.addWidget(footer_line)
        layout.addLayout(footer_row)
        return panel

    def _icon_input(self, placeholder: str, icon_path: Path, *, password: bool) -> QFrame:
        wrapper = QFrame()
        wrapper.setObjectName("loginInputWrap")
        wrapper.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        row = QHBoxLayout(wrapper)
        row.setContentsMargins(12, 0, 12, 0)
        row.setSpacing(8)

        icon = QLabel()
        icon.setObjectName("loginInputIcon")
        icon.setPixmap(QIcon(str(icon_path)).pixmap(18, 18))
        icon.setFixedSize(20, 20)

        line_edit = QLineEdit()
        line_edit.setObjectName("loginInput")
        line_edit.setPlaceholderText(placeholder)
        line_edit.setFrame(False)
        line_edit.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        line_edit.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        if password:
            line_edit.setEchoMode(QLineEdit.EchoMode.Password)

        row.addWidget(icon)
        row.addWidget(line_edit, stretch=1)
        if password:
            self._eye_button = QToolButton()
            self._eye_button.setObjectName("loginEyeButton")
            self._eye_button.setCursor(Qt.CursorShape.PointingHandCursor)
            self._eye_button.setIcon(QIcon(str(LOGIN_ASSETS / "icon-eye.svg")))
            self._eye_button.setIconSize(line_edit.sizeHint())
            self._eye_button.setFixedSize(28, 28)
            self._eye_button.clicked.connect(self._toggle_password_visibility)
            row.addWidget(self._eye_button)

        wrapper._line_edit = line_edit  # type: ignore[attr-defined]
        return wrapper

    def _unwrap_input(self, wrapper: QFrame) -> QLineEdit:
        return wrapper._line_edit  # type: ignore[attr-defined]

    def _toggle_password_visibility(self) -> None:
        self._password_visible = not self._password_visible
        password_input = self._unwrap_input(self.password_field)
        password_input.setEchoMode(
            QLineEdit.EchoMode.Normal if self._password_visible else QLineEdit.EchoMode.Password
        )
        icon_name = "icon-eye-off.svg" if self._password_visible else "icon-eye.svg"
        self._eye_button.setIcon(QIcon(str(LOGIN_ASSETS / icon_name)))

    def _field(self, label: str, widget: QWidget) -> QFrame:
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

    def _build_brand_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("loginBrandPanel")
        panel.setLayoutDirection(Qt.LayoutDirection.RightToLeft)

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(36, 48, 36, 22)
        layout.setSpacing(0)

        logo = QLabel()
        logo.setObjectName("loginBrandPinLogo")
        logo.setPixmap(QIcon(str(LOGIN_ASSETS / "logo-pin.svg")).pixmap(108, 126))
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo.setFixedHeight(130)

        brand_name = QLabel(APP_PRODUCT_NAME)
        brand_name.setObjectName("loginBrandLogo")
        brand_name.setAlignment(Qt.AlignmentFlag.AlignCenter)

        separator = self._brand_separator()

        network = QLabel("شبکه بهداشت و درمان شهرستان رودسر")
        network.setObjectName("loginBrandNetwork")
        network.setAlignment(Qt.AlignmentFlag.AlignCenter)
        network.setWordWrap(True)

        map_pattern = QLabel()
        map_pattern.setObjectName("loginBrandMap")
        map_pattern.setPixmap(QIcon(str(LOGIN_ASSETS / "map-pattern.svg")).pixmap(360, 150))
        map_pattern.setAlignment(Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignHCenter)
        map_pattern.setScaledContents(True)
        map_pattern.setFixedHeight(150)

        credits = QLabel(
            "توسط صادق جعفری و با همکاری علیرضا محمد رضایی\nطراحی و توسعه داده شده"
        )
        credits.setObjectName("loginBrandCredits")
        credits.setAlignment(Qt.AlignmentFlag.AlignCenter)
        credits.setWordWrap(True)

        layout.addStretch(1)
        layout.addWidget(logo, alignment=Qt.AlignmentFlag.AlignHCenter)
        layout.addSpacing(10)
        layout.addWidget(brand_name)
        layout.addSpacing(16)
        layout.addWidget(separator)
        layout.addSpacing(16)
        layout.addWidget(network)
        layout.addStretch(2)
        layout.addWidget(map_pattern)
        layout.addSpacing(10)
        layout.addWidget(credits)
        return panel

    def _brand_separator(self) -> QWidget:
        row_widget = QWidget()
        row_widget.setObjectName("loginBrandSeparator")
        row = QHBoxLayout(row_widget)
        row.setContentsMargins(48, 0, 48, 0)
        row.setSpacing(10)
        left = QFrame()
        left.setObjectName("loginBrandSeparatorLine")
        left.setFixedHeight(1)
        dot = QLabel()
        dot.setObjectName("loginBrandSeparatorDot")
        dot.setFixedSize(8, 8)
        right = QFrame()
        right.setObjectName("loginBrandSeparatorLine")
        right.setFixedHeight(1)
        row.addWidget(left, stretch=1)
        row.addWidget(dot, alignment=Qt.AlignmentFlag.AlignCenter)
        row.addWidget(right, stretch=1)
        return row_widget

    def _login(self) -> None:
        username = self._unwrap_input(self.username_field).text().strip()
        password = self._unwrap_input(self.password_field).text()
        if not username or not password:
            show_error(self, "نام کاربری و رمز عبور را وارد کنید.")
            return
        user = self.db.authenticate(username, password)
        if not user:
            show_error(self, "نام کاربری یا رمز عبور اشتباه است.")
            self._unwrap_input(self.password_field).clear()
            self._unwrap_input(self.password_field).setFocus()
            return
        self.user = user
        self.accept()
