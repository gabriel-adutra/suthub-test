"""
Serviço de inscrição: encapsula lógica de validação, persistência e mensageria.
Facilita testes, manutenção e reuso.
"""
from typing import Dict, Any
from fastapi import HTTPException
from bson import ObjectId
from datetime import datetime
import redis.asyncio as redis
import json
from backend.mongo.db import get_collection
from backend.utils.cpf_utils import CPFUtils

class EnrollmentService:
    def __init__(self, redis_url: str, queue_key: str, logger=None):
        """
        Inicializa o serviço de inscrição.
        Parâmetros:
            redis_url (str): URL do Redis
            queue_key (str): Nome da fila de inscrições
            logger (logging.Logger, opcional): Logger para logs
        """
        self.redis_url = redis_url
        self.queue_key = queue_key
        if logger is None:
            import logging
            logger = logging.getLogger("enrollment_service")
            logger.setLevel(logging.INFO)
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
            if not logger.hasHandlers():
                logger.addHandler(handler)
        self.logger = logger

    async def request_enrollment(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Realiza a solicitação de inscrição: valida dados, persiste no banco e enfileira no Redis.
        Parâmetros:
            payload (dict): dados da inscrição
        Retorno:
            dict: status da inscrição
        """
        name = payload.get("name")
        age = payload.get("age")
        cpf = payload.get("cpf")
        self.logger.info(f"Recebendo payload de inscrição: {payload}")
        if name is None or age is None or cpf is None:
            self.logger.warning(f"Payload incompleto: {payload}")
            raise HTTPException(status_code=400, detail="Campos obrigatórios: name, age, cpf")
        if not isinstance(age, int):
            self.logger.warning(f"Idade não inteira: age={age}")
            raise HTTPException(status_code=400, detail="age deve ser inteiro")

        # Normalização e validação crítica do CPF
        cpf_norm = CPFUtils.normalize_cpf(cpf)
        if not CPFUtils.is_valid_cpf(cpf_norm):
            self.logger.warning(f"CPF inválido detectado: cpf={cpf_norm}")
            raise HTTPException(status_code=422, detail="CPF inválido (digitos verificadores ou formato)")

        # Verifica existência de grupo etário
        ag_coll = get_collection("age_groups")
        group = await ag_coll.find_one({"min_age": {"$lte": age}, "max_age": {"$gte": age}})
        if not group:
            self.logger.warning(f"Faixa etária não encontrada para age={age}")
            raise HTTPException(status_code=422, detail="Nenhuma faixa etária encontrada para a idade informada")

        # Persistência da inscrição
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
        self.logger.info(f"Inscrição criada: enrollment_id={enrollment_id}, doc={doc}")

        # Mensageria: enfileira inscrição no Redis
        try:
            r = redis.from_url(self.redis_url)
            msg = {"enrollment_id": enrollment_id, "name": name, "age": age, "cpf": cpf_norm, "created_at": now.isoformat()}
            await r.rpush(self.queue_key, json.dumps(msg))
            await r.close()
            self.logger.info(f"Inscrição enfileirada no Redis: msg={msg}")
        except Exception:
            # Atualiza status em caso de falha na fila
            self.logger.error(f"Erro ao enfileirar inscrição: enrollment_id={enrollment_id}")
            await coll.update_one({"_id": ObjectId(enrollment_id)}, {"$set": {"status": "failed", "updated_at": datetime.utcnow(), "reason": "enqueue_error"}})
            raise HTTPException(status_code=500, detail="Erro ao enfileirar a solicitação")

        result = {"enrollment_id": enrollment_id, "status": "queued"}
        self.logger.info(f"Retorno da inscrição: {result}")
        return result
