from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends
from fastapi.middleware.cors import CORSMiddleware
from database import db
from models import Message, Room
from rooms import room_manager
from datetime import datetime
from typing import List
import json
from bson import ObjectId

app = FastAPI(title="Web Chat API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup_db_client():
    # Ensure a default room exists
    default_room = await db.rooms.find_one({"room_id": "general"})
    if not default_room:
        await db.rooms.insert_one({
            "room_id": "general",
            "name": "General Room",
            "created_by": "system",
            "is_encrypted": False,
            "created_at": datetime.utcnow(),
            "members": ["system"]
        })
    
    # Ensure E2EE demo room exists
    demo_room = await db.rooms.find_one({"room_id": "e2ee-demo"})
    if not demo_room:
        await db.rooms.insert_one({
            "room_id": "e2ee-demo",
            "name": "E2EE Demo Room",
            "created_by": "system",
            "is_encrypted": True,
            "created_at": datetime.utcnow(),
            "members": ["system"]
        })

    # Ensure Secret Room is always correctly configured
    await db.rooms.update_one(
        {"room_id": "secret-room"},
        {"$set": {
            "name": "Secret Room",
            "is_encrypted": True,
            "created_by": "system"
        }},
        upsert=True
    )

@app.get("/rooms", response_model=List[dict])
async def get_rooms():
    rooms = await db.rooms.find().to_list(100)
    for r in rooms:
        r["_id"] = str(r["_id"])
    return rooms

@app.post("/rooms")
async def create_room(room: Room):
    existing = await db.rooms.find_one({"room_id": room.room_id})
    if existing:
        return {"status": "error", "message": "Room already exists"}
    
    new_room = {
        "room_id": room.room_id,
        "name": room.name,
        "created_by": room.created_by,
        "is_encrypted": room.is_encrypted,
        "created_at": datetime.utcnow(),
        "active_users": [],
        "members": [room.created_by]
    }
    await db.rooms.insert_one(new_room)
    return {"status": "success", "room": room.room_id}

@app.delete("/rooms/{room_id}")
async def delete_room(room_id: str, user_id: str):
    if room_id == "general":
        return {"status": "error", "message": "Cannot delete general room"}
    
    room = await db.rooms.find_one({"room_id": room_id})
    if not room:
        return {"status": "error", "message": "Room not found"}
    
    if room.get("created_by") != user_id:
        return {"status": "error", "message": "Only the creator can delete this room"}
    
    await db.rooms.delete_one({"room_id": room_id})
    await db.messages.delete_many({"room_id": room_id})
    return {"status": "success", "message": "Room deleted"}

@app.post("/rooms/{room_id}/join")
async def join_room(room_id: str, user_id: str):
    room = await db.rooms.find_one({"room_id": room_id})
    if not room:
        return {"status": "error", "message": "Room not found"}
    
    if user_id not in room.get("members", []):
        await db.rooms.update_one(
            {"room_id": room_id},
            {"$addToSet": {"members": user_id}}
        )
        # Save and Broadcast join message ONLY on first join
        join_msg = {
            "room_id": room_id,
            "sender_id": "system",
            "content": f"User {user_id} joined the room",
            "timestamp": datetime.utcnow(),
            "is_system": True
        }
        await db.messages.insert_one(join_msg)
        
        # Prepare for broadcast
        join_msg["timestamp"] = join_msg["timestamp"].isoformat()
        del join_msg["_id"]
        await room_manager.broadcast(room_id, join_msg)
    
    return {"status": "success", "message": "Joined room"}

@app.post("/rooms/{room_id}/leave")
async def leave_room(room_id: str, user_id: str):
    await db.rooms.update_one(
        {"room_id": room_id},
        {"$pull": {"members": user_id}}
    )
    leave_msg = {
        "room_id": room_id,
        "sender_id": "system",
        "content": f"User {user_id} left the room",
        "timestamp": datetime.utcnow(),
        "is_system": True
    }
    await db.messages.insert_one(leave_msg)
    
    # Prepare for broadcast
    leave_msg["timestamp"] = leave_msg["timestamp"].isoformat()
    del leave_msg["_id"]
    await room_manager.broadcast(room_id, leave_msg)
    return {"status": "success", "message": "Left room"}

@app.get("/history/{room_id}", response_model=List[dict])
async def get_history(room_id: str):
    messages = await db.messages.find({"room_id": room_id}).sort("timestamp", 1).to_list(100)
    for m in messages:
        m["_id"] = str(m["_id"])
        m["timestamp"] = m["timestamp"].isoformat()
    return messages

@app.websocket("/ws/{room_id}/{user_id}")
async def websocket_endpoint(websocket: WebSocket, room_id: str, user_id: str):
    print(f"DEBUG: Connecting {user_id} to room {room_id}")
    await room_manager.connect(room_id, websocket, user_id)
    
    # Broadcast member list update
    member_update = {
        "room_id": room_id,
        "type": "member_list",
        "members": room_manager.get_active_users(room_id),
        "timestamp": datetime.utcnow().isoformat()
    }
    await room_manager.broadcast(room_id, member_update)

    try:
        while True:
            data = await websocket.receive_text()
            message_data = json.loads(data)
            print(f"DEBUG: Message from {user_id} in room {room_id}: {message_data['content']}")
            
            # Save to DB
            new_message = {
                "room_id": room_id,
                "sender_id": user_id,
                "content": message_data["content"],
                "timestamp": datetime.utcnow(),
                "is_system": False,
                "is_encrypted": message_data.get("is_encrypted", False),
                "iv": message_data.get("iv")
            }
            await db.messages.insert_one(new_message)
            
            # Broadcast
            new_message["timestamp"] = new_message["timestamp"].isoformat()
            del new_message["_id"]
            await room_manager.broadcast(room_id, new_message)
            
    except WebSocketDisconnect:
        room_manager.disconnect(room_id, websocket, user_id)
        
        # Broadcast member list update
        member_update = {
            "room_id": room_id,
            "type": "member_list",
            "members": room_manager.get_active_users(room_id),
            "timestamp": datetime.utcnow().isoformat()
        }
        await room_manager.broadcast(room_id, member_update)

@app.delete("/messages/{room_id}/{msg_id}")
async def delete_message(room_id: str, msg_id: str, user_id: str):
    res = await db.messages.delete_one({"_id": ObjectId(msg_id), "sender_id": user_id})
    if res.deleted_count > 0:
        return {"status": "success"}
    return {"status": "error", "message": "Unauthorized or not found"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
