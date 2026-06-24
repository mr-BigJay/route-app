from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSize, QTimer, Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from database.db import DB_PATH, DatabaseManager
from pages.dashboard_page import DashboardPage
from pages.drivers_page import DriversPage
from pages.locations_page import LocationsPage
from pages.missions_page import MissionsPage
from pages.reports_page import ReportsPage
from ui.utils import (
    APP_VERSION,
    current_time_text,
    gregorian_to_jalali,
    persian_weekday_name,
    to_persian_digits,
)


class MainWindow(QMainWindow):
    def __init__(self, db: DatabaseManager) -> None:
        super().__init__()
        self.db = db
        self.setWindowTitle("Route v.1 - مدیریت ماموریت خودروها")
        self.setMinimumSize(1180, 760)
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.nav_buttons: list[QPushButton] = []

        self.stack = QStackedWidget()
        self.stack.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.pages = [
            DashboardPage(self.db),
            DriversPage(self.db),
            LocationsPage(self.db),
            MissionsPage(self.db),
            ReportsPage(self.db),
        ]
        for page in self.pages:
            self.stack.addWidget(page)

        central = QWidget()
        # Keep the top-level container physically LTR so the last widget stays
        # on the right; all child pages and sidebar content remain RTL.
        central.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        main_layout = QHBoxLayout(central)
        # Physical placement: content on the left, sidebar on the right.
        # Child widgets keep RTL layout direction for text and controls.
        main_layout.setDirection(QHBoxLayout.Direction.LeftToRight)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        main_layout.addWidget(self.stack, stretch=1)
        main_layout.addWidget(self._build_sidebar())
        self.setCentralWidget(central)
        self._build_status_bar()
        self._select_page(0)

    def _build_sidebar(self) -> QWidget:
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        sidebar.setFixedWidth(240)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(18, 24, 18, 24)
        layout.setSpacing(12)

        logo = QLabel("Route v.1")
        logo.setObjectName("logo")
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle = QLabel("مدیریت ماموریت خودروها")
        subtitle.setObjectName("sidebarSubtitle")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        network = QLabel("شبکه بهداشت و درمان شهرستان")
        network.setObjectName("sidebarNetwork")
        network.setAlignment(Qt.AlignmentFlag.AlignCenter)
        network.setWordWrap(True)
        city = QLabel("رودسر")
        city.setObjectName("sidebarCity")
        city.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(logo)
        layout.addWidget(subtitle)
        layout.addWidget(network)
        layout.addWidget(city)
        layout.addSpacing(18)

        icons_dir = Path(__file__).resolve().parent.parent / "assets" / "icons"
        items = [
            ("داشبورد", icons_dir / "nav_1.svg"),
            ("مدیریت رانندگان", icons_dir / "nav_2.svg"),
            ("مدیریت نقاط", icons_dir / "nav_3.svg"),
            ("ماموریت‌ها", icons_dir / "nav_4.svg"),
            ("گزارشات", icons_dir / "nav_5.svg"),
        ]
        for index, (title, icon_path) in enumerate(items):
            button = QPushButton(title)
            button.setObjectName("navButton")
            button.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
            button.setIcon(QIcon(str(icon_path)))
            button.setIconSize(QSize(24, 24))
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.clicked.connect(lambda checked=False, page=index: self._select_page(page))
            self.nav_buttons.append(button)
            layout.addWidget(button, alignment=Qt.AlignmentFlag.AlignHCenter)

        layout.addStretch(1)
        self.weekday_label = QLabel(persian_weekday_name())
        self.weekday_label.setObjectName("weekdayLabel")
        self.date_label = QLabel(to_persian_digits(gregorian_to_jalali()))
        self.time_label = QLabel(to_persian_digits(current_time_text()))
        date_card = QFrame()
        date_card.setObjectName("dateCard")
        date_layout = QVBoxLayout(date_card)
        date_layout.setSpacing(8)
        date_layout.addWidget(self.weekday_label, alignment=Qt.AlignmentFlag.AlignCenter)
        date_layout.addWidget(self.date_label, alignment=Qt.AlignmentFlag.AlignCenter)
        date_layout.addWidget(self.time_label, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(date_card)

        footer = QLabel(
            "طراحی و توسعه\n"
            "صادق جعفری با همکاری علیرضا محمدرضایی\n"
            "کارشناس IT - شبکه بهداشت رودسر"
        )
        footer.setObjectName("sidebarFooter")
        footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        footer.setWordWrap(True)
        layout.addWidget(footer)

        timer = QTimer(self)
        timer.timeout.connect(self._tick)
        timer.start(1000)
        return sidebar

    def _build_status_bar(self) -> None:
        status = QStatusBar()
        status.setObjectName("statusBar")
        db_state = "متصل" if Path(DB_PATH).exists() else "در حال ایجاد"
        status.addPermanentWidget(QLabel(f"نسخه {to_persian_digits(APP_VERSION)}"))
        status.addPermanentWidget(QLabel("کاربر: مدیر سیستم"))
        status.addWidget(QLabel(f"وضعیت پایگاه داده محلی: {db_state}"))
        self.setStatusBar(status)

    def _select_page(self, index: int) -> None:
        self.stack.setCurrentIndex(index)
        for button_index, button in enumerate(self.nav_buttons):
            button.setProperty("active", button_index == index)
            button.style().unpolish(button)
            button.style().polish(button)

        page = self.pages[index]
        if hasattr(page, "refresh"):
            page.refresh()

    def _tick(self) -> None:
        self.weekday_label.setText(persian_weekday_name())
        self.date_label.setText(to_persian_digits(gregorian_to_jalali()))
        self.time_label.setText(to_persian_digits(current_time_text()))
