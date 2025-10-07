## Age Groups API - Execução via Docker

Este serviço expõe a API de grupos etários utilizando FastAPI e MongoDB. A execução é feita via Docker Compose (API + MongoDB) e os testes manuais via curl.

### Pré-requisitos
- Docker instalado
- jq instalado (para formatar JSON e extrair campos)

### Onde rodar os comandos
- Diretório raiz do projeto (onde está o `docker-compose.yml`): `suthub-test/`

### Executar com docker-compose (API + MongoDB)
A partir do diretório `suthub-test/`:
```bash
docker compose up --build
```
- API: `http://localhost:3000`
- Mongo: disponível na rede interna como `mongo:27017`

- Endpoints disponíveis:
  - GET `/` → status da API
  - GET `/api/v1/age-groups` → lista grupos
  - POST `/api/v1/age-groups` → cria grupo
  - DELETE `/api/v1/age-groups/{group_id}` → apaga grupo

### Testar via curl (comandos em linha única)
Com o `docker compose up` em execução:

1) Criar grupo etário
```bash
curl -s -X POST http://localhost:3000/api/v1/age-groups -H "Content-Type: application/json" -d '{"name":"Infantil","min_age":6,"max_age":10}' | jq .
```

2) Listar grupos
```bash
curl -s http://localhost:3000/api/v1/age-groups | jq .
```

3) Deletar o primeiro grupo retornado (automático, sem substituições manuais)
```bash
curl -i -s -X DELETE http://localhost:3000/api/v1/age-groups/$(curl -s http://localhost:3000/api/v1/age-groups | jq -r '.[0].id')
```

### Desenvolvimento
- Código principal: `backend/api/app_groups.py`
- Banco/Conexão: `backend/mongo/db.py`
- Compose: `docker-compose.yml`.
