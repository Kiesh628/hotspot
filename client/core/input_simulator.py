import ctypes
import ctypes.wintypes
import mss

# Windows Mouse Event Constants
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_MIDDLEDOWN = 0x0020
MOUSEEVENTF_MIDDLEUP = 0x0040
MOUSEEVENTF_WHEEL = 0x0800

# Windows Keyboard Event Constants
KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004

BLOCKED_SIMULATOR_VKS = {
    0x11, 0xA2, 0xA3, # VK_CONTROL, VK_LCONTROL, VK_RCONTROL
    0x12, 0xA4, 0xA5, # VK_MENU, VK_LMENU, VK_RMENU
    0x09,             # VK_TAB
    0x5B, 0x5C        # VK_LWIN, VK_RWIN
}

BLOCKED_SIMULATOR_NAMES = {
    "control", "ctrl", "alt", "altgr", "tab", "backtab", "meta", "windows", "win", "super"
}

VK_MAP = {
    "Return": 0x0D,
    "Enter": 0x0D,
    "Backspace": 0x08,
    "Tab": 0x09,
    "Escape": 0x1B,
    "Space": 0x20,
    "Delete": 0x2E,
    "Shift": 0x10,
    "Control": 0x11,
    "Alt": 0x12,
    "Left": 0x25,
    "Up": 0x26,
    "Right": 0x27,
    "Down": 0x28,
    "Home": 0x24,
    "End": 0x23,
    "PageUp": 0x21,
    "PageDown": 0x22,
    "F1": 0x70, "F2": 0x71, "F3": 0x72, "F4": 0x73, "F5": 0x74, "F6": 0x75,
    "F7": 0x76, "F8": 0x77, "F9": 0x78, "F10": 0x79, "F11": 0x7A, "F12": 0x7B
}

class InputSimulator:
    def __init__(self):
        with mss.mss() as sct:
            mon = sct.monitors[1]
            self.left = mon["left"]
            self.top = mon["top"]
            self.width = mon["width"]
            self.height = mon["height"]

    def _to_screen_coords(self, norm_x: float, norm_y: float):
        x = int(self.left + norm_x * self.width)
        y = int(self.top + norm_y * self.height)
        return max(self.left, min(x, self.left + self.width - 1)), max(self.top, min(y, self.top + self.height - 1))

    def move_mouse(self, norm_x: float, norm_y: float):
        x, y = self._to_screen_coords(norm_x, norm_y)
        ctypes.windll.user32.SetCursorPos(x, y)

    def mouse_down(self, button: str, norm_x: float, norm_y: float):
        self.move_mouse(norm_x, norm_y)
        if button == "left":
            ctypes.windll.user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
        elif button == "right":
            ctypes.windll.user32.mouse_event(MOUSEEVENTF_RIGHTDOWN, 0, 0, 0, 0)
        elif button == "middle":
            ctypes.windll.user32.mouse_event(MOUSEEVENTF_MIDDLEDOWN, 0, 0, 0, 0)

    def mouse_up(self, button: str, norm_x: float, norm_y: float):
        self.move_mouse(norm_x, norm_y)
        if button == "left":
            ctypes.windll.user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
        elif button == "right":
            ctypes.windll.user32.mouse_event(MOUSEEVENTF_RIGHTUP, 0, 0, 0, 0)
        elif button == "middle":
            ctypes.windll.user32.mouse_event(MOUSEEVENTF_MIDDLEUP, 0, 0, 0, 0)

    def mouse_wheel(self, delta_y: int):
        # 120 units per scroll step
        ctypes.windll.user32.mouse_event(MOUSEEVENTF_WHEEL, 0, 0, delta_y, 0)

    def _is_blocked(self, key_name: str, vk: int = 0, char: str = "") -> bool:
        if vk in BLOCKED_SIMULATOR_VKS:
            return True
        clean_name = key_name.strip().lower() if key_name else ""
        if clean_name in BLOCKED_SIMULATOR_NAMES:
            return True
        if char == "\t":
            return True
        try:
            from config import load_config
            cfg = load_config()
            for k in ("keybind_freeze", "keybind_kick", "keybind_mode"):
                val = cfg.get(k)
                if val and str(val).strip().lower() not in ("none", ""):
                    bind = str(val).strip().lower()
                    if clean_name == bind or (char and char.strip().lower() == bind):
                        return True
        except Exception:
            pass
        return False

    def key_down(self, key_name: str, vk: int = 0, char: str = ""):
        if self._is_blocked(key_name, vk, char):
            return
        if key_name in VK_MAP:
            vk_code = VK_MAP[key_name]
            ctypes.windll.user32.keybd_event(vk_code, 0, 0, 0)
        elif vk > 0:
            ctypes.windll.user32.keybd_event(vk, 0, 0, 0)
        elif char and len(char) == 1:
            # Send as unicode character
            code = ord(char)
            ctypes.windll.user32.keybd_event(0, code, KEYEVENTF_UNICODE, 0)

    def key_up(self, key_name: str, vk: int = 0, char: str = ""):
        if self._is_blocked(key_name, vk, char):
            return
        if key_name in VK_MAP:
            vk_code = VK_MAP[key_name]
            ctypes.windll.user32.keybd_event(vk_code, 0, KEYEVENTF_KEYUP, 0)
        elif vk > 0:
            ctypes.windll.user32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)
        elif char and len(char) == 1:
            code = ord(char)
            ctypes.windll.user32.keybd_event(0, code, KEYEVENTF_UNICODE | KEYEVENTF_KEYUP, 0)
