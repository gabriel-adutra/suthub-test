from typing import List, Dict, Any
from fastapi import FastAPI, status, HTTPException, Depends
import logging
import uvicorn
from bson import ObjectId
from backend.mongo.db import connect_to_mongo, close_mongo_connection, get_collection
from backend.auth.basic import basic_auth
from datetime import datetime
import re
import redis.asyncio as redis
import os
import json

app = FastAPI(title="Age Groups API", version="1.0.0")

# Conexão MongoDB no ciclo de vida da aplicação
@app.on_event("startup")
async def on_startup() -> None:
    await connect_to_mongo()


@app.on_event("shutdown")
async def on_shutdown() -> None:
    await close_mongo_connection()


@app.get("/")
async def root(_: str = Depends(basic_auth)) -> dict:
    return {"status": "ok"}


# Endpoints Age Groups (prefixo /api/v1)
COLLECTION_NAME = "age_groups"


#########
@app.post("/api/v1/age-groups", status_code=status.HTTP_201_CREATED)
async def create_age_group(payload: dict, _: str = Depends(basic_auth)) -> dict:
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
async def list_age_groups(_: str = Depends(basic_auth)) -> List[dict]:
    coll = get_collection(COLLECTION_NAME)
    items: List[dict] = []
    async for doc in coll.find().sort("min_age", 1):
        items.append({"id": str(doc["_id"]), "name": doc["name"], "min_age": doc["min_age"], "max_age": doc["max_age"]})
    return items


#########
@app.delete("/api/v1/age-groups/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_age_group(group_id: str, _: str = Depends(basic_auth)) -> None:
    if not ObjectId.is_valid(group_id):
        raise HTTPException(status_code=400, detail="group_id inválido")
    coll = get_collection(COLLECTION_NAME)
    res = await coll.delete_one({"_id": ObjectId(group_id)})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Grupo não encontrado")
    return None


######### Enrollments endpoint (integrado aqui)
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
QUEUE_KEY = "enrollments_queue"


def _normalize_cpf(cpf: str) -> str:
    return re.sub(r"[^0-9]", "", cpf or "")


def _validate_cpf_digits(cpf: str) -> bool:
    # CPF must be 11 digits
    if len(cpf) != 11 or cpf == cpf[0] * 11:
        return False
    def _calc(digs: str) -> int:
        s = 0
        for i, d in enumerate(digs, start=1):
            s += int(d) * (len(digs) + 1 - i)
        r = (s * 10) % 11
        return r if r < 10 else 0
    n1 = _calc(cpf[:9])
    n2 = _calc(cpf[:10])
    return n1 == int(cpf[9]) and n2 == int(cpf[10])


@app.post("/api/v1/enrollments", status_code=status.HTTP_201_CREATED)
async def request_enrollment(payload: Dict[str, Any], _: str = Depends(basic_auth)) -> Dict[str, Any]:
    name = payload.get("name")
    age = payload.get("age")
    cpf = payload.get("cpf")
    if name is None or age is None or cpf is None:
        raise HTTPException(status_code=400, detail="Campos obrigatórios: name, age, cpf")
    if not isinstance(age, int):
        raise HTTPException(status_code=400, detail="age deve ser inteiro")

    cpf_norm = _normalize_cpf(cpf)
    if not _validate_cpf_digits(cpf_norm):
        raise HTTPException(status_code=422, detail="CPF inválido")

    # Check age group exists
    ag_coll = get_collection("age_groups")
    group = await ag_coll.find_one({"min_age": {"$lte": age}, "max_age": {"$gte": age}})
    if not group:
        raise HTTPException(status_code=422, detail="Nenhuma faixa etária encontrada para a idade informada")

    # Create enrollment doc
    coll = get_collection("enrollments")
    now = datetime.utcnow()
    doc = {
        "name": name,
        "age": age,
        "cpf": cpf_norm,
        "status": "queued",
        "created_at": now,
        "updated_at": now,
    }
    res = await coll.insert_one(doc)
    enrollment_id = str(res.inserted_id)

    # Push message to redis queue (simple list)
    try:
        r = redis.from_url(REDIS_URL)
        msg = {"enrollment_id": enrollment_id, "name": name, "age": age, "cpf": cpf_norm, "created_at": now.isoformat()}
        await r.rpush(QUEUE_KEY, json.dumps(msg))
        await r.close()
    except Exception:
        # Try best-effort: update enrollment as failed to enqueue
        await coll.update_one({"_id": ObjectId(enrollment_id)}, {"$set": {"status": "failed", "updated_at": datetime.utcnow(), "reason": "enqueue_error"}})
        raise HTTPException(status_code=500, detail="Erro ao enfileirar a solicitação")

    return {"enrollment_id": enrollment_id, "status": "queued"}


######### ------------------------------ #########
logger = logging.getLogger(__name__)

if __name__ == "__main__":
    logger.info("Starting Uvicorn server on 0.0.0.0:3000")
    uvicorn.run(app, host="0.0.0.0", port=3000)
