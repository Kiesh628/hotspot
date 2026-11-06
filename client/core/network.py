import asyncio
import json
import logging
import threading
from typing import Callable, Optional
import websockets
from PySide6.QtCore import QObject, Signal

logger = logging.getLogger("HotspotNetwork")

class ConnecteeSignals(QObject):
    registered = Signal(str, str) # code, nickname
    connector_joined = Signal(int) # count (used to auto-hide UI to tray)
    code_reset = Signal(str) # new_code
    connection_status = Signal(bool, str) # is_connected, message

class ConnectorSignals(QObject):
    joined = Signal(str, str, bool) # code, nickname, is_blocked
    join_error = Signal(str) # error_msg
    frame_received = Signal(bytes) # binary jpeg bytes
    control_blocked = Signal(bool) # is_blocked
    disconnected = Signal(str) # reason

class ConnecteeClient:
    def __init__(self, server_url: str, code: str, nickname: str, input_simulator):
        self.server_url = server_url
        self.code = code
        self.nickname = nickname
        self.input_simulator = input_simulator
        self.signals = ConnecteeSignals()
        
        self.ws = None
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        self.thread: Optional[threading.Thread] = None
        self.frame_queue: Optional[asyncio.Queue] = None
        self.running = False
        self.is_locally_blocked = False

    def start(self):
        self.running = True
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()

    def _run_loop(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.frame_queue = asyncio.Queue(maxsize=5)
        self.loop.run_until_complete(self._connection_manager())

    async def _connection_manager(self):
        while self.running:
            try:
                self.signals.connection_status.emit(False, "Connecting to relay...")
                async with websockets.connect(
                    self.server_url,
                    max_size=10 * 1024 * 1024,
                    ping_interval=20,
                    ping_timeout=20
                ) as ws:
                    self.ws = ws
                    self.signals.connection_status.emit(True, "Connected to relay")
                    
                    # Register host
                    await ws.send(json.dumps({
                        "type": "register_host",
                        "code": self.code,
                        "nickname": self.nickname
                    }))

                    # Run incoming message reader & frame sender concurrently
                    reader_task = asyncio.create_task(self._reader(ws))
                    sender_task = asyncio.create_task(self._frame_sender(ws))
                    
                    done, pending = await asyncio.wait(
                        [reader_task, sender_task],
                        return_when=asyncio.FIRST_COMPLETED
                    )
                    for task in pending:
                        task.cancel()

            except Exception as e:
                logger.error(f"Connectee connection error: {e}")
                self.signals.connection_status.emit(False, f"Connection error: {e}")
            
            if self.running:
                await asyncio.sleep(3) # Retry delay

    async def _reader(self, ws):
        async for raw_message in ws:
            if isinstance(raw_message, str):
                try:
                    data = json.loads(raw_message)
                except Exception:
                    continue

                msg_type = data.get("type")
                if msg_type == "registered":
                    self.code = data.get("code", self.code)
                    self.signals.registered.emit(self.code, self.nickname)
                elif msg_type == "connector_joined":
                    cnt = data.get("connector_count", 1)
                    self.signals.connector_joined.emit(cnt)
                elif msg_type == "code_reset":
                    self.code = data.get("code", self.code)
                    self.signals.code_reset.emit(self.code)
                elif msg_type == "input":
                    if not self.is_locally_blocked:
                        self._handle_remote_input(data)

    def _handle_remote_input(self, data: dict):
        event = data.get("event")
        try:
            if event == "mouse_move":
                self.input_simulator.move_mouse(data["x"], data["y"])
            elif event == "mouse_down":
                self.input_simulator.mouse_down(data["button"], data["x"], data["y"])
            elif event == "mouse_up":
                self.input_simulator.mouse_up(data["button"], data["x"], data["y"])
            elif event == "wheel":
                self.input_simulator.mouse_wheel(data.get("dy", 0))
            elif event == "key_down":
                self.input_simulator.key_down(data.get("key", ""), data.get("vk", 0), data.get("char", ""))
            elif event == "key_up":
                self.input_simulator.key_up(data.get("key", ""), data.get("vk", 0), data.get("char", ""))
        except Exception as e:
            logger.warning(f"Error handling simulated input: {e}")

    async def _frame_sender(self, ws):
        while self.running:
            frame_bytes = await self.frame_queue.get()
            try:
                await ws.send(frame_bytes)
            except Exception as e:
                logger.warning(f"Error sending frame: {e}")
                break

    def toggle_freeze(self) -> bool:
        self.is_locally_blocked = not self.is_locally_blocked
        if self.ws and self.loop and self.loop.is_running():
            asyncio.run_coroutine_threadsafe(
                self.ws.send(json.dumps({
                    "type": "set_blocked",
                    "blocked": self.is_locally_blocked
                })),
                self.loop
            )
        return self.is_locally_blocked

    def kick_and_reset(self):
        if self.ws and self.loop and self.loop.is_running():
            asyncio.run_coroutine_threadsafe(
                self.ws.send(json.dumps({"type": "kick_and_reset"})),
                self.loop
            )

    def update_nickname(self, nickname: str):
        self.nickname = nickname
        if self.ws and self.loop and self.loop.is_running():
            asyncio.run_coroutine_threadsafe(
                self.ws.send(json.dumps({
                    "type": "update_nickname",
                    "nickname": nickname
                })),
                self.loop
            )

    def stop(self):
        self.running = False
        if self.loop and self.loop.is_running():
            self.loop.stop()


class ConnectorClient:
    def __init__(self, server_url: str, code: str):
        self.server_url = server_url
        self.code = code.upper().strip()
        self.signals = ConnectorSignals()
        self.ws = None
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        self.thread: Optional[threading.Thread] = None
        self.running = False

    def start(self):
        self.running = True
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()

    def _run_loop(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.loop.run_until_complete(self._session())

    async def _session(self):
        try:
            async with websockets.connect(
                self.server_url,
                max_size=10 * 1024 * 1024,
                ping_interval=20,
                ping_timeout=20
            ) as ws:
                self.ws = ws
                # Join room
                await ws.send(json.dumps({
                    "type": "join",
                    "code": self.code
                }))

                async for raw_message in ws:
                    if isinstance(raw_message, bytes):
                        # Video frame
                        self.signals.frame_received.emit(raw_message)
                        continue

                    try:
                        data = json.loads(raw_message)
                    except Exception:
                        continue

                    msg_type = data.get("type")
                    if msg_type == "joined":
                        self.signals.joined.emit(
                            data.get("code", self.code),
                            data.get("nickname", "Friend"),
                            bool(data.get("is_blocked", False))
                        )
                    elif msg_type == "join_error":
                        self.signals.join_error.emit(data.get("message", "Failed to join room"))
                        break
                    elif msg_type == "control_blocked":
                        self.signals.control_blocked.emit(bool(data.get("blocked", False)))
                    elif msg_type == "kicked":
                        self.signals.disconnected.emit(data.get("message", "Host kicked all users."))
                        break
                    elif msg_type == "host_disconnected":
                        self.signals.disconnected.emit("Host ended the session.")
                        break

        except Exception as e:
            self.signals.join_error.emit(f"Connection failed: {e}")
        finally:
            self.running = False

    def send_input(self, payload: dict):
        if self.ws and self.loop and self.loop.is_running():
            msg = json.dumps({"type": "input", **payload})
            asyncio.run_coroutine_threadsafe(self.ws.send(msg), self.loop)

    def disconnect(self):
        self.running = False
        if self.loop and self.loop.is_running():
            self.loop.stop()
