import os
import random
import string
import threading
import sounddevice as sd
import cv2

from PySide6.QtCore import Qt, QSize, QTimer, QThread, Signal
from PySide6.QtGui import QIcon, QFont, QPixmap, QPainter, QColor
from PySide6.QtMultimedia import QMediaDevices
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QLabel,
    QLineEdit, QPushButton, QComboBox, QFrame, QSystemTrayIcon, QMenu, QApplication
)

from config import load_config, save_config, generate_random_code, validate_keybind_uniqueness
from ui.icons import create_eye_icon
from ui.keybind_widget import MinecraftKeybindButton
from ui.connector_window import ConnectorWindow
from ui.device_preview import AudioMonitor, CameraPreviewThread, VolumeMeter, CameraThumbnail, open_camera_capture
from core.network import ConnecteeClient, ConnectorClient
from core.capturer import ScreenCapturer
from core.media_streamer import WebcamCapturer, AudioCapturer
from core.input_simulator import InputSimulator
from core.hotkey_listener import HotkeyManager
from core.gemini import GeminiClient

class KeyVerifierThread(QThread):
    result_ready = Signal(bool, str, str)  # is_valid, message, clean_key

    def __init__(self, key: str, parent=None):
        super().__init__(parent)
        self.key = key

    def run(self):
        try:
            is_valid, msg = GeminiClient.verify_key(self.key)
            self.result_ready.emit(is_valid, msg, self.key)
        except Exception as e:
            self.result_ready.emit(False, f"Verification failed: {e}", self.key)


def create_tray_icon_pixmap() -> QPixmap:
    pixmap = QPixmap(32, 32)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setBrush(QColor("#3b82f6"))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawEllipse(2, 2, 28, 28)
    painter.setBrush(QColor("#ffffff"))
    painter.drawEllipse(11, 11, 10, 10)
    painter.end()
    return pixmap

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.config = load_config()
        self.setWindowTitle("Hotspot")
        self.setFixedSize(850, 680)

        # Ensure code exists
        if not self.config.get("saved_code"):
            self.config["saved_code"] = generate_random_code()
            save_config(self.config)

        # Core subsystems
        self.input_simulator = InputSimulator()
        self.capturer: ScreenCapturer = None
        self.webcam_capturer: WebcamCapturer = None
        self.audio_capturer: AudioCapturer = None
        self.connector_window: ConnectorWindow = None
        self.connector_client: ConnectorClient = None

        # Device previews (landing UI only)
        self.audio_monitor = AudioMonitor()
        self.cam_preview_thread = None

        # Build UI
        self._setup_style()
        self._build_ui()
        self._setup_system_tray()

        # Connectee Client
        self.connectee_client = ConnecteeClient(
            server_url=self.config["server_url"],
            code=self.config["saved_code"],
            nickname=self.config.get("nickname", "Host"),
            input_simulator=self.input_simulator
        )

        # Hotkeys
        self.hotkey_manager = HotkeyManager(
            on_freeze_toggle=self._on_hotkey_freeze,
            on_kick_and_reset=self._on_hotkey_kick,
            on_mode_toggle=self._on_hotkey_mode
        )
        self.hotkey_manager.update_freeze_hotkey(self.config.get("keybind_freeze"))
        self.hotkey_manager.update_kick_hotkey(self.config.get("keybind_kick"))
        self.hotkey_manager.update_mode_hotkey(self.config.get("keybind_mode"))

        # Bind Connectee Network Signals
        self.connectee_client.signals.registered.connect(self._on_host_registered)
        self.connectee_client.signals.connector_joined.connect(self._on_connector_joined)
        self.connectee_client.signals.code_reset.connect(self._on_host_code_reset)

        # Start Connectee Relay Connection & Screen Streamer
        self.connectee_client.start()
        self.capturer = ScreenCapturer(
            frame_queue=self.connectee_client.frame_queue,
            loop=self.connectee_client.loop,
            target_fps=30
        )
        self.capturer.start()

        # Initialize Hardware Devices (Webcam & Mic)
        self._init_hardware_devices()

    def _setup_style(self):
        self.setStyleSheet("""
            QMainWindow {
                background-color: #09090b;
            }
            QWidget {
                color: #f4f4f5;
                font-family: 'Segoe UI', system-ui, sans-serif;
            }
            QLabel {
                font-size: 13px;
            }
            QLineEdit, QComboBox {
                background-color: #18181b;
                border: 1px solid #27272a;
                border-radius: 6px;
                padding: 6px 10px;
                color: #fafafa;
                font-size: 12px;
            }
            QLineEdit:focus, QComboBox:focus {
                border-color: #3b82f6;
            }
            QComboBox::drop-down {
                border: none;
                width: 20px;
            }
            QComboBox QAbstractItemView {
                background-color: #18181b;
                color: #fafafa;
                selection-background-color: #2563eb;
                selection-color: #ffffff;
                border: 1px solid #27272a;
            }
            QPushButton.primary-btn {
                background-color: #2563eb;
                color: white;
                font-weight: 600;
                border: none;
                border-radius: 6px;
                padding: 10px 16px;
                font-size: 14px;
            }
            QPushButton.primary-btn:hover {
                background-color: #1d4ed8;
            }
            QPushButton.secondary-btn {
                background-color: #27272a;
                color: #e4e4e7;
                border: 1px solid #3f3f46;
                border-radius: 6px;
                padding: 6px 12px;
                font-size: 12px;
            }
            QPushButton.secondary-btn:hover {
                background-color: #3f3f46;
            }
        """)

    def _build_ui(self):
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(20, 16, 20, 16)
        main_layout.setSpacing(20)

        # ================= LEFT HALF: CONNECTOR =================
        left_box = QWidget()
        left_layout = QVBoxLayout(left_box)
        left_layout.setContentsMargins(10, 10, 10, 10)
        left_layout.setSpacing(10)

        conn_title = QLabel("Connect to Friend")
        conn_title.setStyleSheet("font-size: 17px; font-weight: 700; color: #60a5fa;")
        left_layout.addWidget(conn_title)

        code_lbl = QLabel("ROOM CODE")
        code_lbl.setStyleSheet("font-weight: 600; font-size: 11px; color: #71717a; letter-spacing: 1px;")
        left_layout.addWidget(code_lbl)

        self.input_code = QLineEdit()
        self.input_code.setPlaceholderText("e.g. ABCD")
        self.input_code.setMaxLength(4)
        self.input_code.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.input_code.setStyleSheet("font-size: 20px; font-weight: bold; letter-spacing: 5px;")
        self.input_code.textChanged.connect(lambda t: self.input_code.setText(t.upper()))
        left_layout.addWidget(self.input_code)

        # Gemini API Key Field
        gemini_lbl = QLabel("GEMINI API KEY (OPTIONAL AI)")
        gemini_lbl.setStyleSheet("font-weight: 600; font-size: 11px; color: #71717a; letter-spacing: 1px;")
        left_layout.addWidget(gemini_lbl)

        gemini_box = QHBoxLayout()
        self.input_api_key = QLineEdit(self.config.get("gemini_api_key", ""))
        self.input_api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.input_api_key.setPlaceholderText("Paste Gemini API Key...")
        gemini_box.addWidget(self.input_api_key)

        self.btn_toggle_key_vis = QPushButton()
        self.btn_toggle_key_vis.setFixedSize(32, 32)
        self.btn_toggle_key_vis.setIcon(create_eye_icon(False, size=18))
        self.btn_toggle_key_vis.setToolTip("Show / Hide API key")
        self.btn_toggle_key_vis.setProperty("class", "secondary-btn")
        self.btn_toggle_key_vis.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_toggle_key_vis.clicked.connect(self._toggle_key_visibility)
        gemini_box.addWidget(self.btn_toggle_key_vis)

        self.btn_verify_key = QPushButton("Verify")
        self.btn_verify_key.setProperty("class", "secondary-btn")
        self.btn_verify_key.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_verify_key.clicked.connect(self._on_verify_key_clicked)
        gemini_box.addWidget(self.btn_verify_key)
        left_layout.addLayout(gemini_box)

        self.lbl_key_status = QLabel("")
        self.lbl_key_status.setWordWrap(True)
        self.lbl_key_status.setStyleSheet("font-size: 11px;")
        if self.config.get("gemini_api_key"):
            self.lbl_key_status.setText("Saved key present (Click Verify to test)")
            self.lbl_key_status.setStyleSheet("color: #a1a1aa; font-size: 11px;")
        left_layout.addWidget(self.lbl_key_status)

        # Mode Switch Keybind for Connector
        mode_kb_layout = QHBoxLayout()
        mode_kb_lbl = QLabel("Toggle AI/Select Mode:")
        mode_kb_lbl.setStyleSheet("color: #e4e4e7; font-size: 12px;")
        self.btn_kb_mode = MinecraftKeybindButton(self.config.get("keybind_mode", "None"))
        self.btn_kb_mode.keybind_changed.connect(self._on_mode_key_changed)
        mode_kb_layout.addWidget(mode_kb_lbl)
        mode_kb_layout.addWidget(self.btn_kb_mode)
        left_layout.addLayout(mode_kb_layout)

        self.btn_connect = QPushButton("Connect")
        self.btn_connect.setProperty("class", "primary-btn")
        self.btn_connect.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_connect.clicked.connect(self._on_connect_clicked)
        left_layout.addWidget(self.btn_connect)

        self.lbl_connector_status = QLabel("")
        self.lbl_connector_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_connector_status.setStyleSheet("color: #f87171; font-size: 12px;")
        left_layout.addWidget(self.lbl_connector_status)

        left_layout.addStretch()
        main_layout.addWidget(left_box)

        # Vertical Divider
        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.VLine)
        divider.setFrameShadow(QFrame.Shadow.Sunken)
        divider.setStyleSheet("color: #27272a;")
        main_layout.addWidget(divider)

        # ================= RIGHT HALF: CONNECTEE =================
        right_box = QWidget()
        right_layout = QVBoxLayout(right_box)
        right_layout.setContentsMargins(10, 10, 10, 10)
        right_layout.setSpacing(8)

        host_title = QLabel("Your Device (Connectee)")
        host_title.setStyleSheet("font-size: 17px; font-weight: 700; color: #34d399;")
        right_layout.addWidget(host_title)

        # Nickname field
        nick_layout = QHBoxLayout()
        nick_lbl = QLabel("Nickname:")
        nick_lbl.setStyleSheet("color: #a1a1aa; font-weight: 500;")
        self.nick_input = QLineEdit(self.config.get("nickname", "Host"))
        self.nick_input.setPlaceholderText("Your Nickname")
        self.nick_input.textChanged.connect(self._on_nickname_changed)
        nick_layout.addWidget(nick_lbl)
        nick_layout.addWidget(self.nick_input)
        right_layout.addLayout(nick_layout)

        # 4-Letter Code Box
        your_code_lbl = QLabel("YOUR SHARE CODE")
        your_code_lbl.setStyleSheet("font-weight: 600; font-size: 11px; color: #71717a; letter-spacing: 1px;")
        right_layout.addWidget(your_code_lbl)

        code_box = QHBoxLayout()
        self.lbl_my_code = QLabel(self.config.get("saved_code", "----"))
        self.lbl_my_code.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_my_code.setStyleSheet("""
            background-color: #18181b;
            border: 1px dashed #3f3f46;
            border-radius: 8px;
            padding: 6px 14px;
            font-size: 22px;
            font-weight: 800;
            letter-spacing: 6px;
            color: #38bdf8;
        """)
        code_box.addWidget(self.lbl_my_code)

        btn_reset_code = QPushButton("Reset Code")
        btn_reset_code.setProperty("class", "secondary-btn")
        btn_reset_code.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_reset_code.clicked.connect(self._on_reset_code_clicked)
        code_box.addWidget(btn_reset_code)
        right_layout.addLayout(code_box)

        # Keybind Controls
        keybinds_header = QLabel("EMERGENCY KEYBINDS")
        keybinds_header.setStyleSheet("font-weight: 600; font-size: 11px; color: #71717a; letter-spacing: 1px;")
        right_layout.addWidget(keybinds_header)

        # Keybind 1: Freeze
        kb1_layout = QHBoxLayout()
        kb1_lbl = QLabel("Toggle Freeze Input:")
        kb1_lbl.setStyleSheet("color: #e4e4e7; font-size: 12px;")
        self.btn_kb_freeze = MinecraftKeybindButton(self.config.get("keybind_freeze", "None"))
        self.btn_kb_freeze.keybind_changed.connect(self._on_freeze_key_changed)
        kb1_layout.addWidget(kb1_lbl)
        kb1_layout.addWidget(self.btn_kb_freeze)
        right_layout.addLayout(kb1_layout)

        # Keybind 2: Kick & Reset
        kb2_layout = QHBoxLayout()
        kb2_lbl = QLabel("Kick All & Reset Code:")
        kb2_lbl.setStyleSheet("color: #e4e4e7; font-size: 12px;")
        self.btn_kb_kick = MinecraftKeybindButton(self.config.get("keybind_kick", "None"))
        self.btn_kb_kick.keybind_changed.connect(self._on_kick_key_changed)
        kb2_layout.addWidget(kb2_lbl)
        kb2_layout.addWidget(self.btn_kb_kick)
        right_layout.addLayout(kb2_layout)

        # Duplicate Keybind Error Label
        self.lbl_keybind_error = QLabel("")
        self.lbl_keybind_error.setStyleSheet("color: #ef4444; font-size: 11px; font-weight: bold;")
        right_layout.addWidget(self.lbl_keybind_error)

        # Hardware Devices Section
        hw_header = QLabel("HARDWARE FEED PREVIEWS")
        hw_header.setStyleSheet("font-weight: 600; font-size: 11px; color: #71717a; letter-spacing: 1px; margin-top: 4px;")
        right_layout.addWidget(hw_header)

        # Camera selector & Preview
        cam_section = QHBoxLayout()
        cam_left = QVBoxLayout()
        cam_left.addWidget(QLabel("Camera Device:"))
        self.combo_cam = QComboBox()
        self.combo_cam.currentIndexChanged.connect(self._on_camera_selected)
        cam_left.addWidget(self.combo_cam)
        cam_left.addStretch()
        cam_section.addLayout(cam_left)

        self.cam_thumbnail = CameraThumbnail()
        cam_section.addWidget(self.cam_thumbnail)
        right_layout.addLayout(cam_section)

        # Microphone selector & Volume Bar
        mic_section = QVBoxLayout()
        mic_section.addWidget(QLabel("Microphone Device:"))
        self.combo_mic = QComboBox()
        self.combo_mic.currentIndexChanged.connect(self._on_mic_selected)
        mic_section.addWidget(self.combo_mic)

        self.volume_bar = VolumeMeter()
        mic_section.addWidget(self.volume_bar)
        right_layout.addLayout(mic_section)

        # Connect volume monitor signal
        self.audio_monitor.volume_changed.connect(self.volume_bar.set_level)

        right_layout.addStretch()
        main_layout.addWidget(right_box)

    def _init_hardware_devices(self):
        # 1. Microphones
        try:
            devices = sd.query_devices()
            input_devices = []
            seen_names = set()
            default_in = sd.default.device[0] if sd.default.device[0] >= 0 else None
            default_combo_idx = 0

            for i, d in enumerate(devices):
                name = d.get("name", "").strip()
                if d.get("max_input_channels", 0) > 0 and name not in seen_names:
                    seen_names.add(name)
                    if i == default_in:
                        default_combo_idx = len(input_devices)
                    input_devices.append((i, name))

            self.combo_mic.blockSignals(True)
            self.combo_mic.clear()
            if input_devices:
                for idx, name in input_devices:
                    self.combo_mic.addItem(name, idx)
                self.combo_mic.setCurrentIndex(default_combo_idx)
                selected_mic_idx = self.combo_mic.currentData()
                self.audio_monitor.start(selected_mic_idx)
                self.connectee_client.mic_available = True
            else:
                self.combo_mic.addItem("No microphone detected", None)
                self.combo_mic.setEnabled(False)
                self.connectee_client.mic_available = False
            self.combo_mic.blockSignals(False)
        except Exception:
            self.combo_mic.addItem("No microphone detected", None)
            self.combo_mic.setEnabled(False)
            self.connectee_client.mic_available = False

        # 2. Cameras (Using QMediaDevices for instant hardware detection)
        try:
            detected_cams = []
            media_cams = QMediaDevices.videoInputs()
            if media_cams:
                for i, c in enumerate(media_cams):
                    desc = c.description().strip()
                    detected_cams.append((i, desc))
            else:
                # Fallback: probe indices 0..3
                for i in range(4):
                    cap = open_camera_capture(i)
                    if cap:
                        detected_cams.append((i, f"Camera {i}"))
                        cap.release()

            self.combo_cam.blockSignals(True)
            self.combo_cam.clear()
            working_cam_idx = None

            if detected_cams:
                for idx, name in detected_cams:
                    self.combo_cam.addItem(f"{name} ({idx})", idx)
                    if working_cam_idx is None:
                        # Test if this index can be opened
                        test_cap = open_camera_capture(idx)
                        if test_cap:
                            test_cap.release()
                            working_cam_idx = idx

                # Select first working camera
                if working_cam_idx is not None:
                    target_pos = self.combo_cam.findData(working_cam_idx)
                    if target_pos >= 0:
                        self.combo_cam.setCurrentIndex(target_pos)
                    self._start_camera_preview(working_cam_idx)
                    self.connectee_client.camera_available = True
                else:
                    self._start_camera_preview(detected_cams[0][0])
                    self.connectee_client.camera_available = True
            else:
                self.combo_cam.addItem("No camera detected", None)
                self.combo_cam.setEnabled(False)
                self.connectee_client.camera_available = False
            self.combo_cam.blockSignals(False)
        except Exception:
            self.combo_cam.addItem("No camera detected", None)
            self.combo_cam.setEnabled(False)
            self.connectee_client.camera_available = False

    def _start_camera_preview(self, cam_idx):
        if self.cam_preview_thread:
            self.cam_preview_thread.stop()
            self.cam_preview_thread.join(timeout=1.0)
            self.cam_preview_thread = None

        if cam_idx is not None:
            self.cam_preview_thread = CameraPreviewThread(
                callback=self.cam_thumbnail.set_frame,
                device_index=cam_idx
            )
            self.cam_preview_thread.start()

    def _on_camera_selected(self, index):
        cam_idx = self.combo_cam.currentData()
        if cam_idx is not None:
            self._start_camera_preview(cam_idx)

    def _on_mic_selected(self, index):
        mic_idx = self.combo_mic.currentData()
        if mic_idx is not None:
            self.audio_monitor.start(mic_idx)

    def _toggle_key_visibility(self):
        if self.input_api_key.echoMode() == QLineEdit.EchoMode.Password:
            self.input_api_key.setEchoMode(QLineEdit.EchoMode.Normal)
            self.btn_toggle_key_vis.setIcon(create_eye_icon(True, size=18))
        else:
            self.input_api_key.setEchoMode(QLineEdit.EchoMode.Password)
            self.btn_toggle_key_vis.setIcon(create_eye_icon(False, size=18))

    def _on_verify_key_clicked(self):
        raw_key = self.input_api_key.text()
        clean_key = raw_key.strip().strip('"').strip("'").strip()
        if not clean_key:
            self.lbl_key_status.setText("Please enter an API key.")
            self.lbl_key_status.setStyleSheet("color: #ef4444; font-size: 11px;")
            return

        self.btn_verify_key.setEnabled(False)
        self.lbl_key_status.setText("Verifying key with Google...")
        self.lbl_key_status.setStyleSheet("color: #38bdf8; font-size: 11px;")

        self.verifier_thread = KeyVerifierThread(clean_key, self)
        self.verifier_thread.result_ready.connect(self._on_key_verified)
        self.verifier_thread.start()

    def _on_key_verified(self, is_valid: bool, text: str, clean_key: str):
        self.btn_verify_key.setEnabled(True)
        if is_valid:
            self.config["gemini_api_key"] = clean_key
            save_config(self.config)
            self.lbl_key_status.setText("✓ Verified & Saved!")
            self.lbl_key_status.setStyleSheet("color: #22c55e; font-size: 11px; font-weight: bold;")
        else:
            self.lbl_key_status.setText(f"✕ {text}")
            self.lbl_key_status.setStyleSheet("color: #ef4444; font-size: 11px; font-weight: bold;")

    def _validate_all_keys(self) -> bool:
        k_freeze = self.config.get("keybind_freeze")
        k_kick = self.config.get("keybind_kick")
        k_mode = self.config.get("keybind_mode")
        is_valid, err = validate_keybind_uniqueness(k_freeze, k_kick, k_mode)
        if not is_valid:
            self.lbl_keybind_error.setText(err)
            return False
        self.lbl_keybind_error.setText("")
        return True

    def _on_freeze_key_changed(self, key: str):
        val = key if key != "None" else None
        self.config["keybind_freeze"] = val
        if not self._validate_all_keys():
            self.config["keybind_freeze"] = None
            self.btn_kb_freeze.set_key("None")
            return
        save_config(self.config)
        self.hotkey_manager.update_freeze_hotkey(val)

    def _on_kick_key_changed(self, key: str):
        val = key if key != "None" else None
        self.config["keybind_kick"] = val
        if not self._validate_all_keys():
            self.config["keybind_kick"] = None
            self.btn_kb_kick.set_key("None")
            return
        save_config(self.config)
        self.hotkey_manager.update_kick_hotkey(val)

    def _on_mode_key_changed(self, key: str):
        val = key if key != "None" else None
        self.config["keybind_mode"] = val
        if not self._validate_all_keys():
            self.config["keybind_mode"] = None
            self.btn_kb_mode.set_key("None")
            return
        save_config(self.config)
        self.hotkey_manager.update_mode_hotkey(val)

    def _on_hotkey_mode(self):
        if self.connector_window and self.connector_window.isVisible():
            self.connector_window.toggle_mode()

    def _setup_system_tray(self):
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(QIcon(create_tray_icon_pixmap()))
        self.tray_icon.setToolTip("Hotspot Remote Control")

        tray_menu = QMenu()
        open_action = tray_menu.addAction("Open Hotspot")
        open_action.triggered.connect(self.show_and_activate)

        reset_action = tray_menu.addAction("Reset Code & Kick")
        reset_action.triggered.connect(self._on_reset_code_clicked)

        tray_menu.addSeparator()
        exit_action = tray_menu.addAction("Exit App")
        exit_action.triggered.connect(self._full_exit)

        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self._on_tray_activated)
        self.tray_icon.show()

    def _on_tray_activated(self, reason):
        if reason in (QSystemTrayIcon.ActivationReason.Trigger, QSystemTrayIcon.ActivationReason.DoubleClick):
            self.show_and_activate()

    def show_and_activate(self):
        self.showNormal()
        self.activateWindow()
        self.raise_()

    def _on_connect_clicked(self):
        code = self.input_code.text().strip().upper()
        if len(code) != 4:
            self.lbl_connector_status.setText("Please enter a valid 4-letter code.")
            return

        self.lbl_connector_status.setText("Connecting...")
        self.connector_client = ConnectorClient(
            server_url=self.config["server_url"],
            code=code
        )
        self.connector_client.signals.joined.connect(self._on_connector_joined_success)
        self.connector_client.signals.join_error.connect(self._on_connector_join_error)
        self.connector_client.start()

    def _on_connector_joined_success(self, code: str, nickname: str, is_blocked: bool):
        self.lbl_connector_status.setText("")
        # Open fullscreen connector window
        self.connector_window = ConnectorWindow(
            connector_client=self.connector_client,
            nickname=nickname,
            is_blocked=is_blocked,
            gemini_api_key=self.config.get("gemini_api_key", ""),
            mode_key=self.config.get("keybind_mode", "None")
        )
        self.connector_window.show()

    def _on_connector_join_error(self, err_msg: str):
        self.lbl_connector_status.setText(err_msg)

    def _on_host_registered(self, code: str, nickname: str):
        self.lbl_my_code.setText(code)
        self.config["saved_code"] = code
        save_config(self.config)

    def _on_connector_joined(self, count: int):
        # 1. Stop landing preview and release camera device cleanly
        if self.cam_preview_thread:
            self.cam_preview_thread.stop()
            self.cam_preview_thread.join(timeout=1.0)
            self.cam_preview_thread = None

        # 2. Stop landing audio monitor
        self.audio_monitor.stop()

        # 3. Start streaming webcam capturer with selected camera
        cam_idx = self.combo_cam.currentData()
        if cam_idx is not None:
            self.webcam_capturer = WebcamCapturer(
                frame_queue=self.connectee_client.frame_queue,
                loop=self.connectee_client.loop,
                target_fps=15,
                camera_index=cam_idx
            )
            self.webcam_capturer.start()
            self.connectee_client.webcam_capturer = self.webcam_capturer
            self.connectee_client.camera_available = self.webcam_capturer.is_available
        else:
            self.connectee_client.camera_available = False

        # 4. Start streaming audio capturer with selected mic
        mic_idx = self.combo_mic.currentData()
        if mic_idx is not None:
            self.audio_capturer = AudioCapturer(
                audio_queue=self.connectee_client.frame_queue,
                loop=self.connectee_client.loop,
                samplerate=16000,
                mic_device_index=mic_idx
            )
            self.audio_capturer.start()
            self.connectee_client.audio_capturer = self.audio_capturer
            self.connectee_client.mic_available = self.audio_capturer.is_available
        else:
            self.connectee_client.mic_available = False

        # 5. Hide main window to system tray
        self.hide()

    def _on_host_code_reset(self, new_code: str):
        self.lbl_my_code.setText(new_code)
        self.config["saved_code"] = new_code
        save_config(self.config)

    def _on_reset_code_clicked(self):
        self.connectee_client.kick_and_reset()

    def _on_nickname_changed(self, text: str):
        nick = text.strip() or "Host"
        self.config["nickname"] = nick
        save_config(self.config)
        self.connectee_client.update_nickname(nick)

    def _on_hotkey_freeze(self):
        self.connectee_client.toggle_freeze()

    def _on_hotkey_kick(self):
        self.connectee_client.kick_and_reset()

    def closeEvent(self, event):
        event.ignore()
        self.hide()

    def _full_exit(self):
        if self.cam_preview_thread:
            self.cam_preview_thread.stop()
        self.audio_monitor.stop()
        if self.capturer:
            self.capturer.stop()
        if self.webcam_capturer:
            self.webcam_capturer.stop()
        if self.audio_capturer:
            self.audio_capturer.stop()
        if self.connectee_client:
            self.connectee_client.stop()
        if self.connector_client:
            self.connector_client.disconnect()
        if self.hotkey_manager:
            self.hotkey_manager.stop_all()
        if self.tray_icon:
            self.tray_icon.hide()
        QApplication.quit()
