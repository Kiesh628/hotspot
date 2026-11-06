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
    "server_url": "wss://hotspot-relay-production.up.railway.app"
}

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
