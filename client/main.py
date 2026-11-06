import sys
import os

# Add client folder to sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.updater import check_for_updates

# Check for updates only when app is initially opened
check_for_updates()

from PySide6.QtWidgets import QApplication
from ui.main_window import MainWindow

def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Hotspot")
    app.setQuitOnLastWindowClosed(False) # Keep running in tray when windows are closed

    window = MainWindow()
    window.show()

    sys.exit(app.exec())

if __name__ == "__main__":
    main()
