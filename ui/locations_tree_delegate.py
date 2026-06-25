from __future__ import annotations

from PySide6.QtCore import QRect, QSize, Qt
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
        if not data:
            return QSize(option.rect.width(), 44)
        if data[0] == "category":
            return QSize(option.rect.width(), 54)
        if data[0] == "add_location":
            return QSize(option.rect.width(), 40)
        return QSize(option.rect.width(), 44)

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index) -> None:
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        data = index.data(Qt.ItemDataRole.UserRole)
        if not data:
            painter.restore()
            return

        rect = option.rect.adjusted(8, 4, -8, -4)
        is_category = data[0] == "category"
        is_add_row = data[0] == "add_location"
        title = str(data[3]) if len(data) > 3 else ""
        accent = self._accent_for_item(index, data)
        is_selected = bool(option.state & QStyle.StateFlag.State_Selected)
        is_hovered = bool(option.state & QStyle.StateFlag.State_MouseOver)
        item = self.tree.itemFromIndex(index)
        is_expanded = bool(item and item.isExpanded())

        if is_add_row:
            self._paint_add_location(painter, rect, accent, is_hovered)
            painter.restore()
            return

        if is_category and (is_selected or is_expanded):
            painter.setBrush(QColor("#DBEAFE"))
            painter.setPen(QPen(QColor("#93C5FD"), 1))
        elif is_selected:
            painter.setBrush(QColor("#DBEAFE"))
            painter.setPen(QPen(QColor("#93C5FD"), 1))
        elif is_hovered:
            painter.setBrush(QColor("#F8FAFC"))
            painter.setPen(QPen(QColor("#E2E8F0"), 1))
        elif is_category:
            painter.setBrush(QColor("#FFFFFF"))
            painter.setPen(QPen(QColor("#E2E8F0"), 1))
        else:
            painter.setBrush(QColor("#FFFFFF"))
            painter.setPen(QPen(QColor("#E8EDF3"), 1))

        painter.drawRoundedRect(rect, 12, 12)

        if is_category:
            self._paint_category(painter, rect, title, accent, index, is_selected or is_expanded)
        else:
            self._paint_location(painter, rect, title, accent, is_selected)

        painter.restore()

    def _accent_for_item(self, index, data) -> str:
        if data[0] == "category":
            return CATEGORY_COLORS.get(str(data[3]), "#2563EB")
        if data[0] == "add_location":
            return CATEGORY_COLORS.get(str(data[2]), "#2563EB")
        item = self.tree.itemFromIndex(index)
        parent = item.parent() if item is not None else None
        if parent is None:
            return "#2563EB"
        parent_data = parent.data(0, Qt.ItemDataRole.UserRole)
        if not parent_data:
            return "#2563EB"
        return CATEGORY_COLORS.get(str(parent_data[3]), "#2563EB")

    @staticmethod
    def _location_child_count(item) -> int:
        if item is None:
            return 0
        count = 0
        for index in range(item.childCount()):
            child = item.child(index)
            child_data = child.data(0, Qt.ItemDataRole.UserRole)
            if child_data and child_data[0] == "location":
                count += 1
        return count

    def _paint_badge(self, painter: QPainter, rect: QRect, child_count: int) -> None:
        badge_text = f"{to_persian_digits(child_count)} نقطه"
        badge_font = QFont(painter.font())
        badge_font.setBold(True)
        badge_font.setPointSize(max(badge_font.pointSize() - 1, 9))
        painter.setFont(badge_font)
        badge_width = painter.fontMetrics().horizontalAdvance(badge_text) + 18
        badge_rect = QRect(rect.left() + 12, rect.center().y() - 11, badge_width, 22)
        painter.setBrush(QColor("#F1F5F9"))
        painter.setPen(QPen(QColor("#CBD5E1"), 1))
        painter.drawRoundedRect(badge_rect, 11, 11)
        painter.setPen(QColor("#64748B"))
        painter.drawText(badge_rect, Qt.AlignmentFlag.AlignCenter, badge_text)

    def _paint_category(
        self,
        painter: QPainter,
        rect: QRect,
        title: str,
        accent: str,
        index,
        highlighted: bool,
    ) -> None:
        item = self.tree.itemFromIndex(index)
        child_count = self._location_child_count(item)
        expanded = item.isExpanded() if item is not None else False

        self._paint_badge(painter, rect, child_count)

        cursor_x = rect.right() - 12
        icon_size = 28
        icon_rect = QRect(cursor_x - icon_size, rect.center().y() - icon_size // 2, icon_size, icon_size)
        painter.setBrush(QColor(accent))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setOpacity(0.16)
        painter.drawRoundedRect(icon_rect, 8, 8)
        painter.setOpacity(1.0)
        folder = self.icons.get("folder")
        if folder is not None:
            folder.paint(
                painter,
                QRect(icon_rect.left() + 4, icon_rect.top() + 4, icon_size - 8, icon_size - 8),
            )
        cursor_x = icon_rect.left() - 12

        title_font = QFont(painter.font())
        title_font.setBold(True)
        title_font.setPointSize(max(title_font.pointSize(), 10))
        painter.setFont(title_font)
        painter.setPen(QColor("#1E3A8A" if highlighted else "#0F172A"))
        title_width = painter.fontMetrics().horizontalAdvance(title)
        title_rect = QRect(cursor_x - title_width, rect.top(), title_width, rect.height())
        painter.drawText(title_rect, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, title)
        cursor_x = title_rect.left() - 8

        if child_count > 0 or (item is not None and item.childCount() > 0):
            chevron_key = "chevron_down" if expanded else "chevron_right"
            chevron = self.icons.get(chevron_key)
            if chevron is not None:
                chevron.paint(painter, QRect(cursor_x - 16, rect.center().y() - 8, 16, 16))

    def _paint_location(
        self,
        painter: QPainter,
        rect: QRect,
        title: str,
        accent: str,
        is_selected: bool,
    ) -> None:
        cursor_x = rect.right() - 14
        pin = self.icons.get("pin")
        pin_size = 18
        if pin is not None:
            pin.paint(painter, QRect(cursor_x - pin_size, rect.center().y() - pin_size // 2, pin_size, pin_size))
        cursor_x -= pin_size + 10

        title_font = QFont(painter.font())
        title_font.setPointSize(max(title_font.pointSize(), 10))
        painter.setFont(title_font)
        painter.setPen(QColor("#1E3A8A" if is_selected else "#334155"))
        title_width = painter.fontMetrics().horizontalAdvance(title)
        title_rect = QRect(cursor_x - title_width, rect.top(), title_width, rect.height())
        painter.drawText(title_rect, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, title)

    def _paint_add_location(
        self,
        painter: QPainter,
        rect: QRect,
        accent: str,
        is_hovered: bool,
    ) -> None:
        painter.setBrush(QColor("#EFF6FF" if is_hovered else "#F8FAFC"))
        painter.setPen(QPen(QColor("#93C5FD"), 1, Qt.PenStyle.DashLine))
        painter.drawRoundedRect(rect, 10, 10)

        plus_size = 22
        plus_rect = QRect(rect.right() - plus_size - 12, rect.center().y() - plus_size // 2, plus_size, plus_size)
        painter.setBrush(QColor(accent))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(plus_rect)

        plus_font = QFont(painter.font())
        plus_font.setBold(True)
        plus_font.setPointSize(12)
        painter.setFont(plus_font)
        painter.setPen(QColor("#FFFFFF"))
        painter.drawText(plus_rect, Qt.AlignmentFlag.AlignCenter, "+")

        label = "افزودن نقطه"
        label_font = QFont(painter.font())
        label_font.setPointSize(max(label_font.pointSize(), 10))
        painter.setFont(label_font)
        painter.setPen(QColor("#2563EB" if is_hovered else "#475569"))
        label_width = painter.fontMetrics().horizontalAdvance(label)
        label_rect = QRect(plus_rect.left() - label_width - 10, rect.top(), label_width, rect.height())
        painter.drawText(label_rect, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, label)
