import sys
import os

# Add client folder to sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.updater import check_for_updates

# Check for updates only when app is initially opened
check_for_updates()

from PySide6.QtWidgets import QApplication
from core.single_instance import SingleInstance
from ui.main_window import MainWindow

def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Hotspot")
    app.setQuitOnLastWindowClosed(False) # Keep running in tray when windows are closed

    # Discord-style single instance lock
    single_inst = SingleInstance(app)
    if single_inst.is_already_running():
        # Another instance is already active: it was instructed to restore to front
        sys.exit(0)

    window = MainWindow()
    single_inst.activate_requested.connect(window.show_and_activate)
    window.show()

    sys.exit(app.exec())

if __name__ == "__main__":
    main()
