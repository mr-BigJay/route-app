from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QComboBox, QDoubleSpinBox, QLineEdit, QSpinBox, QWidget


FORM_FIELD_FONT_SIZE = 11
FORM_FIELD_MIN_HEIGHT = 36


class NoWheelComboBox(QComboBox):
    def wheelEvent(self, event) -> None:
        event.ignore()


class NoWheelSpinBox(QSpinBox):
    def wheelEvent(self, event) -> None:
        event.ignore()


class NoWheelDoubleSpinBox(QDoubleSpinBox):
    def wheelEvent(self, event) -> None:
        event.ignore()


def apply_form_field_font(widget: QWidget) -> None:
    font = widget.font()
    font.setPointSize(FORM_FIELD_FONT_SIZE)
    widget.setFont(font)


def configure_line_edit_field(line_edit: QLineEdit) -> None:
    apply_form_field_font(line_edit)
    line_edit.setMinimumHeight(FORM_FIELD_MIN_HEIGHT)


def configure_combo_field(combo: QComboBox) -> None:
    apply_form_field_font(combo)
    combo.setMinimumHeight(FORM_FIELD_MIN_HEIGHT)
    line_edit = combo.lineEdit()
    if line_edit is None:
        return
    apply_form_field_font(line_edit)
    line_edit.setMinimumHeight(FORM_FIELD_MIN_HEIGHT - 2)
    line_edit.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    line_edit.setFrame(False)
