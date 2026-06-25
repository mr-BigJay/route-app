from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QLineEdit, QPushButton, QSizePolicy, QWidget

from ui.utils import to_persian_digits


class LocationQuickAddWidget(QWidget):
    confirmed = Signal(str)
    cancelled = Signal()

    def __init__(self, sort_order: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("locationQuickAdd")
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 4, 10, 4)
        layout.setSpacing(8)

        self.order_badge = QLabel(to_persian_digits(sort_order))
        self.order_badge.setObjectName("locationQuickAddOrder")
        self.order_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.order_badge.setFixedSize(28, 28)

        self.title_input = QLineEdit()
        self.title_input.setObjectName("locationQuickAddInput")
        self.title_input.setPlaceholderText("عنوان نقطه را وارد کنید")
        self.title_input.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.title_input.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.title_input.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.title_input.returnPressed.connect(self._on_confirm)

        self.confirm_button = QPushButton("✓")
        self.confirm_button.setObjectName("locationQuickAddConfirm")
        self.confirm_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.confirm_button.setFixedSize(32, 32)
        self.confirm_button.clicked.connect(self._on_confirm)

        self.cancel_button = QPushButton("×")
        self.cancel_button.setObjectName("locationQuickAddCancel")
        self.cancel_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.cancel_button.setFixedSize(32, 32)
        self.cancel_button.clicked.connect(self.cancelled.emit)

        layout.addWidget(self.order_badge)
        layout.addWidget(self.title_input, stretch=1)
        layout.addWidget(self.confirm_button)
        layout.addWidget(self.cancel_button)

    def focus_input(self) -> None:
        self.title_input.setFocus(Qt.FocusReason.OtherFocusReason)
        self.title_input.selectAll()

    def _on_confirm(self) -> None:
        title = self.title_input.text().strip()
        if title:
            self.confirmed.emit(title)
