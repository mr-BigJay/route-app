from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsBlurEffect,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from database.db import DatabaseManager
from ui.mission_form_widget import MissionFormWidget
from ui.utils import PRIMARY_COLOR, SUCCESS_COLOR, Page, gregorian_to_jalali, make_stat_card, to_persian_digits

MISSION_COLUMNS = ["ردیف", "تاریخ", "راننده", "سرنشینان", "مبدا", "مقصد", "مسافت (km)"]
PASSENGERS_COLUMN = 3


class DashboardPage(Page):
    def __init__(self, db: DatabaseManager) -> None:
        super().__init__("داشبورد", "نمای کلی وضعیت سیستم")
        self.db = db
        self.setObjectName("dashboardPage")
        self._center_page_header()

        action_row = QHBoxLayout()
        action_row.setContentsMargins(0, 0, 0, 0)
        action_row.setSpacing(12)
        action_row.addStretch(1)
        self.register_button = self.action_button("ثبت ماموریت", "primary")
        self.register_button.setObjectName("dashboardActionButton")
        self.register_button.setMinimumWidth(160)
        self.register_button.clicked.connect(self.open_mission_overlay)
        self.reserve_button = self.action_button("رزرو ماموریت", "secondary")
        self.reserve_button.setObjectName("dashboardReserveButton")
        self.reserve_button.setMinimumWidth(160)
        self.reserve_button.clicked.connect(self._on_reserve_clicked)
        action_row.addWidget(self.register_button)
        action_row.addWidget(self.reserve_button)
        action_row.addStretch(1)
        self.root_layout.addLayout(action_row)

        self.content_area = QWidget()
        self.content_area.setObjectName("dashboardContent")
        content_layout = QVBoxLayout(self.content_area)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(16)

        self.stats_layout = QGridLayout()
        self.stats_layout.setSpacing(14)
        content_layout.addLayout(self.stats_layout)

        self.missions_table = self._create_table("dashboardTable")
        self.reservations_table = self._create_table("dashboardReservationsTable")
        content_layout.addWidget(self._build_tables_tabs(), stretch=2)
        self.root_layout.addWidget(self.content_area, stretch=1)
        self._build_mission_overlay()

    def _build_tables_tabs(self) -> QFrame:
        card = self.card()
        card.setObjectName("dashboardTableCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.tables_tabs = QTabWidget()
        self.tables_tabs.setObjectName("dashboardTablesTabs")
        self.tables_tabs.setLayoutDirection(Qt.LayoutDirection.RightToLeft)

        missions_tab = QWidget()
        missions_layout = QVBoxLayout(missions_tab)
        missions_layout.setContentsMargins(18, 12, 18, 16)
        missions_layout.addWidget(self.missions_table)

        reservations_tab = QWidget()
        reservations_layout = QVBoxLayout(reservations_tab)
        reservations_layout.setContentsMargins(18, 12, 18, 16)
        reservations_layout.addWidget(self.reservations_table)

        self.tables_tabs.addTab(missions_tab, "ماموریت‌های اخیر")
        self.tables_tabs.addTab(reservations_tab, "رزرو ماموریت")
        self.tables_tabs.setCurrentIndex(0)
        layout.addWidget(self.tables_tabs)
        return card

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
                layout.setAlignment(widget, Qt.AlignmentFlag.AlignHCenter)

    def _create_table(self, object_name: str) -> QTableWidget:
        table = QTableWidget(0, len(MISSION_COLUMNS))
        table.setObjectName(object_name)
        table.setHorizontalHeaderLabels(MISSION_COLUMNS)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setDefaultAlignment(Qt.AlignmentFlag.AlignCenter)
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.setAlternatingRowColors(True)
        return table

    def _build_mission_overlay(self) -> None:
        self.mission_overlay = QFrame(self)
        self.mission_overlay.setObjectName("missionOverlay")
        self.mission_overlay.hide()

        overlay_layout = QVBoxLayout(self.mission_overlay)
        overlay_layout.setContentsMargins(24, 24, 24, 24)
        overlay_layout.addStretch(1)

        self.mission_card = QFrame()
        self.mission_card.setObjectName("missionModalCard")
        card_layout = QVBoxLayout(self.mission_card)
        card_layout.setContentsMargins(24, 22, 24, 22)
        card_layout.setSpacing(12)

        self.mission_scroll = QScrollArea()
        self.mission_scroll.setObjectName("missionModalScroll")
        self.mission_scroll.setWidgetResizable(True)
        self.mission_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.mission_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.mission_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.mission_form = MissionFormWidget(self.db)
        self.mission_form.setObjectName("missionFormWidget")
        self.mission_form.saved.connect(self._on_mission_saved)
        self.mission_form.cancelled.connect(self.close_mission_overlay)
        self.mission_scroll.setWidget(self.mission_form)

        card_layout.addWidget(self.mission_scroll)
        overlay_layout.addWidget(self.mission_card, alignment=Qt.AlignmentFlag.AlignCenter)
        overlay_layout.addStretch(1)
        self._resize_mission_modal()

    def _on_reserve_clicked(self) -> None:
        QMessageBox.information(
            self,
            "به زودی",
            "قابلیت رزرو ماموریت در نسخه‌های بعدی اضافه خواهد شد.",
        )

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

    def _resize_mission_modal(self) -> None:
        if not hasattr(self, "mission_card"):
            return
        card_width = min(1100, max(920, int(self.width() * 0.72)))
        card_height = min(720, max(580, int(self.height() * 0.78)))
        self.mission_card.setFixedWidth(card_width)
        self.mission_scroll.setMinimumHeight(card_height)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if hasattr(self, "mission_overlay"):
            self.mission_overlay.setGeometry(self.rect())
        self._resize_mission_modal()

    def refresh(self) -> None:
        self._refresh_stats()
        self._refresh_recent()
        self._refresh_reservations()

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

    @staticmethod
    def _last_destination(destination: str) -> str:
        parts = [part.strip() for part in destination.split("،") if part.strip()]
        return parts[-1] if parts else destination

    def _populate_mission_table(self, table: QTableWidget, missions: list[dict]) -> None:
        passengers_font = QFont()
        passengers_font.setPointSize(9)
        table.setRowCount(len(missions))
        for row, mission in enumerate(missions):
            values = [
                to_persian_digits(row + 1),
                to_persian_digits(mission["mission_date"]),
                mission["driver_name"],
                mission.get("passengers") or "-",
                mission["origin"],
                self._last_destination(mission["destination"]),
                to_persian_digits(f"{float(mission['distance']):.1f}"),
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if col == PASSENGERS_COLUMN:
                    item.setFont(passengers_font)
                table.setItem(row, col, item)

    def _refresh_recent(self) -> None:
        missions = self.db.list_missions(limit=10)
        self._populate_mission_table(self.missions_table, missions)

    def _refresh_reservations(self) -> None:
        self.reservations_table.setRowCount(0)
