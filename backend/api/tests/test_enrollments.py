import pytest
import httpx
import logging

API_URL = "http://api:3000/api/v1/enrollments"
AUTH = ("admin", "admin123")
logger = logging.getLogger("test_enrollments")
logging.basicConfig(level=logging.INFO)

@pytest.mark.asyncio
async def test_create_enrollment_success():
    async with httpx.AsyncClient() as client:
        payload = {"name": "Teste Inscrição", "age": 25, "cpf": "09702414458"}
        response = await client.post(API_URL, auth=AUTH, json=payload)
        logger.info(f"[PASS/FAIL] test_create_enrollment_success: status={response.status_code}, body={response.json()}")
        assert response.status_code == 201
        data = response.json()
        assert "enrollment_id" in data
        assert data["status"] == "queued"
        global created_enrollment_id
        created_enrollment_id = data["enrollment_id"]

@pytest.mark.asyncio
async def test_create_enrollment_blank_name():
    async with httpx.AsyncClient() as client:
        payload = {"name": "", "age": 25, "cpf": "09702414458"}
        response = await client.post(API_URL, auth=AUTH, json=payload)
        logger.info(f"[PASS/FAIL] test_create_enrollment_blank_name: status={response.status_code}, body={response.json()}")
        assert response.status_code == 400

@pytest.mark.asyncio
async def test_create_enrollment_invalid_cpf():
    async with httpx.AsyncClient() as client:
        payload = {"name": "Teste CPF", "age": 25, "cpf": "12345678900"}
        response = await client.post(API_URL, auth=AUTH, json=payload)
        logger.info(f"[PASS/FAIL] test_create_enrollment_invalid_cpf: status={response.status_code}, body={response.json()}")
        assert response.status_code == 422

@pytest.mark.asyncio
async def test_create_enrollment_age_out_of_range():
    async with httpx.AsyncClient() as client:
        payload = {"name": "Fora da Faixa", "age": 5, "cpf": "09702414458"}
        response = await client.post(API_URL, auth=AUTH, json=payload)
        logger.info(f"[PASS/FAIL] test_create_enrollment_age_out_of_range: status={response.status_code}, body={response.json()}")
        assert response.status_code == 422

@pytest.mark.asyncio
async def test_enrollment_status():
    async with httpx.AsyncClient() as client:
        global created_enrollment_id
        response = await client.get(f"{API_URL}/{created_enrollment_id}", auth=AUTH)
        logger.info(f"[PASS/FAIL] test_enrollment_status: status={response.status_code}, body={response.json()}")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data

@pytest.mark.asyncio
async def test_auth_required_enrollment():
    async with httpx.AsyncClient() as client:
        payload = {"name": "Teste Auth", "age": 25, "cpf": "09702414458"}
        response = await client.post(API_URL, json=payload)
        logger.info(f"[PASS/FAIL] test_auth_required_enrollment: status={response.status_code}, body={response.text}")
        assert response.status_code == 401
