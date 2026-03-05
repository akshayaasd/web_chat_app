from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List

class Message(BaseModel):
    room_id: str
    sender_id: str
    content: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    is_encrypted: bool = False
    iv: Optional[str] = None

class Room(BaseModel):
    room_id: str
    name: str
    created_by: str
    is_encrypted: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)
    active_users: List[str] = []
    members: List[str] = [] # List of user_ids who have joined this room
