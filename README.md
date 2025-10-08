docker compose up --build

# Age Groups & Enrollment API

API completa para cadastro de grupos etários e inscrições, com persistência em MongoDB, mensageria via Redis e processamento assíncrono por worker. Desenvolvida em FastAPI, pronta para rodar via Docker Compose.

## Arquitetura
- **FastAPI**: expõe endpoints REST protegidos por autenticação básica
- **MongoDB**: armazena grupos etários e inscrições
- **Redis**: fila de inscrições (mensageria)
- **Worker**: consome fila e persiste inscrições

## Pré-requisitos
- Docker e Docker Compose
- jq (opcional, para formatar JSON)

## Como rodar
1. Clone o projeto e acesse a pasta raiz (onde está o `docker-compose.yml`)
2. Execute:
   ```bash
   docker compose up --build
   ```
3. Acesse a API em: [http://localhost:3000](http://localhost:3000)

## Endpoints

### Autenticação
Todos os endpoints exigem HTTP Basic Auth:
- Usuário: `admin`
- Senha: `admin123`

### 1. Status da API
- `GET /`
  - Retorna `{"status": "ok"}`

### 2. Grupos Etários
- `GET /api/v1/age-groups` — Lista todos os grupos
- `POST /api/v1/age-groups` — Cria novo grupo
- `DELETE /api/v1/age-groups/{group_id}` — Remove grupo

**Exemplo de criação:**
```bash
curl -s -u admin:admin123 -X POST http://localhost:3000/api/v1/age-groups \
  -H "Content-Type: application/json" \
  -d '{"name":"Adulto","min_age":18,"max_age":99}' | jq .
```

**Exemplo de listagem:**
```bash
curl -s -u admin:admin123 http://localhost:3000/api/v1/age-groups | jq .
```

**Exemplo de remoção:**
```bash
curl -i -s -u admin:admin123 -X DELETE "http://localhost:3000/api/v1/age-groups/<GROUP_ID>"
```

**Erros comuns:**
- Campos obrigatórios ausentes: `400 Bad Request`
- Sobreposição de faixa: `409 Conflict`
- Grupo não encontrado: `404 Not Found`

### 3. Inscrição (Enrollment)
- `POST /api/v1/enrollments` — Solicita inscrição
- `GET /api/v1/enrollments/{enrollment_id}` — Consulta status da inscrição

**Exemplo de inscrição:**
```bash
curl -s -u admin:admin123 -X POST http://localhost:3000/api/v1/enrollments \
  -H "Content-Type: application/json" \
  -d '{"name":"Joao Silva","age":30,"cpf":"09702414458"}' | jq .
```
Retorno:
```json
{
  "enrollment_id": "<ID>",
  "status": "queued"
}
```

**Exemplo de consulta de status:**
```bash
curl -s -u admin:admin123 http://localhost:3000/api/v1/enrollments/<ID> | jq .
```

**Erros comuns:**
- CPF inválido: `422 Unprocessable Entity` — "CPF inválido (digitos verificadores ou formato)"
- Idade fora de faixa: `422 Unprocessable Entity` — "Nenhuma faixa etária encontrada para a idade informada"
- Campos obrigatórios ausentes: `400 Bad Request`
- Inscrição não encontrada: `404 Not Found`

## Mensageria e Worker
- Toda inscrição é enfileirada no Redis
- O worker (`backend/worker/consumer_enrollment.py`) consome a fila e persiste no MongoDB
- Status da inscrição: `queued` (aguardando processamento), `failed` (erro de fila), ou outros conforme evolução

## Estrutura do Projeto
- `backend/api/app.py` — API principal
- `backend/worker/consumer_enrollment.py` — Worker da fila
- `backend/mongo/db.py` — Conexão MongoDB
- `docker-compose.yml` — Orquestração dos serviços

## Dicas de Troubleshooting
- Certifique-se que todos os containers estão "healthy" (API, Mongo, Redis, Worker)
- Use logs do Docker para investigar problemas:
  ```bash
  docker compose logs api
  docker compose logs worker
  ```
- Se receber erro de conexão, aguarde alguns segundos após subir os serviços
- Para testar CPF, use apenas números (sem pontos ou hífen)

## Observações
- O projeto é didático e pode ser expandido para testes automatizados, masking de dados sensíveis, métricas, etc.

---
Para dúvidas ou sugestões, abra uma issue!
