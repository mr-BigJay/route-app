from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QLocale, Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

from database.db import DatabaseManager
from ui.main_window import MainWindow
from ui.utils import load_vazirmatn_font


BASE_DIR = Path(__file__).resolve().parent


def load_stylesheet(app: QApplication) -> None:
    style_path = BASE_DIR / "assets" / "style.qss"
    if style_path.exists():
        assets_dir = (BASE_DIR / "assets").as_posix()
        style = style_path.read_text(encoding="utf-8").replace("@ASSETS@", assets_dir)
        app.setStyleSheet(style)


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Route")
    app.setOrganizationName("Rudsar Health Network")
    app.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
    QLocale.setDefault(QLocale(QLocale.Language.Persian, QLocale.Country.Iran))

    font_family = load_vazirmatn_font(BASE_DIR / "assets" / "fonts")
    app.setFont(QFont(font_family, 10))
    load_stylesheet(app)

    db = DatabaseManager()
    window = MainWindow(db)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
