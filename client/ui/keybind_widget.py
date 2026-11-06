from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QPushButton
from PySide6.QtGui import QKeyEvent, QMouseEvent

class MinecraftKeybindButton(QPushButton):
    keybind_changed = Signal(str) # Emits the newly bound key (or "None")

    def __init__(self, current_key: str = "None", parent=None):
        super().__init__(parent)
        self.is_listening = False
        self.current_key = current_key if current_key else "None"
        self._update_text_and_style()
        self.clicked.connect(self._on_clicked)

    def _update_text_and_style(self):
        if self.is_listening:
            self.setText("> Press any key <")
            self.setStyleSheet("""
                QPushButton {
                    background-color: #3b82f6;
                    color: white;
                    font-weight: bold;
                    border: 2px solid #60a5fa;
                    border-radius: 6px;
                    padding: 8px 14px;
                    font-size: 13px;
                }
            """)
        else:
            display_val = self.current_key if self.current_key else "None"
            self.setText(f"[ {display_val.upper()} ]")
            self.setStyleSheet("""
                QPushButton {
                    background-color: #27272a;
                    color: #e4e4e7;
                    border: 1px solid #3f3f46;
                    border-radius: 6px;
                    padding: 8px 14px;
                    font-size: 13px;
                }
                QPushButton:hover {
                    background-color: #3f3f46;
                    border-color: #71717a;
                }
            """)

    def _on_clicked(self):
        if not self.is_listening:
            self.is_listening = True
            self.setFocus()
            self._update_text_and_style()
        else:
            self.is_listening = False
            self._update_text_and_style()

    def set_key(self, key_str: str):
        self.current_key = key_str if key_str else "None"
        self.is_listening = False
        self._update_text_and_style()

    def mousePressEvent(self, event: QMouseEvent):
        if self.is_listening and event.button() == Qt.MouseButton.RightButton:
            # Right click resets to None
            self.current_key = "None"
            self.is_listening = False
            self._update_text_and_style()
            self.keybind_changed.emit("None")
            event.accept()
            return
        super().mousePressEvent(event)

    def keyPressEvent(self, event: QKeyEvent):
        if not self.is_listening:
            super().keyPressEvent(event)
            return

        key = event.key()

        # Escape resets to None
        if key == Qt.Key.Key_Escape:
            self.current_key = "None"
            self.is_listening = False
            self._update_text_and_style()
            self.keybind_changed.emit("None")
            event.accept()
            return

        # If only a modifier is pressed alone, wait for the actual key
        if key in (Qt.Key.Key_Control, Qt.Key.Key_Shift, Qt.Key.Key_Alt, Qt.Key.Key_Meta):
            event.accept()
            return

        parts = []
        modifiers = event.modifiers()
        if modifiers & Qt.KeyboardModifier.ControlModifier:
            parts.append("ctrl")
        if modifiers & Qt.KeyboardModifier.AltModifier:
            parts.append("alt")
        if modifiers & Qt.KeyboardModifier.ShiftModifier:
            parts.append("shift")

        # Resolve key name
        key_name = ""
        # Function keys
        if Qt.Key.Key_F1 <= key <= Qt.Key.Key_F24:
            f_num = key - Qt.Key.Key_F1 + 1
            key_name = f"f{f_num}"
        elif key == Qt.Key.Key_Space:
            key_name = "space"
        elif key == Qt.Key.Key_Tab:
            key_name = "tab"
        elif key == Qt.Key.Key_Backspace:
            key_name = "backspace"
        elif key == Qt.Key.Key_Delete:
            key_name = "delete"
        elif key == Qt.Key.Key_Insert:
            key_name = "insert"
        elif key == Qt.Key.Key_Home:
            key_name = "home"
        elif key == Qt.Key.Key_End:
            key_name = "end"
        elif key == Qt.Key.Key_PageUp:
            key_name = "page up"
        elif key == Qt.Key.Key_PageDown:
            key_name = "page down"
        elif key == Qt.Key.Key_Left:
            key_name = "left"
        elif key == Qt.Key.Key_Right:
            key_name = "right"
        elif key == Qt.Key.Key_Up:
            key_name = "up"
        elif key == Qt.Key.Key_Down:
            key_name = "down"
        elif key == Qt.Key.Key_Pause:
            key_name = "pause"
        elif key == Qt.Key.Key_ScrollLock:
            key_name = "scroll lock"
        elif key == Qt.Key.Key_Print:
            key_name = "print screen"
        else:
            text = event.text().strip().lower()
            if text:
                key_name = text
            else:
                # Fallback to key code name
                key_name = chr(key).lower() if 32 <= key <= 126 else f"key_{key}"

        if key_name and key_name not in parts:
            parts.append(key_name)

        final_key = "+".join(parts)
        self.current_key = final_key
        self.is_listening = False
        self._update_text_and_style()
        self.keybind_changed.emit(final_key)
        event.accept()
