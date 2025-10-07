from typing import Dict
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
import os
import secrets

security = HTTPBasic()
_credentials_cache: Dict[str, str] = {}
_cache_file_path: str = ""


def _load_credentials(file_path: str) -> None:
	global _credentials_cache, _cache_file_path
	if file_path == _cache_file_path and _credentials_cache:
		return
	_credentials_cache = {}
	_cache_file_path = file_path
	try:
		with open(file_path, "r", encoding="utf-8") as f:
			for line in f:
				line = line.strip()
				if not line or line.startswith("#"):
					continue
				if ":" not in line:
					continue
				username, password = line.split(":", 1)
				_credentials_cache[username] = password
	except FileNotFoundError:
		_credentials_cache = {}


async def basic_auth(credentials: HTTPBasicCredentials = Depends(security)) -> str:
	credentials_file = os.getenv("BASIC_AUTH_CREDENTIALS_FILE", "backend/credentials/basic_auth.txt")
	_load_credentials(credentials_file)
	expected = _credentials_cache.get(credentials.username)
	if expected is None or not secrets.compare_digest(expected, credentials.password):
		raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciais inválidas", headers={"WWW-Authenticate": "Basic"})
	return credentials.username
