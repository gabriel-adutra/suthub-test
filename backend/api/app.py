
from typing import List, Dict, Any
from fastapi import FastAPI, status, HTTPException, Depends, Path
import logging
import uvicorn
from bson import ObjectId
from backend.mongo.db import connect_to_mongo, close_mongo_connection, get_collection
from backend.auth.basic import basic_auth
from datetime import datetime
import os

app = FastAPI(title="Age Groups API", version="1.0.0")

# Conexão MongoDB no ciclo de vida da aplicação
@app.on_event("startup")
async def on_startup() -> None:
    """
    Evento de inicialização da API.
    Conecta ao MongoDB.
    Parâmetros: None
    Retorno: None
    """
    logger.info("Iniciando evento de startup da API")
    await connect_to_mongo()
    logger.info("Conexão com MongoDB estabelecida")


@app.on_event("shutdown")
async def on_shutdown() -> None:
    """
    Evento de desligamento da API.
    Fecha conexão com MongoDB.
    Parâmetros: None
    Retorno: None
    """
    logger.info("Iniciando evento de shutdown da API")
    await close_mongo_connection()
    logger.info("Conexão com MongoDB encerrada")


@app.get("/")
async def root(_: str = Depends(basic_auth)) -> dict:
    """
    Endpoint de status da API.
    Parâmetros:
        _: autenticação básica
    Retorno:
        dict: status da API
    """
    logger.info("Endpoint / chamado, status=ok")
    return {"status": "ok"}


# Endpoints Age Groups (prefixo /api/v1)
COLLECTION_NAME = "age_groups"


#########
@app.post("/api/v1/age-groups", status_code=status.HTTP_201_CREATED)
async def create_age_group(payload: dict, _: str = Depends(basic_auth)) -> dict:
    """
    Cria um novo grupo etário.
    Parâmetros:
        payload (dict): dados do grupo
        _: autenticação básica
    Retorno:
        dict: grupo criado
    """
    logger.info(f"Recebendo payload para criação de grupo etário: {payload}")
    name = payload.get("name")
    min_age = payload.get("min_age")
    max_age = payload.get("max_age")
    if name is None or min_age is None or max_age is None:
        logger.warning(f"Payload incompleto: {payload}")
        raise HTTPException(status_code=400, detail="Campos obrigatórios: name, min_age, max_age")
    if not isinstance(min_age, int) or not isinstance(max_age, int):
        logger.warning(f"min_age ou max_age não inteiros: min_age={min_age}, max_age={max_age}")
        raise HTTPException(status_code=400, detail="min_age e max_age devem ser inteiros")
    if min_age > max_age:
        logger.warning(f"min_age maior que max_age: min_age={min_age}, max_age={max_age}")
        raise HTTPException(status_code=400, detail="min_age não pode ser maior que max_age")

    coll = get_collection(COLLECTION_NAME)
    overlap = await coll.find_one({
        "$expr": {
            "$and": [
                {"$lte": ["$min_age", max_age]},
                {"$gte": ["$max_age", min_age]},
            ]
        }
    })
    if overlap:
        logger.warning(f"Sobreposição de faixa etária detectada: {payload}")
        raise HTTPException(status_code=409, detail="Intervalo de idade sobrepõe grupo existente")

    doc = {"name": name, "min_age": min_age, "max_age": max_age}
    res = await coll.insert_one(doc)
    created = await coll.find_one({"_id": res.inserted_id})
    logger.info(f"Grupo etário criado: {created}")
    return {"id": str(created["_id"]), "name": created["name"], "min_age": created["min_age"], "max_age": created["max_age"]}


#########
@app.get("/api/v1/age-groups")
async def list_age_groups(_: str = Depends(basic_auth)) -> List[dict]:
    """
    Lista todos os grupos etários.
    Parâmetros:
        _: autenticação básica
    Retorno:
        List[dict]: lista de grupos
    """
    coll = get_collection(COLLECTION_NAME)
    items: List[dict] = []
    async for doc in coll.find().sort("min_age", 1):
        items.append({"id": str(doc["_id"]), "name": doc["name"], "min_age": doc["min_age"], "max_age": doc["max_age"]})
    logger.info(f"Listando grupos etários: total={len(items)}")
    return items


#########
@app.delete("/api/v1/age-groups/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_age_group(group_id: str, _: str = Depends(basic_auth)) -> None:
    """
    Remove um grupo etário pelo ID.
    Parâmetros:
        group_id (str): ID do grupo
        _: autenticação básica
    Retorno: None
    """
    logger.info(f"Solicitação de remoção de grupo: group_id={group_id}")
    if not ObjectId.is_valid(group_id):
        logger.warning(f"group_id inválido: {group_id}")
        raise HTTPException(status_code=400, detail="group_id inválido")
    coll = get_collection(COLLECTION_NAME)
    res = await coll.delete_one({"_id": ObjectId(group_id)})
    if res.deleted_count == 0:
        logger.warning(f"Grupo não encontrado para remoção: group_id={group_id}")
        raise HTTPException(status_code=404, detail="Grupo não encontrado")
    logger.info(f"Grupo removido: group_id={group_id}")
    return None


######### Enrollments endpoint (integrado aqui)
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
QUEUE_KEY = "enrollments_queue"




# Importa serviço de inscrição do módulo dedicado
from backend.api.services.enrollment_service import EnrollmentService



enrollment_service = EnrollmentService(REDIS_URL, QUEUE_KEY)

@app.post("/api/v1/enrollments", status_code=status.HTTP_201_CREATED)
async def request_enrollment(payload: Dict[str, Any], _: str = Depends(basic_auth)) -> Dict[str, Any]:
    """
    Endpoint de inscrição. Valida dados, persiste e enfileira no Redis.
    Parâmetros:
        payload (dict): dados da inscrição
        _: autenticação básica
    Retorno:
        dict: status da inscrição
    """
    logger.info(f"Recebendo payload de inscrição: {payload}")
    result = await enrollment_service.request_enrollment(payload)
    logger.info(f"Inscrição processada: retorno={result}")
    return result


#########
# Endpoint para consultar status do enrollment
@app.get("/api/v1/enrollments/{enrollment_id}")
async def get_enrollment_status(enrollment_id: str = Path(..., description="ID da inscrição"), _: str = Depends(basic_auth)) -> dict:
    """
    Consulta status de uma inscrição.
    Parâmetros:
        enrollment_id (str): ID da inscrição
        _: autenticação básica
    Retorno:
        dict: dados da inscrição
    """
    logger.info(f"Consulta de status de inscrição: enrollment_id={enrollment_id}")
    coll = get_collection("enrollments")
    try:
        obj_id = ObjectId(enrollment_id)
    except Exception:
        logger.warning(f"enrollment_id inválido: {enrollment_id}")
        raise HTTPException(status_code=400, detail="enrollment_id inválido")
    enrollment = await coll.find_one({"_id": obj_id})
    if not enrollment:
        logger.warning(f"Inscrição não encontrada: enrollment_id={enrollment_id}")
        raise HTTPException(status_code=404, detail="Inscrição não encontrada")
    logger.debug(f"Dados brutos da inscrição: {enrollment}")
    def bson_to_json(val):
        if isinstance(val, dict):
            return {k: bson_to_json(v) for k, v in val.items()}
        elif isinstance(val, list):
            return [bson_to_json(v) for v in val]
        elif isinstance(val, ObjectId):
            return str(val)
        elif isinstance(val, datetime):
            return val.isoformat()
        else:
            return val
    result = bson_to_json(enrollment)
    result["enrollment_id"] = str(result.pop("_id"))
    logger.info(f"Retornando status de inscrição: {result}")
    return result





######### ------------------------------ #########
logger = logging.getLogger(__name__)

if __name__ == "__main__":
    """
    Inicializa o servidor Uvicorn para rodar a API.
    """
    logger.info("Starting Uvicorn server on 0.0.0.0:3000")
    uvicorn.run(app, host="0.0.0.0", port=3000)
