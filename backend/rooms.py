from typing import Dict, List, Set
from fastapi import WebSocket

class RoomManager:
    def __init__(self):
        # room_id -> set of active WebSockets
        self.active_connections: Dict[str, Set[WebSocket]] = {}
        # room_id -> list of user_ids
        self.room_users: Dict[str, Set[str]] = {}

    async def connect(self, room_id: str, websocket: WebSocket, user_id: str):
        await websocket.accept()
        if room_id not in self.active_connections:
            self.active_connections[room_id] = set()
            self.room_users[room_id] = set()
        
        self.active_connections[room_id].add(websocket)
        self.room_users[room_id].add(user_id)

    def disconnect(self, room_id: str, websocket: WebSocket, user_id: str):
        if room_id in self.active_connections:
            self.active_connections[room_id].remove(websocket)
            # Find if user has other connections in the same room
            # (In case of multi-tab, user_id might still be present)
            # For simplicity, we'll just check if connections is empty
            if not self.active_connections[room_id]:
                del self.active_connections[room_id]
        
        # We need a better way to handle user_id in multi-tab
        # For now, let's keep it simple. Real multi-tab support
        # usually involves session tracking.

    async def broadcast(self, room_id: str, message: dict):
        if room_id in self.active_connections:
            for connection in self.active_connections[room_id]:
                await connection.send_json(message)

    def get_active_users(self, room_id: str) -> List[str]:
        return list(self.room_users.get(room_id, set()))

room_manager = RoomManager()
