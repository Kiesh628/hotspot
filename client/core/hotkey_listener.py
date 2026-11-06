import logging
from typing import Callable, Optional
import keyboard

logger = logging.getLogger("HotkeyManager")

class HotkeyManager:
    def __init__(self, on_freeze_toggle: Callable, on_kick_and_reset: Callable):
        self.on_freeze_toggle = on_freeze_toggle
        self.on_kick_and_reset = on_kick_and_reset
        self.freeze_hook = None
        self.kick_hook = None
        self.current_freeze_key: Optional[str] = None
        self.current_kick_key: Optional[str] = None

    def update_freeze_hotkey(self, key_str: Optional[str]):
        if self.freeze_hook is not None:
            try:
                keyboard.remove_hotkey(self.freeze_hook)
            except Exception:
                pass
            self.freeze_hook = None

        self.current_freeze_key = key_str
        if key_str and key_str.lower() != "none":
            try:
                self.freeze_hook = keyboard.add_hotkey(key_str, self._safe_freeze, suppress=False)
                logger.info(f"Registered freeze hotkey: {key_str}")
            except Exception as e:
                logger.warning(f"Failed to register freeze hotkey '{key_str}': {e}")

    def update_kick_hotkey(self, key_str: Optional[str]):
        if self.kick_hook is not None:
            try:
                keyboard.remove_hotkey(self.kick_hook)
            except Exception:
                pass
            self.kick_hook = None

        self.current_kick_key = key_str
        if key_str and key_str.lower() != "none":
            try:
                self.kick_hook = keyboard.add_hotkey(key_str, self._safe_kick, suppress=False)
                logger.info(f"Registered kick hotkey: {key_str}")
            except Exception as e:
                logger.warning(f"Failed to register kick hotkey '{key_str}': {e}")

    def _safe_freeze(self):
        try:
            self.on_freeze_toggle()
        except Exception as e:
            logger.error(f"Error in freeze callback: {e}")

    def _safe_kick(self):
        try:
            self.on_kick_and_reset()
        except Exception as e:
            logger.error(f"Error in kick callback: {e}")

    def stop_all(self):
        try:
            keyboard.unhook_all_hotkeys()
        except Exception:
            pass
