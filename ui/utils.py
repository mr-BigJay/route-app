from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


APP_VERSION = "1.0.0"
PRIMARY_COLOR = "#2563EB"
SUCCESS_COLOR = "#22C55E"
BACKGROUND_COLOR = "#F8FAFC"
PERSIAN_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")
ENGLISH_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


def to_persian_digits(value: object) -> str:
    return str(value).translate(PERSIAN_DIGITS)


def to_english_digits(value: object) -> str:
    return str(value).translate(ENGLISH_DIGITS)


def gregorian_to_jalali(g_date: date | None = None) -> str:
    g_date = g_date or date.today()
    gy = g_date.year
    gm = g_date.month
    gd = g_date.day
    g_days_in_month = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    j_days_in_month = [31, 31, 31, 31, 31, 31, 30, 30, 30, 30, 30, 29]

    gy -= 1600
    gm -= 1
    gd -= 1

    g_day_no = 365 * gy + (gy + 3) // 4 - (gy + 99) // 100 + (gy + 399) // 400
    for i in range(gm):
        g_day_no += g_days_in_month[i]
    if gm > 1 and ((gy + 1600) % 4 == 0 and ((gy + 1600) % 100 != 0 or (gy + 1600) % 400 == 0)):
        g_day_no += 1
    g_day_no += gd

    j_day_no = g_day_no - 79
    j_np = j_day_no // 12053
    j_day_no %= 12053
    jy = 979 + 33 * j_np + 4 * (j_day_no // 1461)
    j_day_no %= 1461

    if j_day_no >= 366:
        jy += (j_day_no - 1) // 365
        j_day_no = (j_day_no - 1) % 365

    jm = 0
    for i, days in enumerate(j_days_in_month):
        if j_day_no < days:
            jm = i + 1
            break
        j_day_no -= days
    jd = j_day_no + 1

    return f"{jy:04d}/{jm:02d}/{jd:02d}"


def current_time_text() -> str:
    return datetime.now().strftime("%H:%M:%S")


def load_vazirmatn_font(fonts_dir: Path) -> str:
    font_family = "Vazirmatn"
    for font_path in fonts_dir.glob("Vazirmatn*.ttf"):
        font_id = QFontDatabase.addApplicationFont(str(font_path))
        families = QFontDatabase.applicationFontFamilies(font_id)
        if families:
            font_family = families[0]
            break
    return font_family


def show_error(parent: QWidget, message: str) -> None:
    QMessageBox.critical(parent, "خطا", message)


def show_success(parent: QWidget, message: str) -> None:
    QMessageBox.information(parent, "موفق", message)


def confirm(parent: QWidget, message: str) -> bool:
    answer = QMessageBox.question(
        parent,
        "تایید عملیات",
        message,
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        QMessageBox.StandardButton.No,
    )
    return answer == QMessageBox.StandardButton.Yes


def clear_layout(layout: QVBoxLayout | QHBoxLayout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        if widget is not None:
            widget.deleteLater()


class Page(QWidget):
    def __init__(self, title: str, subtitle: str = "") -> None:
        super().__init__()
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.root_layout = QVBoxLayout(self)
        self.root_layout.setContentsMargins(22, 22, 22, 16)
        self.root_layout.setSpacing(16)
        self.root_layout.addWidget(self._header(title, subtitle))

    def _header(self, title: str, subtitle: str) -> QWidget:
        header = QWidget()
        layout = QVBoxLayout(header)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        title_label = QLabel(title)
        title_label.setObjectName("pageTitle")
        subtitle_label = QLabel(subtitle)
        subtitle_label.setObjectName("pageSubtitle")
        layout.addWidget(title_label, alignment=Qt.AlignmentFlag.AlignRight)
        if subtitle:
            layout.addWidget(subtitle_label, alignment=Qt.AlignmentFlag.AlignRight)
        return header

    def card(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("card")
        frame.setFrameShape(QFrame.Shape.NoFrame)
        return frame

    def action_button(self, text: str, role: str = "primary") -> QPushButton:
        button = QPushButton(text)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setProperty("role", role)
        return button


def make_stat_card(title: str, value: str, accent: str = PRIMARY_COLOR) -> QFrame:
    frame = QFrame()
    frame.setObjectName("statCard")
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(18, 16, 18, 16)
    layout.setSpacing(8)
    title_label = QLabel(title)
    title_label.setObjectName("statTitle")
    value_label = QLabel(value)
    value_label.setText(to_persian_digits(value))
    value_label.setObjectName("statValue")
    accent_bar = QFrame()
    accent_bar.setFixedHeight(4)
    accent_bar.setStyleSheet(f"background: {accent}; border-radius: 2px;")
    layout.addWidget(title_label)
    layout.addWidget(value_label)
    layout.addWidget(accent_bar)
    return frame
