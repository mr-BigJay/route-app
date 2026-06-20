from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QTimer, Qt
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
from ui.utils import APP_VERSION, current_time_text, gregorian_to_jalali


class MainWindow(QMainWindow):
    def __init__(self, db: DatabaseManager) -> None:
        super().__init__()
        self.db = db
        self.setWindowTitle("Route - مدیریت ماموریت خودروها")
        self.setMinimumSize(1180, 760)
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.nav_buttons: list[QPushButton] = []

        self.stack = QStackedWidget()
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
        main_layout = QHBoxLayout(central)
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
        sidebar.setFixedWidth(240)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(18, 24, 18, 24)
        layout.setSpacing(12)

        logo = QLabel("Route")
        logo.setObjectName("logo")
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle = QLabel("مدیریت ماموریت خودروها")
        subtitle.setObjectName("sidebarSubtitle")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(logo)
        layout.addWidget(subtitle)
        layout.addSpacing(22)

        items = [
            ("داشبورد", "⌂"),
            ("مدیریت رانندگان", "◯"),
            ("مدیریت نقاط", "◇"),
            ("ماموریت‌ها", "□"),
            ("گزارشات", "▥"),
        ]
        for index, (title, icon) in enumerate(items):
            button = QPushButton(f"{icon}  {title}")
            button.setObjectName("navButton")
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.clicked.connect(lambda checked=False, page=index: self._select_page(page))
            self.nav_buttons.append(button)
            layout.addWidget(button)

        layout.addStretch(1)
        self.date_label = QLabel(gregorian_to_jalali())
        self.time_label = QLabel(current_time_text())
        date_card = QFrame()
        date_card.setObjectName("dateCard")
        date_layout = QVBoxLayout(date_card)
        date_layout.setSpacing(8)
        date_layout.addWidget(QLabel("امروز"), alignment=Qt.AlignmentFlag.AlignCenter)
        date_layout.addWidget(self.date_label, alignment=Qt.AlignmentFlag.AlignCenter)
        date_layout.addWidget(self.time_label, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(date_card)

        timer = QTimer(self)
        timer.timeout.connect(self._tick)
        timer.start(1000)
        return sidebar

    def _build_status_bar(self) -> None:
        status = QStatusBar()
        status.setObjectName("statusBar")
        db_state = "متصل" if Path(DB_PATH).exists() else "در حال ایجاد"
        status.addPermanentWidget(QLabel(f"نسخه {APP_VERSION}"))
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
        self.date_label.setText(gregorian_to_jalali())
        self.time_label.setText(current_time_text())
