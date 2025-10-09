import pytest
import httpx
import logging

AGE_GROUPS_URL = "http://api:3000/api/v1/age-groups"
ENROLLMENTS_URL = "http://api:3000/api/v1/enrollments"
AUTH = ("admin", "admin123")
logger = logging.getLogger("test_api")
logging.basicConfig(level=logging.INFO)

created_group_id = None
created_enrollment_id = None

@pytest.mark.asyncio
async def test_create_age_group_success():
    global created_group_id
    async with httpx.AsyncClient() as client:
        response = await client.post(
            AGE_GROUPS_URL,
            auth=AUTH,
            json={"name": "Adulto", "min_age": 18, "max_age": 60}
        )
        logger.info(f"[PASS] test_create_age_group_success: status={response.status_code}, body={response.json()}")
        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        created_group_id = data["id"]

@pytest.mark.asyncio
async def test_create_age_group_missing_name():
    async with httpx.AsyncClient() as client:
        response = await client.post(
            AGE_GROUPS_URL,
            auth=AUTH,
            json={"min_age": 15, "max_age": 17}
        )
        logger.info(f"[PASS/FAIL] test_create_age_group_missing_name: status={response.status_code}, body={response.json()}")
        assert response.status_code == 400

@pytest.mark.asyncio
async def test_create_age_group_invalid_age_range():
    async with httpx.AsyncClient() as client:
        response = await client.post(
            AGE_GROUPS_URL,
            auth=AUTH,
            json={"name": "Faixa Inválida", "min_age": 30, "max_age": 10}
        )
        logger.info(f"[PASS/FAIL] test_create_age_group_invalid_age_range: status={response.status_code}, body={response.json()}")
        assert response.status_code == 400

@pytest.mark.asyncio
async def test_create_age_group_conflict():
    async with httpx.AsyncClient() as client:
        await client.post(
            AGE_GROUPS_URL,
            auth=AUTH,
            json={"name": "Jovem", "min_age": 0, "max_age": 9}
        )
        response = await client.post(
            AGE_GROUPS_URL,
            auth=AUTH,
            json={"name": "Sobreposto", "min_age": 1, "max_age": 8}
        )
        logger.info(f"[PASS/FAIL] test_create_age_group_conflict: status={response.status_code}, body={response.json()}")
        assert response.status_code == 409

@pytest.mark.asyncio
async def test_create_enrollment_success():
    global created_enrollment_id
    async with httpx.AsyncClient() as client:
        payload = {"name": "Teste Inscrição", "age": 25, "cpf": "09702414458"}
        response = await client.post(ENROLLMENTS_URL, auth=AUTH, json=payload)
        logger.info(f"[PASS/FAIL] test_create_enrollment_success: status={response.status_code}, body={response.json()}")
        assert response.status_code == 201
        data = response.json()
        assert "enrollment_id" in data
        assert data["status"] == "queued"
        created_enrollment_id = data["enrollment_id"]

@pytest.mark.asyncio
async def test_delete_age_group():
    async with httpx.AsyncClient() as client:
        global created_group_id
        del_resp = await client.delete(f"{AGE_GROUPS_URL}/{created_group_id}", auth=AUTH)
        logger.info(f"[PASS/FAIL] test_delete_age_group: status={del_resp.status_code}, body={del_resp.text}")
        assert del_resp.status_code == 204

@pytest.mark.asyncio
async def test_list_age_groups():
    async with httpx.AsyncClient() as client:
        response = await client.get(AGE_GROUPS_URL, auth=AUTH)
        logger.info(f"[PASS] test_list_age_groups: status={response.status_code}, body={response.json()}")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

@pytest.mark.asyncio
async def test_auth_required():
    async with httpx.AsyncClient() as client:
        response = await client.get(AGE_GROUPS_URL)
        logger.info(f"[PASS/FAIL] test_auth_required: status={response.status_code}, body={response.text}")
        assert response.status_code == 401


@pytest.mark.asyncio
async def test_create_enrollment_blank_name():
    async with httpx.AsyncClient() as client:
        payload = {"name": "", "age": 25, "cpf": "09702414458"}
        response = await client.post(ENROLLMENTS_URL, auth=AUTH, json=payload)
        logger.info(f"[PASS/FAIL] test_create_enrollment_blank_name: status={response.status_code}, body={response.json()}")
        assert response.status_code == 400

@pytest.mark.asyncio
async def test_create_enrollment_invalid_cpf():
    async with httpx.AsyncClient() as client:
        payload = {"name": "Teste CPF", "age": 25, "cpf": "12345678900"}
        response = await client.post(ENROLLMENTS_URL, auth=AUTH, json=payload)
        logger.info(f"[PASS/FAIL] test_create_enrollment_invalid_cpf: status={response.status_code}, body={response.json()}")
        assert response.status_code == 422

@pytest.mark.asyncio
async def test_create_enrollment_age_out_of_range():
    async with httpx.AsyncClient() as client:
        payload = {"name": "Fora da Faixa", "age": 99, "cpf": "09702414458"}
        response = await client.post(ENROLLMENTS_URL, auth=AUTH, json=payload)
        logger.info(f"[PASS/FAIL] test_create_enrollment_age_out_of_range: status={response.status_code}, body={response.json()}")
        assert response.status_code == 422

@pytest.mark.asyncio
async def test_enrollment_status():
    global created_enrollment_id
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{ENROLLMENTS_URL}/{created_enrollment_id}", auth=AUTH)
        logger.info(f"[PASS/FAIL] test_enrollment_status: status={response.status_code}, body={response.json()}")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data

@pytest.mark.asyncio
async def test_auth_required_enrollment():
    async with httpx.AsyncClient() as client:
        payload = {"name": "Teste Auth", "age": 25, "cpf": "09702414458"}
        response = await client.post(ENROLLMENTS_URL, json=payload)
        logger.info(f"[PASS/FAIL] test_auth_required_enrollment: status={response.status_code}, body={response.text}")
        assert response.status_code == 401
