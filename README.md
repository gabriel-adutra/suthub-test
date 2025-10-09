# 🏷️ Age Groups & Enrollment API

> **API robusta para cadastro de grupos etários e inscrições, com persistência em MongoDB, mensageria via Redis e processamento assíncrono por worker. Desenvolvida em FastAPI, pronta para rodar via Docker Compose.**

---

## 🚀 Visão Geral

Este projeto entrega uma solução completa para gestão de grupos etários e inscrições, com arquitetura moderna, observabilidade, validação de dados e processamento assíncrono. Ideal para cenários de triagem, eventos, ou qualquer contexto que exija controle de faixas etárias e filas de inscrição.

**Principais recursos:**
- API RESTful com autenticação básica
- Cadastro e consulta de grupos etários
- Inscrição de usuários com validação de CPF
- Fila de processamento via Redis
- Worker assíncrono para persistência e validação
- Código modular, com docstrings de contrato e logging detalhado para facilitar manutenção.

---

## 🧱 Arquitetura

Fluxo resumido: a API valida e registra a intenção de inscrição, publica a mensagem na fila Redis; o worker consome, valida regras (CPF e faixa etária), cria o usuário associado e marca como `completed` ou `rejected` / `failed` conforme o caso.


Diagrama completo: [arquitetura-teste.pdf](./arquitetura-teste.pdf)


---


## �️ Frontend Web (Streamlit)

O projeto inclui uma interface web moderna feita com Streamlit, permitindo:
- Visualizar grupos etários cadastrados
- Realizar inscrições com validação de CPF e faixa etária
- Consultar status de inscrições
- Login via autenticação Basic Auth (mesmas credenciais da API)

### Como acessar
- Após subir os serviços (`docker compose up --build`), acesse: [http://localhost:8501](http://localhost:8501)
- O frontend depende da API estar rodando (porta 3000 por padrão)

### Login
- Ao acessar, será solicitado login (usuário/senha da API)
- As credenciais padrão são:
  - Usuário: `admin`
  - Senha: `admin123`

### Fluxo de uso
1. Faça login na tela inicial
2. Navegue pelas abas:
   - **Grupos**: lista e consulta grupos etários
   - **Inscrições**: envia nova inscrição (nome, idade, CPF)
   - **Status**: consulta status de inscrições enviadas
   - **Sobre**: informações do sistema
3. Mensagens de erro e validação são exibidas diretamente na interface

### Observações
- O frontend realiza validações antes de enviar dados (nome obrigatório, CPF válido)
- Erros da API são exibidos detalhadamente para facilitar diagnóstico
- Logout disponível no menu lateral

## 📦 Estrutura do Projeto

```
backend/
  api/
    app.py                # API principal (FastAPI)
    services/
      enrollment_service.py # Serviço de inscrição
    ...
  worker/
    consumer_enrollment.py # Worker da fila
  mongo/
    db.py                 # Conexão MongoDB
Dockerfile                # Build da API
requirements.txt          # Dependências Python
README.md                 # Documentação
```

---

## ⚡ Como Executar

1. **Clone o projeto:**
   `git clone https://github.com/gabriel-adutra/suthub-test.git && cd suthub-test`
2. **Suba os serviços:**
   `docker compose up --build`

3. **Acesse a API:**
  [http://localhost:3000](http://localhost:3000)
4. **Acesse o Frontend Web:**
  [http://localhost:8501](http://localhost:8501)

---

## 🔐 Autenticação

Todos os endpoints exigem HTTP Basic Auth:
- Usuário: `admin`
- Senha: `admin123`

---

## 📚 Endpoints Principais

### Status da API
- `GET /` → Retorna `{ "status": "ok" }`

### Grupos Etários
- `GET /api/v1/age-groups` → Lista todos os grupos
- `POST /api/v1/age-groups` → Cria novo grupo
- `DELETE /api/v1/age-groups/{group_id}` → Remove grupo

**Exemplo de criação:**
`curl -s -u admin:admin123 -X POST http://localhost:3000/api/v1/age-groups -H "Content-Type: application/json" -d '{"name":"Adulto","min_age":18,"max_age":99}' | jq .`

**Exemplo de listagem:**
`curl -s -u admin:admin123 http://localhost:3000/api/v1/age-groups | jq .`

**Exemplo de remoção:**
`curl -i -s -u admin:admin123 -X DELETE "http://localhost:3000/api/v1/age-groups/<GROUP_ID>"`

**Erros comuns:**
- `400 Bad Request`: Campos obrigatórios ausentes
- `409 Conflict`: Sobreposição de faixa
- `404 Not Found`: Grupo não encontrado

### Inscrição (Enrollment)
- `POST /api/v1/enrollments` → Solicita inscrição
- `GET /api/v1/enrollments/{enrollment_id}` → Consulta status da inscrição

**Exemplo de inscrição:**
`curl -s -u admin:admin123 -X POST http://localhost:3000/api/v1/enrollments -H "Content-Type: application/json" -d '{"name":"Joao Silva","age":30,"cpf":"09702414458"}' | jq .`

**Retorno esperado:**
```json
{
  "enrollment_id": "<ID>",
  "status": "queued"
}
```

**Exemplo de consulta de status:**
`curl -s -u admin:admin123 http://localhost:3000/api/v1/enrollments/<ID> | jq .`

**Erros comuns:**
- `422 Unprocessable Entity`: CPF inválido ou idade fora de faixa
- `400 Bad Request`: Campos obrigatórios ausentes
- `404 Not Found`: Inscrição não encontrada

---

## 📨 Mensageria & Worker

- Toda inscrição é enfileirada no Redis
- O worker (`backend/worker/consumer_enrollment.py`) consome a fila e persiste no MongoDB
- Status da inscrição:
- `queued`: aguardando processamento
- `processing`: sendo processada pelo worker
- `completed`: inscrição processada e usuário persistido
- `failed`: erro de fila ou processamento
- `rejected`: inscrição rejeitada (CPF inválido ou faixa etária não encontrada)

---

## 🧑‍💻 Testes & Troubleshooting

- Certifique-se que todos os containers estão "healthy" (API, Mongo, Redis, Worker)
- Para logs detalhados, utilize:
  `docker compose logs api` e 
  `docker compose logs worker`
- Para testar CPF, use apenas números (sem pontos ou hífen)

---

## 🧪 Ambiente de Testes & Integração via Docker

O projeto inclui um container dedicado para testes de integração, permitindo rodar todos os testes automatizados em ambiente isolado, simulando o fluxo real do usuário e dos serviços.

### Como funciona o ambiente de testes
- O serviço de testes é definido no `docker-compose.yml` e utiliza um Dockerfile próprio em `backend/api/tests/Dockerfile`.
- O container de testes sobe junto com os demais serviços (API, MongoDB, Redis, Worker, Frontend), garantindo que todos os endpoints e integrações estejam disponíveis.
- Os testes utilizam `pytest` e cobrem todos os principais fluxos da API, incluindo casos de sucesso e erro.

### Como rodar os testes de integração manualmente
1. Certifique-se que todos os containers estão rodando:
   ```bash
   docker compose up --build
   ```
2. Execute os testes manualmente dentro do container de testes:
   ```bash
   docker compose exec test pytest -s --log-cli-level=INFO tests/testFastAPI.py
   ```

3. Os logs detalhados dos testes serão exibidos no terminal, facilitando o diagnóstico e validação dos endpoints.

### Observações
- O ambiente de testes é totalmente isolado, não interfere nos dados reais do banco.
- Os testes podem ser adaptados para rodar em pipelines CI/CD, garantindo qualidade contínua.
- Para logs detalhados dos serviços, utilize também:
  ```bash
  docker compose logs api
  docker compose logs worker
  docker compose logs test
  ```

---


## 🤝 Dùvidas?

Entre em contato através do email gabriel.adutra@ufpe.br
