from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QSizePolicy, QWidget


class DriverStatusBadge(QWidget):
    def __init__(self, is_active: bool, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)

        badge = QFrame()
        badge.setObjectName("driverStatusBadge")
        badge.setProperty("active", "true" if is_active else "false")

        layout = QHBoxLayout(badge)
        layout.setContentsMargins(10, 4, 10, 4)
        layout.setSpacing(6)

        dot = QLabel()
        dot.setObjectName("driverStatusDot")
        dot.setProperty("active", "true" if is_active else "false")
        dot.setFixedSize(8, 8)

        label = QLabel("فعال" if is_active else "غیرفعال")
        label.setObjectName("driverStatusText")
        label.setProperty("active", "true" if is_active else "false")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(dot, alignment=Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(label, alignment=Qt.AlignmentFlag.AlignVCenter)

        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(badge, alignment=Qt.AlignmentFlag.AlignCenter)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
