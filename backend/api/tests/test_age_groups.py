
import pytest
import httpx
import logging

API_URL = "http://api:3000/api/v1/age-groups"
AUTH = ("admin", "admin123")
logger = logging.getLogger("test_age_groups")
logging.basicConfig(level=logging.INFO)

@pytest.mark.asyncio
async def test_create_age_group_success():
    async with httpx.AsyncClient() as client:
        response = await client.post(
            API_URL,
            auth=AUTH,
            json={"name": "Adulto", "min_age": 18, "max_age": 99}
        )
        logger.info(f"[PASS] test_create_age_group_success: status={response.status_code}, body={response.json()}")
        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        # Salva o id para o teste de remoção
        global created_group_id
        created_group_id = data["id"]

@pytest.mark.asyncio
async def test_create_age_group_missing_name():
    async with httpx.AsyncClient() as client:
        response = await client.post(
            API_URL,
            auth=AUTH,
            json={"min_age": 10, "max_age": 20}
        )
        logger.info(f"[PASS/FAIL] test_create_age_group_missing_name: status={response.status_code}, body={response.json()}")
        assert response.status_code == 400

@pytest.mark.asyncio
async def test_create_age_group_invalid_age_range():
    async with httpx.AsyncClient() as client:
        response = await client.post(
            API_URL,
            auth=AUTH,
            json={"name": "Faixa Inválida", "min_age": 30, "max_age": 10}
        )
        logger.info(f"[PASS/FAIL] test_create_age_group_invalid_age_range: status={response.status_code}, body={response.json()}")
        assert response.status_code == 400

@pytest.mark.asyncio
async def test_create_age_group_conflict():
    async with httpx.AsyncClient() as client:
        # Cria grupo inicial
        await client.post(
            API_URL,
            auth=AUTH,
            json={"name": "Jovem", "min_age": 10, "max_age": 20}
        )
        # Tenta criar grupo sobreposto
        response = await client.post(
            API_URL,
            auth=AUTH,
            json={"name": "Sobreposto", "min_age": 15, "max_age": 25}
        )
        logger.info(f"[PASS/FAIL] test_create_age_group_conflict: status={response.status_code}, body={response.json()}")
        assert response.status_code == 409

@pytest.mark.asyncio
async def test_delete_age_group():
    async with httpx.AsyncClient() as client:
        # Remove o grupo criado no teste anterior
        global created_group_id
        del_resp = await client.delete(f"{API_URL}/{created_group_id}", auth=AUTH)
        logger.info(f"[PASS/FAIL] test_delete_age_group: status={del_resp.status_code}, body={del_resp.text}")
        assert del_resp.status_code == 204

@pytest.mark.asyncio
async def test_list_age_groups():
    async with httpx.AsyncClient() as client:
        response = await client.get(API_URL, auth=AUTH)
        logger.info(f"[PASS] test_list_age_groups: status={response.status_code}, body={response.json()}")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

@pytest.mark.asyncio
async def test_auth_required():
    async with httpx.AsyncClient() as client:
        response = await client.get(API_URL)
        logger.info(f"[PASS/FAIL] test_auth_required: status={response.status_code}, body={response.text}")
        assert response.status_code == 401
