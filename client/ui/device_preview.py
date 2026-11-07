import threading
import time
import cv2
import sounddevice as sd
import numpy as np
from PySide6.QtCore import Qt, QTimer, Signal, QObject, QRectF
from PySide6.QtGui import QImage, QPixmap, QPainter, QColor, QFont, QLinearGradient, QPen
from PySide6.QtWidgets import QWidget, QLabel

def open_camera_capture(index: int):
    """
    Tries opening a camera using DirectShow first, then Media Foundation, then Any.
    Returns the opened VideoCapture or None.
    """
    for backend in (cv2.CAP_DSHOW, cv2.CAP_MSMF, cv2.CAP_ANY):
        try:
            cap = cv2.VideoCapture(index, backend)
            if cap.isOpened():
                ret, _ = cap.read()
                if ret:
                    return cap
                cap.release()
        except Exception:
            pass
    return None

class AudioMonitor(QObject):
    volume_changed = Signal(int) # 0 to 100

    def __init__(self):
        super().__init__()
        self.device_index = None
        self.stream = None
        self.running = False

    def start(self, device_index=None):
        self.stop()
        self.device_index = device_index
        self.running = True
        try:
            self.stream = sd.InputStream(
                device=self.device_index,
                channels=1,
                samplerate=16000,
                blocksize=1024,
                callback=self._audio_callback
            )
            self.stream.start()
        except Exception as e:
            self.stream = None

    def _audio_callback(self, indata, frames, time_info, status):
        if not self.running:
            return
        # Calculate Root-Mean-Square (RMS) amplitude
        rms = np.sqrt(np.mean(indata**2))
        if rms > 0.0001:
            # Decibel-based sensitivity scaling (maps -55 dB .. -15 dB to 0% .. 100%)
            db = 20 * np.log10(rms)
            level = int(np.clip((db + 55) * (100.0 / 40.0), 0, 100))
        else:
            level = 0
        self.volume_changed.emit(level)

    def stop(self):
        self.running = False
        if self.stream:
            try:
                self.stream.stop()
                self.stream.close()
            except Exception:
                pass
            self.stream = None


class CameraPreviewThread(threading.Thread):
    def __init__(self, callback, device_index=0):
        super().__init__(daemon=True)
        self.callback = callback
        self.device_index = device_index
        self._stop_event = threading.Event()

    def run(self):
        cap = open_camera_capture(self.device_index)
        if not cap or not cap.isOpened():
            return

        while not self._stop_event.is_set() and cap.isOpened():
            ret, frame = cap.read()
            if ret:
                # Resize to thumbnail
                small = cv2.resize(frame, (140, 95))
                # Convert BGR to RGB
                rgb = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)
                h, w, ch = rgb.shape
                qimg = QImage(rgb.data, w, h, ch * w, QImage.Format.Format_RGB888).copy()
                self.callback(qimg)
            time.sleep(0.05) # ~20 fps

        cap.release()

    def stop(self):
        self._stop_event.set()


class VolumeMeter(QWidget):
    """
    Smooth, custom-painted audio volume level meter with animated decay.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(10)
        self.current_level = 0.0
        self.target_level = 0.0

        # Smooth animation timer (30 fps)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._animate_decay)
        self.timer.start(33)

    def set_level(self, level: int):
        self.target_level = float(level)
        if self.target_level > self.current_level:
            self.current_level = self.target_level
        self.update()

    def _animate_decay(self):
        if self.current_level > self.target_level:
            self.current_level = max(self.target_level, self.current_level - 4.0)
            self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Track background
        bg_rect = QRectF(0, 0, self.width(), self.height())
        painter.setBrush(QColor("#18181b"))
        painter.setPen(QPen(QColor("#27272a"), 1))
        painter.drawRoundedRect(bg_rect, 4, 4)

        # Active fill width
        fill_width = (self.width() * self.current_level) / 100.0
        if fill_width > 2:
            fill_rect = QRectF(1, 1, fill_width - 2, self.height() - 2)
            gradient = QLinearGradient(0, 0, self.width(), 0)
            gradient.setColorAt(0.0, QColor("#22c55e")) # Green
            gradient.setColorAt(0.7, QColor("#4ade80")) # Light green
            gradient.setColorAt(0.9, QColor("#eab308")) # Yellow
            gradient.setColorAt(1.0, QColor("#ef4444")) # Red peak

            painter.setBrush(gradient)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(fill_rect, 3, 3)

        painter.end()


class CameraThumbnail(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(140, 95)
        self.setStyleSheet("""
            background-color: #18181b;
            border: 1px solid #27272a;
            border-radius: 6px;
        """)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.show_placeholder("No Preview")

    def show_placeholder(self, text: str):
        pixmap = QPixmap(140, 95)
        pixmap.fill(QColor("#18181b"))
        painter = QPainter(pixmap)
        painter.setPen(QColor("#71717a"))
        painter.setFont(QFont("Segoe UI", 9))
        painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, text)
        painter.end()
        self.setPixmap(pixmap)

    def set_frame(self, qimg: QImage):
        self.setPixmap(QPixmap.fromImage(qimg))
