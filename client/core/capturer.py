import asyncio
import ctypes
import ctypes.wintypes
import threading
import time
import cv2
import mss
import numpy as np

class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

def get_cursor_pos():
    pt = POINT()
    ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
    return pt.x, pt.y

class ScreenCapturer(threading.Thread):
    def __init__(self, frame_queue: asyncio.Queue, loop: asyncio.AbstractEventLoop, target_fps: int = 30):
        super().__init__(daemon=True)
        self.frame_queue = frame_queue
        self.loop = loop
        self.target_fps = target_fps
        self.running = False
        self._stop_event = threading.Event()

    def run(self):
        self.running = True
        interval = 1.0 / self.target_fps
        with mss.mss() as sct:
            # Monitor 1 is the primary monitor
            mon = sct.monitors[1]
            left, top, width, height = mon["left"], mon["top"], mon["width"], mon["height"]

            while not self._stop_event.is_set():
                start_time = time.time()
                try:
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

                    # Push to asyncio queue if queue is not full (skip frame if lagging)
                    if self.frame_queue.qsize() < 2:
                        asyncio.run_coroutine_threadsafe(self.frame_queue.put(jpeg_bytes), self.loop)

                except Exception as e:
                    print(f"Error in screen capture: {e}")

                elapsed = time.time() - start_time
                sleep_time = interval - elapsed
                if sleep_time > 0:
                    time.sleep(sleep_time)

    def stop(self):
        self._stop_event.set()
        self.running = False
