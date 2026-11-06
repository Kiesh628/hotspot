import json
import os
import random
import string
from pathlib import Path

CONFIG_DIR = Path.home() / ".hotspot"
CONFIG_FILE = CONFIG_DIR / "config.json"

def generate_random_code() -> str:
    return "".join(random.choices(string.ascii_uppercase, k=4))

DEFAULT_CONFIG = {
    "nickname": "Host",
    "saved_code": "",
    "keybind_freeze": None,
    "keybind_kick": None,
    "keybind_mode": None,
    "gemini_api_key": "",
    "server_url": "wss://hotspot-relay-production.up.railway.app"
}

def validate_keybind_uniqueness(freeze_key, kick_key, mode_key) -> tuple[bool, str]:
    """
    Checks that none of the active keybinds collide.
    'None' is allowed to be shared.
    """
    keys = [
        ("Freeze Control", freeze_key),
        ("Kick & Reset", kick_key),
        ("Mode Switch", mode_key)
    ]
    seen = {}
    for name, k in keys:
        if k and k.lower() != "none":
            clean_k = k.lower().strip()
            if clean_k in seen:
                return False, f"'{k.upper()}' is already assigned to {seen[clean_k]}!"
            seen[clean_k] = name
    return True, ""

def load_config() -> dict:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if not CONFIG_FILE.exists():
        cfg = DEFAULT_CONFIG.copy()
        cfg["saved_code"] = generate_random_code()
        save_config(cfg)
        return cfg
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            # Ensure all keys exist
            for k, v in DEFAULT_CONFIG.items():
                if k not in data:
                    data[k] = v
            if not data.get("saved_code") or len(data["saved_code"]) != 4:
                data["saved_code"] = generate_random_code()
                save_config(data)
            return data
    except Exception:
        cfg = DEFAULT_CONFIG.copy()
        cfg["saved_code"] = generate_random_code()
        save_config(cfg)
        return cfg

def save_config(cfg: dict):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
    except Exception as e:
        print(f"Failed to save config: {e}")
