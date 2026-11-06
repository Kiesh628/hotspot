import asyncio
import json
import logging
import os
import random
import string
from typing import Dict, Set
import websockets
from websockets.server import WebSocketServerProtocol

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("HotspotRelay")

class Room:
    def __init__(self, code: str, host_ws: WebSocketServerProtocol, nickname: str):
        self.code = code
        self.host_ws = host_ws
        self.nickname = nickname
        self.connectors: Set[WebSocketServerProtocol] = set()
        self.is_blocked: bool = False

rooms: Dict[str, Room] = {}
ws_to_room_code: Dict[WebSocketServerProtocol, str] = {}
ws_is_host: Dict[WebSocketServerProtocol, bool] = {}

def generate_unique_code() -> str:
    chars = string.ascii_uppercase
    for _ in range(1000):
        code = "".join(random.choices(chars, k=4))
        if code not in rooms:
            return code
    raise RuntimeError("No available 4-letter room codes")

async def handler(websocket: WebSocketServerProtocol):
    logger.info(f"New client connected from {websocket.remote_address}")
    try:
        async for raw_message in websocket:
            if isinstance(raw_message, bytes):
                # Binary message: screen frame from host to connectors
                code = ws_to_room_code.get(websocket)
                if code and code in rooms and ws_is_host.get(websocket, False):
                    room = rooms[code]
                    if room.connectors:
                        # Broadcast binary frame to all connectors concurrently
                        dead_connectors = set()
                        for c_ws in list(room.connectors):
                            try:
                                await c_ws.send(raw_message)
                            except Exception:
                                dead_connectors.add(c_ws)
                        for d in dead_connectors:
                            room.connectors.discard(d)
                continue

            # JSON control message
            try:
                data = json.loads(raw_message)
            except Exception as e:
                logger.warning(f"Invalid JSON received: {e}")
                continue

            msg_type = data.get("type")

            if msg_type == "register_host":
                # Connectee registering code & nickname
                code = data.get("code", "").upper().strip()
                nickname = data.get("nickname", "Friend").strip() or "Friend"
                
                # If code is invalid or taken, pick/assign a new unique one
                if not code or len(code) != 4 or not code.isalpha() or code in rooms:
                    code = generate_unique_code()

                room = Room(code=code, host_ws=websocket, nickname=nickname)
                rooms[code] = room
                ws_to_room_code[websocket] = code
                ws_is_host[websocket] = True

                await websocket.send(json.dumps({
                    "type": "registered",
                    "code": code,
                    "nickname": nickname
                }))
                logger.info(f"Host registered room [{code}] with nickname '{nickname}'")

            elif msg_type == "join":
                # Connector attempting to join a host by 4-letter code
                code = data.get("code", "").upper().strip()
                if code not in rooms:
                    await websocket.send(json.dumps({
                        "type": "join_error",
                        "message": f"Room '{code}' not found or host is offline."
                    }))
                    continue

                room = rooms[code]
                room.connectors.add(websocket)
                ws_to_room_code[websocket] = code
                ws_is_host[websocket] = False

                # Acknowledge connection to connector with host's nickname & current blocked state
                await websocket.send(json.dumps({
                    "type": "joined",
                    "code": code,
                    "nickname": room.nickname,
                    "is_blocked": room.is_blocked
                }))

                # Notify host internally (silent to the connectee's user UI)
                try:
                    await room.host_ws.send(json.dumps({
                        "type": "connector_joined",
                        "connector_count": len(room.connectors)
                    }))
                except Exception:
                    pass

                logger.info(f"Connector joined room [{code}]. Total connectors: {len(room.connectors)}")

            elif msg_type == "input":
                # Connector sending keyboard/mouse input to host
                code = ws_to_room_code.get(websocket)
                if not code or code not in rooms:
                    continue

                room = rooms[code]
                if room.is_blocked:
                    # Ignore input if connectee froze controls
                    continue

                # Forward input to host
                try:
                    await room.host_ws.send(raw_message)
                except Exception:
                    pass

            elif msg_type == "set_blocked":
                # Host toggling control freeze
                code = ws_to_room_code.get(websocket)
                if code and code in rooms and ws_is_host.get(websocket, False):
                    room = rooms[code]
                    room.is_blocked = bool(data.get("blocked", False))
                    status_msg = json.dumps({
                        "type": "control_blocked",
                        "blocked": room.is_blocked
                    })
                    for c_ws in list(room.connectors):
                        try:
                            await c_ws.send(status_msg)
                        except Exception:
                            pass
                    logger.info(f"Room [{code}] control blocked set to {room.is_blocked}")

            elif msg_type == "kick_and_reset":
                # Host emergency keybind triggered: kick all connectors and reset code
                code = ws_to_room_code.get(websocket)
                if code and code in rooms and ws_is_host.get(websocket, False):
                    room = rooms[code]
                    kick_msg = json.dumps({
                        "type": "kicked",
                        "message": "Host disconnected all users and reset the code."
                    })
                    for c_ws in list(room.connectors):
                        try:
                            await c_ws.send(kick_msg)
                            await c_ws.close()
                        except Exception:
                            pass
                    
                    del rooms[code]
                    new_code = generate_unique_code()
                    new_room = Room(code=new_code, host_ws=websocket, nickname=room.nickname)
                    rooms[new_code] = new_room
                    ws_to_room_code[websocket] = new_code

                    await websocket.send(json.dumps({
                        "type": "code_reset",
                        "code": new_code
                    }))
                    logger.info(f"Room [{code}] kicked all users. New room code: [{new_code}]")

            elif msg_type == "update_nickname":
                code = ws_to_room_code.get(websocket)
                if code and code in rooms and ws_is_host.get(websocket, False):
                    new_nick = data.get("nickname", "Friend").strip() or "Friend"
                    rooms[code].nickname = new_nick
                    logger.info(f"Room [{code}] nickname updated to: {new_nick}")

    except websockets.exceptions.ConnectionClosed:
        pass
    except Exception as e:
        logger.error(f"Error handling websocket: {e}")
    finally:
        # Cleanup
        code = ws_to_room_code.pop(websocket, None)
        is_host = ws_is_host.pop(websocket, False)
        if code and code in rooms:
            room = rooms[code]
            if is_host:
                # Host disconnected -> notify connectors and close room
                logger.info(f"Host disconnected from room [{code}]")
                host_disc_msg = json.dumps({
                    "type": "host_disconnected",
                    "message": "The host closed the session."
                })
                for c_ws in list(room.connectors):
                    try:
                        await c_ws.send(host_disc_msg)
                        await c_ws.close()
                    except Exception:
                        pass
                del rooms[code]
            else:
                # Connector left
                room.connectors.discard(websocket)
                logger.info(f"Connector left room [{code}]. Remaining: {len(room.connectors)}")
                try:
                    await room.host_ws.send(json.dumps({
                        "type": "connector_left",
                        "connector_count": len(room.connectors)
                    }))
                except Exception:
                    pass

async def main():
    port = int(os.environ.get("PORT", 8765))
    host = "0.0.0.0"
    logger.info(f"Starting Hotspot Relay Server on {host}:{port}...")
    async with websockets.serve(
        handler,
        host,
        port,
        max_size=10 * 1024 * 1024, # 10MB max packet for high res frames
        ping_interval=20,
        ping_timeout=20
    ):
        await asyncio.Future() # run forever

if __name__ == "__main__":
    asyncio.run(main())
