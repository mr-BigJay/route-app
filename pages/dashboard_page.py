from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from database.db import DB_PATH, DatabaseManager
from ui.utils import PRIMARY_COLOR, SUCCESS_COLOR, Page, gregorian_to_jalali, make_stat_card


class DashboardPage(Page):
    def __init__(self, db: DatabaseManager) -> None:
        super().__init__("داشبورد", "نمای کلی وضعیت سیستم")
        self.db = db
        self.stats_layout = QGridLayout()
        self.stats_layout.setSpacing(14)
        self.root_layout.addLayout(self.stats_layout)

        body = QHBoxLayout()
        body.setSpacing(16)
        body.addWidget(self._recent_missions_card(), stretch=2)
        body.addWidget(self._database_status_card(), stretch=1)
        self.root_layout.addLayout(body, stretch=1)

    def _recent_missions_card(self):
        card = self.card()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 16, 18, 16)
        title = QLabel("ماموریت‌های اخیر")
        title.setObjectName("sectionTitle")
        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(
            ["ردیف", "تاریخ", "راننده", "خودرو", "مسیر", "مسافت (km)", "ساعت"]
        )
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        layout.addWidget(title)
        layout.addWidget(self.table)
        return card

    def _database_status_card(self):
        card = self.card()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)
        title = QLabel("وضعیت سیستم")
        title.setObjectName("sectionTitle")
        self.db_path_label = QLabel()
        self.db_status_label = QLabel()
        self.today_label = QLabel()
        layout.addWidget(title)
        layout.addWidget(self.db_status_label)
        layout.addWidget(self.today_label)
        layout.addWidget(self.db_path_label)
        layout.addStretch(1)
        return card

    def refresh(self) -> None:
        self._refresh_stats()
        self._refresh_recent()
        db_exists = Path(DB_PATH).exists()
        self.db_status_label.setText("پایگاه داده: فعال" if db_exists else "پایگاه داده: آماده ایجاد")
        self.today_label.setText(f"تاریخ امروز: {gregorian_to_jalali()}")
        self.db_path_label.setText(f"مسیر فایل: {DB_PATH}")

    def _refresh_stats(self) -> None:
        while self.stats_layout.count():
            item = self.stats_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        stats = self.db.dashboard_stats(gregorian_to_jalali())
        cards = [
            ("رانندگان فعال", str(stats["drivers"]), "#7C3AED"),
            ("نقاط ثبت شده", str(stats["locations"]), "#F97316"),
            ("ماموریت‌های امروز", str(stats["today_missions"]), PRIMARY_COLOR),
            ("کل ماموریت‌ها", str(stats["missions"]), SUCCESS_COLOR),
        ]
        for column, (title, value, color) in enumerate(cards):
            self.stats_layout.addWidget(make_stat_card(title, value, color), 0, column)

    def _refresh_recent(self) -> None:
        missions = self.db.list_missions(limit=10)
        self.table.setRowCount(len(missions))
        for row, mission in enumerate(missions):
            values = [
                str(row + 1),
                mission["mission_date"],
                mission["driver_name"],
                mission["vehicle"],
                f"{mission['origin']} ← {mission['destination']}",
                f"{float(mission['distance']):.1f}",
                mission["mission_time"],
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(row, col, item)
