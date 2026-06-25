from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QSizePolicy, QWidget


class DriverStatusBadge(QWidget):
    def __init__(self, is_active: bool, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(26)

        active_value = "true" if is_active else "false"
        badge = QFrame()
        badge.setObjectName("driverStatusBadge")
        badge.setProperty("active", active_value)
        badge.setFixedHeight(24)

        layout = QHBoxLayout(badge)
        layout.setContentsMargins(8, 0, 8, 0)
        layout.setSpacing(6)

        dot = QFrame()
        dot.setObjectName("driverStatusDot")
        dot.setProperty("active", active_value)
        dot.setFixedSize(8, 8)
        dot.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        label = QLabel("فعال" if is_active else "غیرفعال")
        label.setObjectName("driverStatusText")
        label.setProperty("active", active_value)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        layout.addWidget(dot, alignment=Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(label, alignment=Qt.AlignmentFlag.AlignVCenter)

        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(badge, alignment=Qt.AlignmentFlag.AlignCenter)

        for widget in (badge, dot, label):
            widget.style().unpolish(widget)
            widget.style().polish(widget)
