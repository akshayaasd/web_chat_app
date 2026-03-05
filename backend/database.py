from motor.motor_asyncio import AsyncIOMotorClient
import os

MONGODB_URL = os.environ.get("MONGODB_URL", "mongodb://localhost:27017")
DATABASE_NAME = "chat_app"

client = AsyncIOMotorClient(MONGODB_URL)
db = client[DATABASE_NAME]

async def get_db():
    return db
