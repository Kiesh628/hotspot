from PySide6.QtCore import Qt, QPoint, QRect, QTimer
from PySide6.QtGui import QPainter, QPixmap, QImage, QColor, QFont, QKeyEvent, QMouseEvent, QWheelEvent
from PySide6.QtWidgets import QWidget, QLabel, QPushButton, QHBoxLayout, QVBoxLayout, QGraphicsOpacityEffect

class RemoteCanvas(QWidget):
    def __init__(self, connector_client, parent=None):
        super().__init__(parent)
        self.client = connector_client
        self.current_pixmap: QPixmap = QPixmap()
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent)

    def update_frame(self, jpeg_bytes: bytes):
        image = QImage.fromData(jpeg_bytes, "JPG")
        if not image.isNull():
            self.current_pixmap = QPixmap.fromImage(image)
            self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(10, 10, 12))

        if not self.current_pixmap.isNull():
            # Scale pixmap maintaining aspect ratio to fit inside canvas
            scaled = self.current_pixmap.scaled(
                self.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            # Center the scaled image
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
        
        # Calculate viewport bounds
        scaled_w = self.width()
        scaled_h = self.height()
        orig_w = self.current_pixmap.width()
        orig_h = self.current_pixmap.height()

        aspect_orig = orig_w / orig_h
        aspect_win = scaled_w / scaled_h

        if aspect_win > aspect_orig:
            # Pillarbox (black bars on left/right)
            render_h = scaled_h
            render_w = int(render_h * aspect_orig)
            offset_x = (scaled_w - render_w) // 2
            offset_y = 0
        else:
            # Letterbox (black bars on top/bottom)
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
        nx, ny = self._get_normalized_pos(event.position().x(), event.position().y())
        if nx is not None and ny is not None:
            self.client.send_input({"event": "mouse_move", "x": nx, "y": ny})
        super().mouseMoveEvent(event)

    def mousePressEvent(self, event: QMouseEvent):
        nx, ny = self._get_normalized_pos(event.position().x(), event.position().y())
        if nx is not None and ny is not None:
            btn = "left" if event.button() == Qt.MouseButton.LeftButton else \
                  "right" if event.button() == Qt.MouseButton.RightButton else "middle"
            self.client.send_input({"event": "mouse_down", "button": btn, "x": nx, "y": ny})
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        nx, ny = self._get_normalized_pos(event.position().x(), event.position().y())
        if nx is not None and ny is not None:
            btn = "left" if event.button() == Qt.MouseButton.LeftButton else \
                  "right" if event.button() == Qt.MouseButton.RightButton else "middle"
            self.client.send_input({"event": "mouse_up", "button": btn, "x": nx, "y": ny})
        super().mouseReleaseEvent(event)

    def wheelEvent(self, event: QWheelEvent):
        delta = event.angleDelta().y()
        self.client.send_input({"event": "wheel", "dy": delta})
        super().wheelEvent(event)

    def keyPressEvent(self, event: QKeyEvent):
        key = event.key()
        text = event.text()
        key_name = event.text() if event.text() else f"key_{key}"
        if key == Qt.Key.Key_Return or key == Qt.Key.Key_Enter:
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

    def keyReleaseEvent(self, event: QKeyEvent):
        key = event.key()
        key_name = event.text() if event.text() else f"key_{key}"
        if key == Qt.Key.Key_Return or key == Qt.Key.Key_Enter:
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


class ConnectorWindow(QWidget):
    def __init__(self, connector_client, nickname: str = "Friend", is_blocked: bool = False, parent=None):
        super().__init__(parent)
        self.client = connector_client
        self.nickname = nickname
        self.is_blocked = is_blocked

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

        # Sleek Top Bar with Window Controls
        top_bar = QWidget()
        top_bar.setFixedHeight(34)
        top_bar.setStyleSheet("background-color: #18181b; border-bottom: 1px solid #27272a;")
        bar_layout = QHBoxLayout(top_bar)
        bar_layout.setContentsMargins(12, 0, 8, 0)

        title_lbl = QLabel(f"Hotspot — {self.nickname}'s Screen")
        title_lbl.setStyleSheet("color: #a1a1aa; font-size: 12px; font-weight: 500;")
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

        # Remote Canvas
        self.canvas = RemoteCanvas(self.client, self)
        root_layout.addWidget(self.canvas)

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

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Position welcome popup centered at top
        if self.welcome_popup.isVisible():
            self.welcome_popup.move((self.width() - self.welcome_popup.width()) // 2, 45)
        # Position freeze banner centered near bottom
        self.freeze_banner.move((self.width() - self.freeze_banner.width()) // 2, self.height() - 60)

    def _show_welcome_popup(self, nickname: str):
        self.welcome_popup.setText(f"Connected to {nickname}")
        self.welcome_popup.adjustSize()
        self.welcome_popup.move((self.width() - self.welcome_popup.width()) // 2, 45)
        self.welcome_popup.show()
        QTimer.singleShot(4000, self.welcome_popup.hide)

    def _bind_signals(self):
        self.client.signals.frame_received.connect(self.canvas.update_frame)
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

    def closeEvent(self, event):
        self.client.disconnect()
        super().closeEvent(event)
