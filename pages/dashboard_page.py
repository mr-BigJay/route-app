from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsBlurEffect,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from database.db import DatabaseManager
from ui.mission_form_widget import MissionFormWidget
from ui.utils import PRIMARY_COLOR, SUCCESS_COLOR, Page, gregorian_to_jalali, make_stat_card, to_persian_digits


class DashboardPage(Page):
    def __init__(self, db: DatabaseManager) -> None:
        super().__init__("داشبورد", "نمای کلی وضعیت سیستم")
        self.db = db
        self.setObjectName("dashboardPage")

        action_row = QHBoxLayout()
        action_row.setContentsMargins(0, 0, 0, 0)
        action_row.addStretch(1)
        self.register_button = self.action_button("ثبت ماموریت", "primary")
        self.register_button.setObjectName("dashboardActionButton")
        self.register_button.setMinimumWidth(160)
        self.register_button.clicked.connect(self.open_mission_overlay)
        action_row.addWidget(self.register_button)
        self.root_layout.addLayout(action_row)

        self.content_area = QWidget()
        self.content_area.setObjectName("dashboardContent")
        content_layout = QVBoxLayout(self.content_area)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(16)

        self.stats_layout = QGridLayout()
        self.stats_layout.setSpacing(14)
        content_layout.addLayout(self.stats_layout)
        content_layout.addWidget(self._recent_missions_card(), stretch=1)
        self.root_layout.addWidget(self.content_area, stretch=1)
        self._build_mission_overlay()

    def _recent_missions_card(self) -> QFrame:
        card = self.card()
        card.setObjectName("dashboardTableCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QFrame()
        header.setObjectName("dashboardTableHeader")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(18, 14, 18, 14)
        title = QLabel("ماموریت‌های اخیر")
        title.setObjectName("dashboardTableTitle")
        header_layout.addWidget(title)
        header_layout.addStretch(1)

        body = QFrame()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(18, 12, 18, 16)
        self.table = QTableWidget(0, 7)
        self.table.setObjectName("dashboardTable")
        self.table.setHorizontalHeaderLabels(
            ["ردیف", "تاریخ", "راننده", "خودرو", "مسیر", "مسافت (km)", "ساعت"]
        )
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        body_layout.addWidget(self.table)

        layout.addWidget(header)
        layout.addWidget(body)
        return card

    def _build_mission_overlay(self) -> None:
        self.mission_overlay = QFrame(self)
        self.mission_overlay.setObjectName("missionOverlay")
        self.mission_overlay.hide()

        overlay_layout = QVBoxLayout(self.mission_overlay)
        overlay_layout.setContentsMargins(24, 24, 24, 24)
        overlay_layout.addStretch(1)

        mission_card = QFrame()
        mission_card.setObjectName("missionModalCard")
        mission_card.setMaximumWidth(760)
        card_layout = QVBoxLayout(mission_card)
        card_layout.setContentsMargins(20, 18, 20, 18)
        card_layout.setSpacing(10)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.mission_form = MissionFormWidget(self.db)
        self.mission_form.saved.connect(self._on_mission_saved)
        self.mission_form.cancelled.connect(self.close_mission_overlay)
        scroll.setWidget(self.mission_form)

        card_layout.addWidget(scroll)
        overlay_layout.addWidget(mission_card, alignment=Qt.AlignmentFlag.AlignCenter)
        overlay_layout.addStretch(1)

    def open_mission_overlay(self) -> None:
        self.mission_form.prepare_new()
        blur = QGraphicsBlurEffect(self.content_area)
        blur.setBlurRadius(8)
        self.content_area.setGraphicsEffect(blur)
        self.mission_overlay.setGeometry(self.rect())
        self.mission_overlay.raise_()
        self.mission_overlay.show()

    def close_mission_overlay(self) -> None:
        self.content_area.setGraphicsEffect(None)
        self.mission_overlay.hide()

    def _on_mission_saved(self) -> None:
        self.close_mission_overlay()
        self.refresh()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if hasattr(self, "mission_overlay"):
            self.mission_overlay.setGeometry(self.rect())

    def refresh(self) -> None:
        self._refresh_stats()
        self._refresh_recent()

    def _refresh_stats(self) -> None:
        while self.stats_layout.count():
            item = self.stats_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        stats = self.db.dashboard_stats(gregorian_to_jalali())
        cards = [
            ("رانندگان فعال", str(stats["drivers"]), "#7C3AED", "#F5F3FF"),
            ("نقاط ثبت شده", str(stats["locations"]), "#F97316", "#FFF7ED"),
            ("ماموریت‌های امروز", str(stats["today_missions"]), PRIMARY_COLOR, "#EFF6FF"),
            ("کل ماموریت‌ها", str(stats["missions"]), SUCCESS_COLOR, "#ECFDF5"),
        ]
        for column, (title, value, color, tint) in enumerate(cards):
            self.stats_layout.addWidget(make_stat_card(title, value, color, tint), 0, column)

    def _refresh_recent(self) -> None:
        missions = self.db.list_missions(limit=10)
        self.table.setRowCount(len(missions))
        for row, mission in enumerate(missions):
            values = [
                to_persian_digits(row + 1),
                to_persian_digits(mission["mission_date"]),
                mission["driver_name"],
                mission["vehicle"],
                f"{mission['origin']} ← {mission['destination']}",
                to_persian_digits(f"{float(mission['distance']):.1f}"),
                to_persian_digits(mission["mission_time"]),
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(row, col, item)
