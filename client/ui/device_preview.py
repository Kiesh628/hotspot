import threading
import time
import cv2
import sounddevice as sd
import numpy as np
from PySide6.QtCore import Qt, QTimer, Signal, QObject
from PySide6.QtGui import QImage, QPixmap, QPainter, QColor, QFont
from PySide6.QtWidgets import QWidget, QLabel, QProgressBar, QVBoxLayout

class AudioMonitor(QObject):
    volume_changed = Signal(int) # 0 to 100

    def __init__(self, device_index=None):
        super().__init__()
        self.device_index = device_index
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
        except Exception:
            self.stream = None

    def _audio_callback(self, indata, frames, time_info, status):
        if not self.running:
            return
        # Calculate Root-Mean-Square (RMS) amplitude
        rms = np.sqrt(np.mean(indata**2))
        # Scale to 0 - 100 with sensitivity multiplier
        level = int(min(100, rms * 400))
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
        try:
            cap = cv2.VideoCapture(self.device_index, cv2.CAP_DSHOW)
            if not cap.isOpened():
                cap = cv2.VideoCapture(self.device_index)
        except Exception:
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
            time.sleep(0.06) # ~15 fps

        cap.release()

    def stop(self):
        self._stop_event.set()


class VolumeBar(QProgressBar):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setRange(0, 100)
        self.setValue(0)
        self.setTextVisible(False)
        self.setFixedHeight(8)
        self.setStyleSheet("""
            QProgressBar {
                background-color: #18181b;
                border: 1px solid #27272a;
                border-radius: 4px;
            }
            QProgressBar::chunk {
                background-color: #22c55e;
                border-radius: 3px;
            }
        """)


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
        self._show_placeholder("No Preview")

    def _show_placeholder(self, text: str):
        pixmap = QPixmap(140, 95)
        pixmap.fill(QColor("#18181b"))
        painter = QPainter(pixmap)
        painter.setPen(QColor("#71717a"))
        painter.setFont(QFont("Segoe UI", 10))
        painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, text)
        painter.end()
        self.setPixmap(pixmap)

    def set_frame(self, qimg: QImage):
        self.setPixmap(QPixmap.fromImage(qimg))
