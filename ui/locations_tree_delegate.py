from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, QSize, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QStyle, QStyledItemDelegate, QStyleOptionViewItem, QTreeWidget

from ui.utils import to_persian_digits


CATEGORY_COLORS = {
    "ستاد": "#2563EB",
    "بیمارستان": "#7C3AED",
    "مرکز درمانی": "#F97316",
    "خانه بهداشت": "#22C55E",
}


class LocationsTreeDelegate(QStyledItemDelegate):
    def __init__(self, tree: QTreeWidget, icons: dict[str, object], parent=None) -> None:
        super().__init__(parent)
        self.tree = tree
        self.icons = icons

    def sizeHint(self, option: QStyleOptionViewItem, index) -> QSize:
        data = index.data(Qt.ItemDataRole.UserRole)
        is_category = bool(data and data[0] == "category")
        return QSize(option.rect.width(), 52 if is_category else 42)

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index) -> None:
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        data = index.data(Qt.ItemDataRole.UserRole)
        if not data:
            painter.restore()
            return

        rect = option.rect.adjusted(8, 4, -8, -4)
        is_category = data[0] == "category"
        title = str(data[3])
        accent = self._accent_for_item(index, data)
        is_selected = bool(option.state & QStyle.StateFlag.State_Selected)
        is_hovered = bool(option.state & QStyle.StateFlag.State_MouseOver)

        if is_selected:
            painter.setBrush(QColor("#DBEAFE"))
            painter.setPen(QPen(QColor("#93C5FD"), 1))
        elif is_hovered:
            painter.setBrush(QColor("#F8FAFC"))
            painter.setPen(QPen(QColor("#E2E8F0"), 1))
        elif is_category:
            painter.setBrush(QColor("#FFFFFF"))
            painter.setPen(QPen(QColor("#E2E8F0"), 1))
        else:
            painter.setBrush(QColor("#FBFDFF"))
            painter.setPen(QPen(QColor("#EDF2F7"), 1))

        painter.drawRoundedRect(rect, 12, 12)

        if is_category:
            self._paint_category(painter, rect, title, accent, index, is_selected)
        else:
            self._paint_location(painter, rect, title, accent, is_selected)

        painter.restore()

    def _accent_for_item(self, index, data) -> str:
        if data[0] == "category":
            return CATEGORY_COLORS.get(str(data[3]), "#2563EB")
        item = self.tree.itemFromIndex(index)
        parent = item.parent() if item is not None else None
        if parent is None:
            return "#2563EB"
        parent_data = parent.data(0, Qt.ItemDataRole.UserRole)
        if not parent_data:
            return "#2563EB"
        return CATEGORY_COLORS.get(str(parent_data[3]), "#2563EB")

    def _paint_category(
        self,
        painter: QPainter,
        rect: QRect,
        title: str,
        accent: str,
        index,
        is_selected: bool,
    ) -> None:
        item = self.tree.itemFromIndex(index)
        child_count = item.childCount() if item is not None else 0
        expanded = item.isExpanded() if item is not None else False
        right_edge = rect.right() - 12

        if child_count > 0:
            chevron_key = "chevron_down" if expanded else "chevron_left"
            chevron = self.icons.get(chevron_key)
            if chevron is not None:
                chevron.paint(painter, QRect(right_edge - 14, rect.center().y() - 8, 16, 16))
            right_edge -= 24

        badge_text = f"{to_persian_digits(child_count)} نقطه"
        badge_font = QFont(painter.font())
        badge_font.setBold(True)
        badge_font.setPointSize(max(badge_font.pointSize() - 1, 9))
        painter.setFont(badge_font)
        badge_width = painter.fontMetrics().horizontalAdvance(badge_text) + 18
        badge_rect = QRect(right_edge - badge_width, rect.center().y() - 11, badge_width, 22)
        painter.setBrush(QColor(accent))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(badge_rect, 11, 11)
        painter.setPen(QColor("#FFFFFF"))
        painter.drawText(badge_rect, Qt.AlignmentFlag.AlignCenter, badge_text)
        right_edge -= badge_width + 10

        icon_rect = QRect(rect.left() + 12, rect.center().y() - 12, 24, 24)
        painter.setBrush(QColor(accent))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setOpacity(0.14)
        painter.drawEllipse(icon_rect.adjusted(-2, -2, 2, 2))
        painter.setOpacity(1.0)
        folder = self.icons.get("folder")
        if folder is not None:
            folder.paint(painter, icon_rect)

        title_font = QFont(painter.font())
        title_font.setBold(True)
        title_font.setPointSize(max(title_font.pointSize(), 10))
        painter.setFont(title_font)
        painter.setPen(QColor("#0F172A" if not is_selected else "#1E3A8A"))
        title_rect = QRect(icon_rect.right() + 10, rect.top(), right_edge - icon_rect.right() - 10, rect.height())
        painter.drawText(title_rect, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, title)

    def _paint_location(
        self,
        painter: QPainter,
        rect: QRect,
        title: str,
        accent: str,
        is_selected: bool,
    ) -> None:
        right_edge = rect.right() - 18
        dot_center = QPoint(right_edge, rect.center().y())
        painter.setBrush(QColor(accent))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(dot_center, 4, 4)

        pin_rect = QRect(rect.left() + 34, rect.center().y() - 9, 18, 18)
        pin = self.icons.get("pin")
        if pin is not None:
            pin.paint(painter, pin_rect)

        title_font = QFont(painter.font())
        title_font.setPointSize(max(title_font.pointSize(), 10))
        painter.setFont(title_font)
        painter.setPen(QColor("#334155" if not is_selected else "#1E3A8A"))
        title_rect = QRect(pin_rect.right() + 10, rect.top(), right_edge - pin_rect.right() - 24, rect.height())
        painter.drawText(title_rect, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, title)
