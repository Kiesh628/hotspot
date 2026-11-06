import asyncio
import threading
import time
import cv2
import sounddevice as sd
import numpy as np
import logging

logger = logging.getLogger("MediaStreamer")

class WebcamCapturer(threading.Thread):
    def __init__(self, frame_queue: asyncio.Queue, loop: asyncio.AbstractEventLoop, target_fps: int = 15, camera_index: int = 0):
        super().__init__(daemon=True)
        self.frame_queue = frame_queue
        self.loop = loop
        self.target_fps = target_fps
        self.camera_index = camera_index
        self._stop_event = threading.Event()
        self.is_enabled = True
        self.is_available = False

        # Probe camera
        try:
            cap = cv2.VideoCapture(self.camera_index, cv2.CAP_DSHOW)
            if not cap.isOpened():
                cap = cv2.VideoCapture(self.camera_index)
            if cap.isOpened():
                ret, _ = cap.read()
                self.is_available = bool(ret)
            cap.release()
        except Exception:
            self.is_available = False

    def run(self):
        if not self.is_available:
            return

        try:
            cap = cv2.VideoCapture(self.camera_index, cv2.CAP_DSHOW)
            if not cap.isOpened():
                cap = cv2.VideoCapture(self.camera_index)
        except Exception:
            return

        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 320)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)
        interval = 1.0 / self.target_fps

        while not self._stop_event.is_set():
            start_time = time.time()
            if self.is_enabled:
                ret, frame = cap.read()
                if ret:
                    # Resize to compact 320x240
                    frame_small = cv2.resize(frame, (320, 240))
                    _, buffer = cv2.imencode(".jpg", frame_small, [int(cv2.IMWRITE_JPEG_QUALITY), 55])
                    # 0x02 header for webcam
                    tagged_packet = b"\x02" + buffer.tobytes()
                    if self.frame_queue.qsize() < 4:
                        asyncio.run_coroutine_threadsafe(self.frame_queue.put(tagged_packet), self.loop)

            elapsed = time.time() - start_time
            sleep_time = interval - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

        cap.release()

    def set_enabled(self, enabled: bool):
        self.is_enabled = enabled

    def stop(self):
        self._stop_event.set()


class AudioCapturer:
    def __init__(self, audio_queue: asyncio.Queue, loop: asyncio.AbstractEventLoop, samplerate: int = 16000, mic_device_index=None):
        self.audio_queue = audio_queue
        self.loop = loop
        self.samplerate = samplerate
        self.mic_device_index = mic_device_index
        self.is_enabled = True
        self.is_available = False
        self.stream = None

        # Check for input device
        try:
            devices = sd.query_devices()
            input_devices = [d for d in devices if d.get("max_input_channels", 0) > 0]
            self.is_available = len(input_devices) > 0
        except Exception:
            self.is_available = False

    def start(self):
        if not self.is_available:
            return
        try:
            self.stream = sd.InputStream(
                device=self.mic_device_index,
                samplerate=self.samplerate,
                channels=1,
                dtype="int16",
                blocksize=1600, # 100ms chunks
                callback=self._audio_callback
            )
            self.stream.start()
        except Exception as e:
            logger.warning(f"Failed to start audio input stream: {e}")
            self.is_available = False

    def _audio_callback(self, indata, frames, time_info, status):
        if self.is_enabled and status == 0:
            # 0x03 header for mic audio
            raw_bytes = indata.tobytes()
            tagged_packet = b"\x03" + raw_bytes
            if self.audio_queue.qsize() < 10:
                asyncio.run_coroutine_threadsafe(self.audio_queue.put(tagged_packet), self.loop)

    def set_enabled(self, enabled: bool):
        self.is_enabled = enabled

    def stop(self):
        if self.stream:
            try:
                self.stream.stop()
                self.stream.close()
            except Exception:
                pass


class AudioPlayer:
    def __init__(self, samplerate: int = 16000):
        self.samplerate = samplerate
        self.is_muted = False
        self.stream = None
        self.is_available = False

        try:
            devices = sd.query_devices()
            output_devices = [d for d in devices if d.get("max_output_channels", 0) > 0]
            self.is_available = len(output_devices) > 0
            if self.is_available:
                self.stream = sd.OutputStream(
                    samplerate=self.samplerate,
                    channels=1,
                    dtype="int16"
                )
                self.stream.start()
        except Exception as e:
            logger.warning(f"Audio output unavailable: {e}")
            self.is_available = False

    def play_chunk(self, raw_bytes: bytes):
        if not self.is_muted and self.is_available and self.stream:
            try:
                data = np.frombuffer(raw_bytes, dtype=np.int16)
                self.stream.write(data)
            except Exception:
                pass

    def set_muted(self, muted: bool):
        self.is_muted = muted

    def stop(self):
        if self.stream:
            try:
                self.stream.stop()
                self.stream.close()
            except Exception:
                pass
