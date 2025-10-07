from typing import List
from fastapi import FastAPI, status, HTTPException
import logging
import uvicorn
from bson import ObjectId
from backend.mongo.db import connect_to_mongo, close_mongo_connection, get_collection

app = FastAPI(title="Age Groups API", version="1.0.0")

# Conexão MongoDB no ciclo de vida da aplicação
@app.on_event("startup")
async def on_startup() -> None:
	await connect_to_mongo()

@app.on_event("shutdown")
async def on_shutdown() -> None:
	await close_mongo_connection()

@app.get("/")
async def root() -> dict:
	return {"status": "ok"}

# Endpoints Age Groups (prefixo /api/v1)
COLLECTION_NAME = "age_groups"


#########
@app.post("/api/v1/age-groups", status_code=status.HTTP_201_CREATED)
async def create_age_group(payload: dict) -> dict:
	name = payload.get("name")
	min_age = payload.get("min_age")
	max_age = payload.get("max_age")
	if name is None or min_age is None or max_age is None:
		raise HTTPException(status_code=400, detail="Campos obrigatórios: name, min_age, max_age")
	if not isinstance(min_age, int) or not isinstance(max_age, int):
		raise HTTPException(status_code=400, detail="min_age e max_age devem ser inteiros")
	if min_age > max_age:
		raise HTTPException(status_code=400, detail="min_age não pode ser maior que max_age")

	coll = get_collection(COLLECTION_NAME)
	# Verificar sobreposição de intervalos existentes: [min, max] com [min_age, max_age]
	overlap = await coll.find_one({
		"$expr": {
			"$and": [
				{"$lte": ["$min_age", max_age]},
				{"$gte": ["$max_age", min_age]},
			]
		}
	})
	if overlap:
		raise HTTPException(status_code=409, detail="Intervalo de idade sobrepõe grupo existente")

	doc = {"name": name, "min_age": min_age, "max_age": max_age}
	res = await coll.insert_one(doc)
	created = await coll.find_one({"_id": res.inserted_id})
	return {"id": str(created["_id"]), "name": created["name"], "min_age": created["min_age"], "max_age": created["max_age"]}


#########
@app.get("/api/v1/age-groups")
async def list_age_groups() -> List[dict]:
	coll = get_collection(COLLECTION_NAME)
	items: List[dict] = []
	async for doc in coll.find().sort("min_age", 1):
		items.append({"id": str(doc["_id"]), "name": doc["name"], "min_age": doc["min_age"], "max_age": doc["max_age"]})
	return items


#########
@app.delete("/api/v1/age-groups/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_age_group(group_id: str) -> None:
	if not ObjectId.is_valid(group_id):
		raise HTTPException(status_code=400, detail="group_id inválido")
	coll = get_collection(COLLECTION_NAME)
	res = await coll.delete_one({"_id": ObjectId(group_id)})
	if res.deleted_count == 0:
		raise HTTPException(status_code=404, detail="Grupo não encontrado")
	return None



######### ------------------------------ #########
logger = logging.getLogger(__name__)

if __name__ == "__main__":
	logger.info("Starting Uvicorn server on 0.0.0.0:3000")
	uvicorn.run(app, host="0.0.0.0", port=3000)
