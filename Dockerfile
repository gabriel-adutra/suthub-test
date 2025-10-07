FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 POETRY_VIRTUALENVS_CREATE=false PYTHONPATH=/app

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends build-essential && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY backend ./backend

EXPOSE 3000

# Use uvicorn to run the FastAPI ASGI app
CMD ["uvicorn", "backend.api.app:app", "--host", "0.0.0.0", "--port", "3000"]
