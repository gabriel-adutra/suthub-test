import asyncio
import json
import os
import logging
import time
from datetime import datetime

from bson import ObjectId
import redis.asyncio as redis
from backend.mongo.db import connect_to_mongo, close_mongo_connection, get_collection
from backend.utils.cpf_utils import CPFUtils

LOG = logging.getLogger("consumer_enrollment")
LOG.setLevel(logging.INFO)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
LOG.addHandler(handler)

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
QUEUE_KEY = os.getenv("ENROLLMENTS_QUEUE", "enrollments_queue")
DLQ_KEY = os.getenv("ENROLLMENTS_DLQ", "enrollments_dlq")



# ------------------- Classe principal do worker -------------------
class EnrollmentProcessor:
    def __init__(self, redis_url, queue_key, dlq_key, logger):
        """
        Inicializa o processador de inscrições.
        Parâmetros:
            redis_url (str): URL de conexão do Redis
            queue_key (str): Nome da fila principal
            dlq_key (str): Nome da fila de dead-letter
            logger (logging.Logger): Logger para logs
        """
        self.logger = logger
        self.logger.debug(f"Inicializando EnrollmentProcessor: redis_url={redis_url}, queue_key={queue_key}, dlq_key={dlq_key}")
        self.queue_key = queue_key
        self.dlq_key = dlq_key


    async def _validate_enrollment_data(self, enrollment_id, name, age, cpf, coll) -> str:
        """
        Valida CPF e faixa etária do candidato.
        Parâmetros:
            enrollment_id (str): ID da inscrição
            name (str): Nome do candidato
            age (int): Idade do candidato
            cpf (str): CPF do candidato
            coll: Coleção MongoDB de inscrições
        Retorno:
            str: Motivo de rejeição ou None se válido
        """
        self.logger.debug(f"Validando dados: enrollment_id={enrollment_id}, name={name}, age={age}, cpf={cpf}")
        cpf_norm = CPFUtils.normalize_cpf(cpf)
        if not CPFUtils.is_valid_cpf(cpf_norm):
            await coll.update_one({"_id": ObjectId(enrollment_id)}, {"$set": {"status": "rejected", "reason": "cpf_invalido", "updated_at": datetime.utcnow()}})
            self.logger.info(f"Enrollment {enrollment_id} rejeitado por CPF inválido")
            self.logger.warning(f"CPF inválido detectado: cpf={cpf_norm}")
            return "cpf_invalido"
        ag = get_collection("age_groups")
        group = await ag.find_one({"min_age": {"$lte": age}, "max_age": {"$gte": age}})
        if not group:
            await coll.update_one({"_id": ObjectId(enrollment_id)}, {"$set": {"status": "rejected", "reason": "faixa_nao_encontrada", "updated_at": datetime.utcnow()}})
            self.logger.info(f"Enrollment {enrollment_id} rejeitado por faixa etária")
            self.logger.warning(f"Faixa etária não encontrada para age={age}")
            return "faixa_nao_encontrada"
        self.logger.debug(f"Dados válidos para enrollment_id={enrollment_id}")
        return None
    

    async def _persist_user(self, name, age, cpf_norm):
        """
        Persiste usuário vinculado à inscrição.
        Parâmetros:
            name (str): Nome do usuário
            age (int): Idade
            cpf_norm (str): CPF normalizado
        Retorno:
            ObjectId: ID do usuário criado
        """
        self.logger.debug(f"Persistindo usuário: name={name}, age={age}, cpf_norm={cpf_norm}")
        users = get_collection("users")
        now = datetime.utcnow()
        user_doc = {"name": name, "age": age, "cpf": cpf_norm, "created_at": now}
        res = await users.insert_one(user_doc)
        self.logger.info(f"Usuário criado: user_id={res.inserted_id}, doc={user_doc}")
        return res.inserted_id
    

    async def _update_enrollment_status(self, enrollment_id, coll, status, extra=None):
        """
        Atualiza status da inscrição no banco.
        Parâmetros:
            enrollment_id (str): ID da inscrição
            coll: Coleção MongoDB de inscrições
            status (str): Novo status
            extra (dict, opcional): Campos extras para atualizar
        Retorno: None
        """
        self.logger.debug(f"Atualizando status: enrollment_id={enrollment_id}, status={status}, extra={extra}")
        update = {"status": status, "updated_at": datetime.utcnow()}
        if extra:
            update.update(extra)
        await coll.update_one({"_id": ObjectId(enrollment_id)}, {"$set": update})
        self.logger.info(f"Status atualizado: enrollment_id={enrollment_id}, status={status}, extra={extra}")


    async def _handle_processing_error(self, enrollment_id, coll, r, msg, exc):
        """
        Lida com erro de processamento, atualiza status e envia para DLQ.
        Parâmetros:
            enrollment_id (str): ID da inscrição
            coll: Coleção MongoDB de inscrições
            r: Instância Redis
            msg (str): Mensagem original
            exc (Exception): Exceção capturada
        Retorno: None
        """
        self.logger.exception(f"Erro ao processar mensagem: {exc}")
        self.logger.warning(f"Processamento falhou para enrollment_id={enrollment_id}, mensagem={msg}")
        try:
            if enrollment_id:
                await self._update_enrollment_status(enrollment_id, coll, "failed", {"reason": "processing_error"})
        except Exception as e:
            self.logger.exception(f"Erro ao marcar enrollment como failed: {e}")
        try:
            await r.rpush(self.dlq_key, msg)
        except Exception as e:
            self.logger.exception(f"Erro ao empurrar para DLQ: {e}")


    async def process_message(self, msg: str, r: redis.Redis) -> None:
        """
        Processa uma mensagem de inscrição da fila.
        Parâmetros:
            msg (str): Mensagem JSON da inscrição
            r: Instância Redis
        Retorno: None
        """
        self.logger.info(f"Recebendo mensagem da fila: {msg}")
        start = time.monotonic()
        enrollment_id = None
        try:
            data = json.loads(msg)
            enrollment_id = data.get("enrollment_id")
            name = data.get("name")
            age = data.get("age")
            cpf = data.get("cpf")

            if not enrollment_id:
                self.logger.warning(f"Mensagem sem enrollment_id: {data}")
                return

            coll = get_collection("enrollments")
            enroll = await coll.find_one({"_id": ObjectId(enrollment_id)})
            if not enroll:
                self.logger.warning(f"Enrollment não encontrado: {enrollment_id}")
                return

            # Idempotência: só processa se status for queued ou None
            status = enroll.get("status")
            if status not in ("queued", None):
                self.logger.info(f"Enrollment {enrollment_id} já processado (status={status}), pulando")
                return

            await self._update_enrollment_status(enrollment_id, coll, "processing")

            # Validação dos dados
            motivo_rejeicao = await self._validate_enrollment_data(enrollment_id, name, age, cpf, coll)
            if motivo_rejeicao:
                self.logger.warning(f"Inscrição rejeitada: enrollment_id={enrollment_id}, motivo={motivo_rejeicao}")
                return

            cpf_norm = CPFUtils.normalize_cpf(cpf)
            user_id = await self._persist_user(name, age, cpf_norm)
            await self._update_enrollment_status(
                enrollment_id,
                coll,
                "completed",
                {"user_id": user_id, "processed_at": datetime.utcnow()}
            )
            self.logger.info(f"Enrollment {enrollment_id} processado com sucesso, user_id={user_id}")
            self.logger.debug(f"Processamento finalizado para enrollment_id={enrollment_id}")

        except Exception as exc:
            await self._handle_processing_error(enrollment_id, coll if 'coll' in locals() else None, r, msg, exc)
        finally:
            elapsed = time.monotonic() - start
            if elapsed < 2.0:
                await asyncio.sleep(2.0 - elapsed)



####################
####################
async def main() -> None:
    """
    Loop principal do worker. Conecta aos serviços, consome fila e processa inscrições.
    Parâmetros: None
    Retorno: None
    """

    LOG.info("Conectando ao MongoDB e Redis...")
    await connect_to_mongo()
    r = redis.from_url(REDIS_URL)
    processor = EnrollmentProcessor(REDIS_URL, QUEUE_KEY, DLQ_KEY, LOG)
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
                LOG.debug(f"Mensagem recebida da fila: {value}")
                await processor.process_message(value, r)
            except asyncio.CancelledError:
                raise
            except Exception:
                LOG.exception("Erro no loop do consumer")
                await asyncio.sleep(1)
    finally:
        await r.close()
        await close_mongo_connection()



####################-----------------------------####################

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        LOG.info("Worker finalizado pelo usuário")
