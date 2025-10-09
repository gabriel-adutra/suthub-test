from typing import Optional
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase, AsyncIOMotorCollection
import os


# ====== Conexão MongoDB (motor) ======
_mongo_client: Optional[AsyncIOMotorClient] = None
_mongo_db: Optional[AsyncIOMotorDatabase] = None

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "age_groups_db")

async def connect_to_mongo() -> None:
	global _mongo_client, _mongo_db
	if _mongo_client is None:
		_mongo_client = AsyncIOMotorClient(MONGO_URI)
		_mongo_db = _mongo_client[MONGO_DB_NAME]

async def close_mongo_connection() -> None:
	global _mongo_client
	if _mongo_client is not None:
		_mongo_client.close()
		_mongo_client = None

def get_db() -> AsyncIOMotorDatabase:
	if _mongo_db is None:
		raise RuntimeError("MongoDB nao inicializado. Chame connect_to_mongo no startup da API.")
	return _mongo_db

def get_collection(name: str) -> AsyncIOMotorCollection:
	return get_db()[name]
