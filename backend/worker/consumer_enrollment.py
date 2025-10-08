import asyncio
import json
import os
import logging
import time
from datetime import datetime
from bson import ObjectId

import redis.asyncio as redis

from backend.mongo.db import connect_to_mongo, close_mongo_connection, get_collection

LOG = logging.getLogger("consumer_enrollment")
LOG.setLevel(logging.INFO)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
LOG.addHandler(handler)

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
QUEUE_KEY = os.getenv("ENROLLMENTS_QUEUE", "enrollments_queue")
DLQ_KEY = os.getenv("ENROLLMENTS_DLQ", "enrollments_dlq")


def _normalize_cpf(cpf: str) -> str:
    import re
    # Remove pontos, hífens e qualquer caractere não numérico
    return re.sub(r"[^0-9]", "", cpf or "")


def _validate_cpf_digits(cpf: str) -> bool:
    # Validação oficial do CPF (igual API)
    if len(cpf) != 11 or not cpf.isdigit():
        return False
    if cpf == cpf[0] * 11:
        return False
    soma = sum(int(cpf[i]) * (10 - i) for i in range(9))
    resto = soma % 11
    if resto < 2:
        dv1 = 0
    else:
        dv1 = 11 - resto
    soma = sum(int(cpf[i]) * (11 - i) for i in range(10))
    resto = soma % 11
    if resto < 2:
        dv2 = 0
    else:
        dv2 = 11 - resto
    return int(cpf[9]) == dv1 and int(cpf[10]) == dv2


async def process_message(msg: str, r: redis.Redis) -> None:
    start = time.monotonic()
    try:
        data = json.loads(msg)
        enrollment_id = data.get("enrollment_id")
        name = data.get("name")
        age = data.get("age")
        cpf = data.get("cpf")

        if not enrollment_id:
            LOG.warning("Mensagem sem enrollment_id: %s", data)
            return

        coll = get_collection("enrollments")
        enroll = await coll.find_one({"_id": ObjectId(enrollment_id)})
        if not enroll:
            LOG.warning("Enrollment não encontrado: %s", enrollment_id)
            return

        # Idempotence: only process queued
        status = enroll.get("status")
        if status not in ("queued", None):
            LOG.info("Enrollment %s já processado (status=%s), pulando", enrollment_id, status)
            return

        await coll.update_one({"_id": ObjectId(enrollment_id)}, {"$set": {"status": "processing", "updated_at": datetime.utcnow()}})

        # Validate CPF
        cpf_norm = _normalize_cpf(cpf)
        if not _validate_cpf_digits(cpf_norm):
            await coll.update_one({"_id": ObjectId(enrollment_id)}, {"$set": {"status": "rejected", "reason": "cpf_invalido", "updated_at": datetime.utcnow()}})
            LOG.info("Enrollment %s rejeitado por CPF inválido", enrollment_id)
            return

        # Check age group
        ag = get_collection("age_groups")
        group = await ag.find_one({"min_age": {"$lte": age}, "max_age": {"$gte": age}})
        if not group:
            await coll.update_one({"_id": ObjectId(enrollment_id)}, {"$set": {"status": "rejected", "reason": "faixa_nao_encontrada", "updated_at": datetime.utcnow()}})
            LOG.info("Enrollment %s rejeitado por faixa etária", enrollment_id)
            return

        # Insert user
        users = get_collection("users")
        now = datetime.utcnow()
        user_doc = {"name": name, "age": age, "cpf": cpf_norm, "created_at": now}
        res = await users.insert_one(user_doc)

        # Update enrollment as completed
        await coll.update_one({"_id": ObjectId(enrollment_id)}, {"$set": {"status": "completed", "user_id": res.inserted_id, "processed_at": datetime.utcnow(), "updated_at": datetime.utcnow()}})
        LOG.info("Enrollment %s processado com sucesso, user_id=%s", enrollment_id, str(res.inserted_id))

    except Exception as exc:
        LOG.exception("Erro ao processar mensagem: %s", exc)
        try:
            # try marking failed in DB
            if 'enrollment_id' in locals() and enrollment_id:
                coll = get_collection("enrollments")
                await coll.update_one({"_id": ObjectId(enrollment_id)}, {"$set": {"status": "failed", "reason": "processing_error", "updated_at": datetime.utcnow()}})
        except Exception:
            LOG.exception("Erro ao marcar enrollment como failed")
        # push to DLQ
        try:
            await r.rpush(DLQ_KEY, msg)
        except Exception:
            LOG.exception("Erro ao empurrar para DLQ")
    finally:
        elapsed = time.monotonic() - start
        if elapsed < 2.0:
            await asyncio.sleep(2.0 - elapsed)


async def main() -> None:
    LOG.info("Conectando ao MongoDB e Redis...")
    await connect_to_mongo()
    r = redis.from_url(REDIS_URL)
    try:
        while True:
            try:
                item = await r.brpop(QUEUE_KEY, timeout=5)
                if not item:
                    await asyncio.sleep(0.5)
                    continue
                # item is a tuple (key, value)
                _, value = item
                if isinstance(value, bytes):
                    value = value.decode()
                await process_message(value, r)
            except asyncio.CancelledError:
                raise
            except Exception:
                LOG.exception("Erro no loop do consumer")
                await asyncio.sleep(1)
    finally:
        await r.close()
        await close_mongo_connection()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        LOG.info("Worker finalizado pelo usuário")
