# Hotspot — Stealth Remote Desktop Sharing

A lightweight, middleman-relayed remote desktop application for Windows.

## Features
- **Relay-only Connection:** No P2P hole-punching or direct IP exposure. All data streams through the middleman relay server (Railway).
- **Dual-Pane UI:** Connector on the left (enter 4-letter code), Connectee on the right (auto-generated code + nickname + keybinds).
- **Stealth Connectee Mode:** When a friend connects, the Connectee window auto-hides to the system tray. Zero notifications, zero on-screen indicators.
- **System Tray Persistence:** Closing the window hides to the tray. Exit only via tray context menu. Single-click tray icon to restore.
- **Minecraft-style Keybinds:** Click to bind custom hotkeys or modifiers:
  1. Freeze/Unfreeze remote input (keeps video stream, alerts connector).
  2. Kick all connectors & instantly reset room code.
- **Input Arbitration:** "Last move wins" for multi-connectors; connectee retains continuous local control.

## Project Structure
- `server/`: Python WebSocket relay server (deployable to Railway).
- `client/`: Windows desktop application (PySide6, `mss`, `cv2`, `pynput`).
