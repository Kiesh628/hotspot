import logging
from typing import Callable, Optional
import keyboard

logger = logging.getLogger("HotkeyManager")

class HotkeyManager:
    def __init__(self, on_freeze_toggle: Optional[Callable] = None, on_kick_and_reset: Optional[Callable] = None, on_mode_toggle: Optional[Callable] = None):
        self.on_freeze_toggle = on_freeze_toggle
        self.on_kick_and_reset = on_kick_and_reset
        self.on_mode_toggle = on_mode_toggle
        
        self.freeze_hook = None
        self.kick_hook = None
        self.mode_hook = None

        self.current_freeze_key: Optional[str] = None
        self.current_kick_key: Optional[str] = None
        self.current_mode_key: Optional[str] = None

    def update_freeze_hotkey(self, key_str: Optional[str]):
        if self.freeze_hook is not None:
            try:
                keyboard.remove_hotkey(self.freeze_hook)
            except Exception:
                pass
            self.freeze_hook = None

        self.current_freeze_key = key_str
        if key_str and key_str.lower() != "none" and self.on_freeze_toggle:
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
        if key_str and key_str.lower() != "none" and self.on_kick_and_reset:
            try:
                self.kick_hook = keyboard.add_hotkey(key_str, self._safe_kick, suppress=False)
                logger.info(f"Registered kick hotkey: {key_str}")
            except Exception as e:
                logger.warning(f"Failed to register kick hotkey '{key_str}': {e}")

    def update_mode_hotkey(self, key_str: Optional[str]):
        if self.mode_hook is not None:
            try:
                keyboard.remove_hotkey(self.mode_hook)
            except Exception:
                pass
            self.mode_hook = None

        self.current_mode_key = key_str
        if key_str and key_str.lower() != "none" and self.on_mode_toggle:
            try:
                self.mode_hook = keyboard.add_hotkey(key_str, self._safe_mode, suppress=False)
                logger.info(f"Registered mode toggle hotkey: {key_str}")
            except Exception as e:
                logger.warning(f"Failed to register mode hotkey '{key_str}': {e}")

    def _safe_freeze(self):
        try:
            if self.on_freeze_toggle:
                self.on_freeze_toggle()
        except Exception as e:
            logger.error(f"Error in freeze callback: {e}")

    def _safe_kick(self):
        try:
            if self.on_kick_and_reset:
                self.on_kick_and_reset()
        except Exception as e:
            logger.error(f"Error in kick callback: {e}")

    def _safe_mode(self):
        try:
            if self.on_mode_toggle:
                self.on_mode_toggle()
        except Exception as e:
            logger.error(f"Error in mode callback: {e}")

    def stop_all(self):
        try:
            keyboard.unhook_all_hotkeys()
        except Exception:
            pass
