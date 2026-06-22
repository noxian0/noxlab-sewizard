"""Application entry point for NOXLAB SEWIZARD."""

from __future__ import annotations

import sys

try:
    from .paths import asset_path
except ImportError:
    from paths import asset_path


def main() -> int:
    try:
        from PySide6.QtGui import QIcon
        from PySide6.QtWidgets import QApplication
    except ImportError as exc:
        print("PySide6 is required to run the NOXLAB SEWIZARD desktop app.")
        print("Install it with: pip install -r requirements.txt")
        raise SystemExit(1) from exc

    try:
        from .ui import MainWindow
    except ImportError:
        from ui import MainWindow

    app = QApplication(sys.argv)
    app.setApplicationName("NOXLAB SEWIZARD")
    app.setOrganizationName("NoxLab")
    icon_file = asset_path("noxlab_sewizard_wand.ico")
    if not icon_file.exists():
        icon_file = asset_path("noxlab_sewizard.ico")
    if icon_file.exists():
        app.setWindowIcon(QIcon(str(icon_file)))

    window = MainWindow()
    window.resize(1280, 820)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
