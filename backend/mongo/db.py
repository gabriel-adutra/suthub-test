from typing import List, Dict, Optional
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase, AsyncIOMotorCollection
import os

class AgeGroupRepository:
	"""Repositório em memória para grupos etários.
	Este módulo é provisório para desenvolvimento inicial; depois trocaremos por MongoDB.
	"""

	def __init__(self) -> None:
		self._items: List[Dict] = []
		self._next_id: int = 1

	def list_groups(self) -> List[Dict]:
		return list(self._items)

	def _has_overlap(self, min_age: int, max_age: int) -> bool:
		for item in self._items:
			if item["min_age"] <= max_age and item["max_age"] >= min_age:
				return True
		return False

	def create_group(self, name: str, min_age: int, max_age: int) -> Dict:
		if min_age > max_age:
			raise ValueError("min_age nao pode ser maior que max_age")
		if self._has_overlap(min_age, max_age):
			raise ValueError("Intervalo de idade sobrepoe grupo existente")
		new = {
			"id": str(self._next_id),
			"name": name,
			"min_age": min_age,
			"max_age": max_age,
		}
		self._items.append(new)
		self._next_id += 1
		return new

	def delete_group(self, group_id: str) -> bool:
		for idx, item in enumerate(self._items):
			if item["id"] == group_id:
				del self._items[idx]
				return True
		return False

# Instância default para uso simples
age_group_repo = AgeGroupRepository()

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
