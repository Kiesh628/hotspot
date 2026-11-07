import asyncio
import ctypes
import ctypes.wintypes
import logging
import threading
import time
import cv2
import mss
import numpy as np

logger = logging.getLogger("ScreenCapturer")

class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

def get_cursor_pos():
    pt = POINT()
    ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
    return pt.x, pt.y

class ScreenCapturer(threading.Thread):
    def __init__(self, connectee_client=None, frame_queue: asyncio.Queue = None, loop: asyncio.AbstractEventLoop = None, target_fps: int = 30):
        super().__init__(daemon=True)
        self.client = connectee_client
        self.frame_queue = frame_queue
        self.loop = loop
        self.target_fps = target_fps
        self.running = False
        self._stop_event = threading.Event()

    def run(self):
        self.running = True
        interval = 1.0 / self.target_fps
        with mss.mss() as sct:
            while not self._stop_event.is_set():
                # Pause capture while no connectors are connected to save CPU & bandwidth
                if self.client is not None and not self.client.has_connectors:
                    time.sleep(0.05)
                    continue

                start_time = time.time()
                try:
                    # Monitor 1 is the primary monitor
                    mon = sct.monitors[1] if len(sct.monitors) > 1 else sct.monitors[0]
                    left, top, width, height = mon["left"], mon["top"], mon["width"], mon["height"]

                    # Capture screen
                    sct_img = sct.grab(mon)
                    frame = np.array(sct_img) # BGRA

                    # Convert to BGR
                    frame_bgr = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)

                    # Draw local cursor
                    cx, cy = get_cursor_pos()
                    # Relative to monitor
                    rel_cx, rel_cy = cx - left, cy - top
                    if 0 <= rel_cx < width and 0 <= rel_cy < height:
                        cv2.circle(frame_bgr, (rel_cx, rel_cy), 7, (0, 0, 255), -1)
                        cv2.circle(frame_bgr, (rel_cx, rel_cy), 8, (255, 255, 255), 1)

                    # Encode to JPEG
                    _, buffer = cv2.imencode(".jpg", frame_bgr, [int(cv2.IMWRITE_JPEG_QUALITY), 65])
                    # Tag with 0x01 header for screen frame
                    jpeg_bytes = b"\x01" + buffer.tobytes()

                    # Push to transmission queue
                    if self.client is not None:
                        self.client.send_packet(jpeg_bytes, max_queue_size=2)
                    elif self.frame_queue is not None and self.loop is not None and self.loop.is_running():
                        if self.frame_queue.qsize() < 2:
                            asyncio.run_coroutine_threadsafe(self.frame_queue.put(jpeg_bytes), self.loop)

                except Exception as e:
                    logger.warning(f"Error in screen capture: {e}")

                elapsed = time.time() - start_time
                sleep_time = interval - elapsed
                if sleep_time > 0:
                    time.sleep(sleep_time)

    def stop(self):
        self._stop_event.set()
        self.running = False
