import threading
from PySide6.QtCore import Qt, QTimer, QEvent
from PySide6.QtGui import (
    QPainter, QPixmap, QImage, QColor, QFont, QKeyEvent, QMouseEvent, QWheelEvent
)
from PySide6.QtWidgets import (
    QWidget, QLabel, QPushButton, QHBoxLayout, QVBoxLayout,
    QSplitter, QTextEdit, QLineEdit, QScrollArea, QFrame, QApplication
)

from ui.icons import create_mic_icon, create_cam_icon, create_mode_icon
from core.gemini import GeminiClient
from core.media_streamer import AudioPlayer

class RemoteCanvas(QWidget):
    def __init__(self, connector_client, get_mode_fn, parent=None):
        super().__init__(parent)
        self.client = connector_client
        self.get_mode_fn = get_mode_fn # Returns "control" or "select"
        self.current_pixmap: QPixmap = QPixmap()
        self.latest_jpeg_bytes: bytes = b""
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent)

    def update_frame(self, jpeg_bytes: bytes):
        self.latest_jpeg_bytes = jpeg_bytes
        image = QImage.fromData(jpeg_bytes, "JPG")
        if not image.isNull():
            self.current_pixmap = QPixmap.fromImage(image)
            self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(10, 10, 12))

        if not self.current_pixmap.isNull():
            scaled = self.current_pixmap.scaled(
                self.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            x = (self.width() - scaled.width()) // 2
            y = (self.height() - scaled.height()) // 2
            painter.drawPixmap(x, y, scaled)
        else:
            painter.setPen(QColor(160, 160, 160))
            painter.setFont(QFont("Segoe UI", 16))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Waiting for screen stream...")

    def _get_normalized_pos(self, local_x: int, local_y: int):
        if self.current_pixmap.isNull():
            return None, None
        
        scaled_w = self.width()
        scaled_h = self.height()
        orig_w = self.current_pixmap.width()
        orig_h = self.current_pixmap.height()

        aspect_orig = orig_w / orig_h
        aspect_win = scaled_w / scaled_h

        if aspect_win > aspect_orig:
            render_h = scaled_h
            render_w = int(render_h * aspect_orig)
            offset_x = (scaled_w - render_w) // 2
            offset_y = 0
        else:
            render_w = scaled_w
            render_h = int(render_w / aspect_orig)
            offset_x = 0
            offset_y = (scaled_h - render_h) // 2

        if render_w == 0 or render_h == 0:
            return None, None

        img_x = local_x - offset_x
        img_y = local_y - offset_y

        if 0 <= img_x <= render_w and 0 <= img_y <= render_h:
            return img_x / render_w, img_y / render_h
        return None, None

    def mouseMoveEvent(self, event: QMouseEvent):
        if self.get_mode_fn() == "control":
            nx, ny = self._get_normalized_pos(event.position().x(), event.position().y())
            if nx is not None and ny is not None:
                self.client.send_input({"event": "mouse_move", "x": nx, "y": ny})
        super().mouseMoveEvent(event)

    def mousePressEvent(self, event: QMouseEvent):
        if self.get_mode_fn() == "control":
            nx, ny = self._get_normalized_pos(event.position().x(), event.position().y())
            if nx is not None and ny is not None:
                btn = "left" if event.button() == Qt.MouseButton.LeftButton else \
                      "right" if event.button() == Qt.MouseButton.RightButton else "middle"
                self.client.send_input({"event": "mouse_down", "button": btn, "x": nx, "y": ny})
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        if self.get_mode_fn() == "control":
            nx, ny = self._get_normalized_pos(event.position().x(), event.position().y())
            if nx is not None and ny is not None:
                btn = "left" if event.button() == Qt.MouseButton.LeftButton else \
                      "right" if event.button() == Qt.MouseButton.RightButton else "middle"
                self.client.send_input({"event": "mouse_up", "button": btn, "x": nx, "y": ny})
        super().mouseReleaseEvent(event)

    def wheelEvent(self, event: QWheelEvent):
        if self.get_mode_fn() == "control":
            delta = event.angleDelta().y()
            self.client.send_input({"event": "wheel", "dy": delta})
        super().wheelEvent(event)

    def keyPressEvent(self, event: QKeyEvent):
        if self.get_mode_fn() == "control":
            key = event.key()
            text = event.text()
            key_name = event.text() if event.text() else f"key_{key}"
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                key_name = "Enter"
            elif key == Qt.Key.Key_Backspace:
                key_name = "Backspace"
            elif key == Qt.Key.Key_Tab:
                key_name = "Tab"
            elif key == Qt.Key.Key_Space:
                key_name = "Space"

            self.client.send_input({
                "event": "key_down",
                "key": key_name,
                "vk": event.nativeVirtualKey(),
                "char": text
            })
            event.accept()
        else:
            super().keyPressEvent(event)

    def keyReleaseEvent(self, event: QKeyEvent):
        if self.get_mode_fn() == "control":
            key = event.key()
            key_name = event.text() if event.text() else f"key_{key}"
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                key_name = "Enter"
            elif key == Qt.Key.Key_Backspace:
                key_name = "Backspace"
            elif key == Qt.Key.Key_Tab:
                key_name = "Tab"
            elif key == Qt.Key.Key_Space:
                key_name = "Space"

            self.client.send_input({
                "event": "key_up",
                "key": key_name,
                "vk": event.nativeVirtualKey(),
                "char": event.text()
            })
            event.accept()
        else:
            super().keyReleaseEvent(event)


class WebcamBox(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(180)
        self.setStyleSheet("background-color: #000000; border-radius: 6px; border: 1px solid #27272a;")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)

    def update_frame(self, jpeg_bytes: bytes):
        img = QImage.fromData(jpeg_bytes, "JPG")
        if not img.isNull():
            scaled = QPixmap.fromImage(img).scaled(
                self.size(),
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation
            )
            self.setPixmap(scaled)


class ConnectorWindow(QWidget):
    def __init__(self, connector_client, nickname: str = "Friend", is_blocked: bool = False, gemini_api_key: str = "", mode_key: str = "None", parent=None):
        super().__init__(parent)
        self.client = connector_client
        self.nickname = nickname
        self.is_blocked = is_blocked
        self.gemini_api_key = gemini_api_key
        self.mode_key = mode_key if mode_key else "None"
        self.current_mode = "control" # "control" or "select"

        # Media states
        self.cam_state = "active" # "active", "muted", "error"
        self.mic_state = "active" # "active", "muted", "error"

        # Subsystems
        self.gemini = GeminiClient(gemini_api_key) if gemini_api_key else None
        self.audio_player = AudioPlayer()

        self.setWindowTitle(f"Hotspot — Viewing {nickname}")
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint)
        self.showMaximized()

        self._build_ui()
        self._bind_signals()
        self._show_welcome_popup(nickname)

        if self.is_blocked:
            self.freeze_banner.show()

    def _build_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # Sleek Top Window Bar
        top_bar = QWidget()
        top_bar.setFixedHeight(34)
        top_bar.setStyleSheet("background-color: #18181b; border-bottom: 1px solid #27272a;")
        bar_layout = QHBoxLayout(top_bar)
        bar_layout.setContentsMargins(12, 0, 8, 0)

        # Floating Hover Toolbar inside top bar (Left)
        self.btn_mode_toggle = QPushButton()
        self.btn_mode_toggle.setFixedSize(28, 24)
        self.btn_mode_toggle.setStyleSheet("""
            QPushButton {
                background-color: #27272a;
                border: 1px solid #3f3f46;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #3f3f46;
            }
        """)
        self._update_mode_button_ui()
        self.btn_mode_toggle.clicked.connect(self.toggle_mode)
        bar_layout.addWidget(self.btn_mode_toggle)

        title_lbl = QLabel(f"Hotspot — {self.nickname}'s Screen")
        title_lbl.setStyleSheet("color: #a1a1aa; font-size: 12px; font-weight: 500; margin-left: 8px;")
        bar_layout.addWidget(title_lbl)

        bar_layout.addStretch()

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(28, 24)
        close_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #a1a1aa;
                border: none;
                font-size: 14px;
                font-weight: bold;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #ef4444;
                color: white;
            }
        """)
        close_btn.clicked.connect(self.close)
        bar_layout.addWidget(close_btn)

        root_layout.addWidget(top_bar)

        # Splitter Layout (Canvas on Left ~82%, Sidebar on Right ~18%)
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.setStyleSheet("""
            QSplitter::handle {
                background-color: #27272a;
                width: 4px;
            }
            QSplitter::handle:hover {
                background-color: #3b82f6;
            }
        """)

        # Left Canvas
        self.canvas = RemoteCanvas(self.client, lambda: self.current_mode, self)
        self.splitter.addWidget(self.canvas)

        # Right Sidebar
        self.sidebar = QWidget()
        self.sidebar.setStyleSheet("background-color: #111113; border-left: 1px solid #1f1f23;")
        sidebar_layout = QVBoxLayout(self.sidebar)
        sidebar_layout.setContentsMargins(10, 10, 10, 10)
        sidebar_layout.setSpacing(10)

        # Media Controls Header (Discord Style: Icon-only buttons with hover tooltips)
        media_bar = QHBoxLayout()
        media_bar.setContentsMargins(0, 0, 0, 0)
        media_bar.setSpacing(8)

        ai_header = QLabel("AI Assistant")
        ai_header.setStyleSheet("color: #60a5fa; font-weight: 700; font-size: 13px;")
        media_bar.addWidget(ai_header)
        media_bar.addStretch()

        # Discord Mic button
        self.btn_mic = QPushButton()
        self.btn_mic.setFixedSize(30, 30)
        self.btn_mic.setIcon(create_mic_icon("active"))
        self.btn_mic.setToolTip("Mute connectee audio")
        self.btn_mic.setStyleSheet(self._media_btn_style("active"))
        self.btn_mic.clicked.connect(self._toggle_mic)
        media_bar.addWidget(self.btn_mic)

        # Discord Cam button
        self.btn_cam = QPushButton()
        self.btn_cam.setFixedSize(30, 30)
        self.btn_cam.setIcon(create_cam_icon("active"))
        self.btn_cam.setToolTip("Cut connectee camera feed")
        self.btn_cam.setStyleSheet(self._media_btn_style("active"))
        self.btn_cam.clicked.connect(self._toggle_cam)
        media_bar.addWidget(self.btn_cam)

        sidebar_layout.addLayout(media_bar)

        # Connectee Webcam Box
        self.webcam_box = WebcamBox(self)
        sidebar_layout.addWidget(self.webcam_box)

        # AI Chat History
        self.chat_history = QTextEdit()
        self.chat_history.setReadOnly(True)
        self.chat_history.setStyleSheet("""
            QTextEdit {
                background-color: #18181b;
                color: #e4e4e7;
                border: 1px solid #27272a;
                border-radius: 6px;
                padding: 8px;
                font-size: 12px;
                line-height: 1.4;
            }
        """)
        if not self.gemini_api_key:
            self.chat_history.setHtml("<i style='color:#71717a;'>No Gemini API key provided. AI features are disabled.</i>")
        else:
            self.chat_history.setHtml("<i style='color:#71717a;'>AI Assistant active. Type a question below to analyze the screen.</i>")
        sidebar_layout.addWidget(self.chat_history)

        # Prompt input + Ask button
        prompt_bar = QHBoxLayout()
        prompt_bar.setSpacing(6)
        self.prompt_input = QLineEdit()
        self.prompt_input.setPlaceholderText("Ask AI about this screen...")
        self.prompt_input.setStyleSheet("""
            QLineEdit {
                background-color: #18181b;
                color: #ffffff;
                border: 1px solid #27272a;
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 12px;
            }
            QLineEdit:focus {
                border-color: #3b82f6;
            }
        """)
        self.prompt_input.returnPressed.connect(self._ask_ai)
        prompt_bar.addWidget(self.prompt_input)

        self.btn_ask = QPushButton("➔")
        self.btn_ask.setFixedSize(32, 28)
        self.btn_ask.setToolTip("Ask AI (snapshot screen)")
        self.btn_ask.setStyleSheet("""
            QPushButton {
                background-color: #2563eb;
                color: white;
                font-weight: bold;
                border: none;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #1d4ed8;
            }
        """)
        self.btn_ask.clicked.connect(self._ask_ai)
        prompt_bar.addWidget(self.btn_ask)

        sidebar_layout.addLayout(prompt_bar)
        self.splitter.addWidget(self.sidebar)

        # Set initial splitter sizes (82% Canvas, 18% Sidebar)
        self.splitter.setStretchFactor(0, 82)
        self.splitter.setStretchFactor(1, 18)
        root_layout.addWidget(self.splitter)

        # Welcome popup pill
        self.welcome_popup = QLabel(f"Connected to {self.nickname}", self)
        self.welcome_popup.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.welcome_popup.setStyleSheet("""
            QLabel {
                background-color: rgba(34, 197, 94, 0.9);
                color: white;
                font-weight: bold;
                font-size: 14px;
                padding: 10px 24px;
                border-radius: 20px;
                border: 1px solid #4ade80;
            }
        """)
        self.welcome_popup.adjustSize()
        self.welcome_popup.hide()

        # Freeze warning banner
        self.freeze_banner = QLabel("⚠️ Control access is blocked by host", self)
        self.freeze_banner.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.freeze_banner.setStyleSheet("""
            QLabel {
                background-color: rgba(239, 68, 68, 0.95);
                color: white;
                font-weight: bold;
                font-size: 14px;
                padding: 8px 24px;
                border-radius: 8px;
                border: 1px solid #f87171;
            }
        """)
        self.freeze_banner.adjustSize()
        self.freeze_banner.hide()

    def _media_btn_style(self, state: str) -> str:
        border_color = "#22c55e" if state == "active" else "#ef4444" if state == "error" else "#3f3f46"
        return f"""
            QPushButton {{
                background-color: #18181b;
                border: 1px solid {border_color};
                border-radius: 6px;
            }}
            QPushButton:hover {{
                background-color: #27272a;
            }}
        """

    def _update_mode_button_ui(self):
        icon = create_mode_icon(self.current_mode)
        self.btn_mode_toggle.setIcon(icon)
        hotkey_hint = f" [{self.mode_key.upper()}]" if self.mode_key != "None" else ""
        if self.current_mode == "control":
            self.btn_mode_toggle.setToolTip(f"Mode: Remote Control (Click to switch to Select/AI Mode{hotkey_hint})")
        else:
            self.btn_mode_toggle.setToolTip(f"Mode: Select / AI (Click to switch to Remote Control{hotkey_hint})")

    def toggle_mode(self):
        self.current_mode = "select" if self.current_mode == "control" else "control"
        self._update_mode_button_ui()

    def changeEvent(self, event):
        # Auto-switch to Select Mode when app loses focus (Alt-Tab, click off, minimize)
        if event.type() == QEvent.Type.ActivationChange:
            if not self.isActiveWindow():
                if self.current_mode == "control":
                    self.current_mode = "select"
                    self._update_mode_button_ui()
        super().changeEvent(event)

    def _toggle_mic(self):
        if self.mic_state == "error":
            return
        if self.mic_state == "active":
            self.mic_state = "muted"
            self.btn_mic.setIcon(create_mic_icon("muted"))
            self.btn_mic.setToolTip("Unmute connectee microphone")
            self.audio_player.set_muted(True)
            self.client.send_media_control(camera=(self.cam_state == "active"), mic=False)
        else:
            self.mic_state = "active"
            self.btn_mic.setIcon(create_mic_icon("active"))
            self.btn_mic.setToolTip("Mute connectee microphone")
            self.audio_player.set_muted(False)
            self.client.send_media_control(camera=(self.cam_state == "active"), mic=True)
        self.btn_mic.setStyleSheet(self._media_btn_style(self.mic_state))

    def _toggle_cam(self):
        if self.cam_state == "error":
            return
        if self.cam_state == "active":
            self.cam_state = "muted"
            self.btn_cam.setIcon(create_cam_icon("muted"))
            self.btn_cam.setToolTip("Enable connectee camera feed")
            self.webcam_box.hide()
            self.client.send_media_control(camera=False, mic=(self.mic_state == "active"))
        else:
            self.cam_state = "active"
            self.btn_cam.setIcon(create_cam_icon("active"))
            self.btn_cam.setToolTip("Cut connectee camera feed")
            self.webcam_box.show()
            self.client.send_media_control(camera=True, mic=(self.mic_state == "active"))
        self.btn_cam.setStyleSheet(self._media_btn_style(self.cam_state))

    def _on_media_status(self, cam_available: bool, mic_available: bool):
        if not cam_available:
            self.cam_state = "error"
            self.btn_cam.setIcon(create_cam_icon("error"))
            self.btn_cam.setToolTip("Connectee has no camera connected")
            self.btn_cam.setStyleSheet(self._media_btn_style("error"))
            self.webcam_box.hide()
        if not mic_available:
            self.mic_state = "error"
            self.btn_mic.setIcon(create_mic_icon("error"))
            self.btn_mic.setToolTip("Connectee has no microphone connected")
            self.btn_mic.setStyleSheet(self._media_btn_style("error"))

    def _ask_ai(self):
        prompt = self.prompt_input.text().strip()
        if not prompt:
            return
        if not self.gemini:
            self.chat_history.append("<b style='color:#ef4444;'>AI:</b> No Gemini API key verified.")
            return

        jpeg_bytes = self.canvas.latest_jpeg_bytes
        if not jpeg_bytes:
            self.chat_history.append("<b style='color:#ef4444;'>AI:</b> No screen frame captured yet.")
            return

        self.chat_history.append(f"<b style='color:#60a5fa;'>You:</b> {prompt}")
        self.prompt_input.clear()
        self.chat_history.append("<i style='color:#a1a1aa;'>Thinking...</i>")

        def worker():
            answer = self.gemini.ask_screen(prompt, jpeg_bytes)
            # Remove "Thinking..." and append response
            QTimer.singleShot(0, lambda: self._append_ai_response(answer))

        threading.Thread(target=worker, daemon=True).start()

    def _append_ai_response(self, text: str):
        # Format markdown-like code or bolding
        formatted = text.replace("\n", "<br>").replace("`", "")
        self.chat_history.append(f"<b style='color:#34d399;'>AI:</b> {formatted}<br>")

    def _bind_signals(self):
        self.client.signals.screen_frame_received.connect(self.canvas.update_frame)
        self.client.signals.webcam_frame_received.connect(self.webcam_box.update_frame)
        self.client.signals.audio_chunk_received.connect(self.audio_player.play_chunk)
        self.client.signals.media_status_received.connect(self._on_media_status)
        self.client.signals.control_blocked.connect(self._on_control_blocked)
        self.client.signals.disconnected.connect(self._on_disconnected)

    def _on_control_blocked(self, is_blocked: bool):
        self.is_blocked = is_blocked
        if is_blocked:
            self.freeze_banner.move((self.width() - self.freeze_banner.width()) // 2, self.height() - 60)
            self.freeze_banner.show()
        else:
            self.freeze_banner.hide()

    def _on_disconnected(self, reason: str):
        self.close()

    def _show_welcome_popup(self, nickname: str):
        self.welcome_popup.setText(f"Connected to {nickname}")
        self.welcome_popup.adjustSize()
        self.welcome_popup.move((self.width() - self.welcome_popup.width()) // 2, 45)
        self.welcome_popup.show()
        QTimer.singleShot(4000, self.welcome_popup.hide)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.welcome_popup.isVisible():
            self.welcome_popup.move((self.width() - self.welcome_popup.width()) // 2, 45)
        self.freeze_banner.move((self.width() - self.freeze_banner.width()) // 2, self.height() - 60)

    def closeEvent(self, event):
        self.audio_player.stop()
        self.client.disconnect()
        super().closeEvent(event)
