# API corporativa de gestão de ativos

API REST em Python 3.12+ para parques de impressão/computadores, ordens de serviço, SLA e estoque de toners FIFO. Usa FastAPI, Pydantic v2, SQLAlchemy 2, Alembic e PostgreSQL 16. O frontend pode ser feito em HTML/CSS/JavaScript e consumir os endpoints JSON; CORS local fica configurado para `localhost:5500` e `127.0.0.1:5500`.

## Executar com Docker Compose

1. Copie `.env.example` para `.env` e altere `POSTGRES_PASSWORD`, `DATABASE_URL` e `SECRET_KEY`. Use uma senha PostgreSQL sem caracteres que precisem de escape na URL ou codifique-os corretamente.
2. Na raiz do projeto:

```bash
docker compose up --build -d
docker compose ps
```

O Compose aguarda o PostgreSQL 16 ficar saudável. O container da API executa `alembic upgrade head` antes de iniciar o Uvicorn em `0.0.0.0:8000`; a API fica disponível em `http://localhost:8000`, a documentação interativa em `/docs` e o health check em `/health`. O volume `postgres_data` mantém os dados entre reinicializações.

3. Crie o primeiro ADMIN localmente no container. O comando pede nome, e-mail e senha sem colocá-la no histórico do shell:

```bash
docker compose exec api python -m toner_api.cli create-admin
```

Para execução sem Docker, use um PostgreSQL 16 acessível, instale `requirements.txt`, configure `DATABASE_URL` com host `localhost`, aplique `alembic upgrade head`, execute `python -m toner_api.cli create-admin` e depois `python main.py`. A API requer autenticação; não existe usuário ou senha padrão.

## Configuração

| Variável | Uso |
| --- | --- |
| `APP_NAME`, `APP_ENV`, `DEBUG` | Identificação e modo da aplicação |
| `DATABASE_URL` | URL SQLAlchemy, por exemplo `postgresql+psycopg://usuario:senha@db:5432/asset_management` |
| `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` | Banco e credenciais do serviço PostgreSQL no Compose |
| `POSTGRES_PORT`, `API_PORT` | Portas publicadas no host; padrões `5432` e `8000` |
| `API_HOST` | Endereço de escuta ao iniciar com `python main.py`; padrão `127.0.0.1` |
| `CORS_ORIGINS` | Origens web permitidas, separadas por vírgula |
| `SECRET_KEY` | Chave aleatória forte usada para assinar JWT; obrigatória trocar antes de uso real |
| `JWT_ALGORITHM` | Algoritmo JWT; padrão `HS256` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Validade do access token; padrão 480 minutos (8 horas) |
| `REFRESH_TOKEN_EXPIRE_DAYS` | Validade do refresh token; padrão 7 dias |

O `.env.example` contém todas as variáveis esperadas. Não versione `.env` nem reutilize os segredos de exemplo em produção.

## Autenticação e paginação

Faça login com `POST /auth/login` enviando JSON com `email` e `senha`; use o `access_token` retornado no botão `Authorize` do `/docs` (ou como `Authorization: Bearer ...`). O botão `Authorize` recebe um token, não as credenciais. Envie o `refresh_token` para `POST /auth/refresh` para renovar o par. `GET /auth/me` retorna o usuário autenticado. O bootstrap inicial do ADMIN é feito pelo comando CLI acima; os demais usuários são geridos por ADMIN em `/usuarios`.

Listagens aceitam `limit` (padrão 50, máximo 200) e `offset` (padrão 0) e retornam `items`, `total`, `limit` e `offset`. Erros de negócio retornam `422`, recursos inexistentes `404` e conflitos (por exemplo, saldo insuficiente ou duplicidade) `409`. A autenticação retorna `401` e a falta de permissão `403`.

## Fluxos principais com curl

Defina a URL e autentique um ADMIN:

```bash
BASE=http://localhost:8000
curl -s -X POST "$BASE/auth/login" -H 'Content-Type: application/json' \
  -d '{"email":"admin@example.com","senha":"SENHA_DO_ADMIN"}'
```

Copie o `access_token` da resposta para `TOKEN` e use o cabeçalho abaixo nos exemplos protegidos:

```bash
TOKEN=ACCESS_TOKEN_RECEBIDO
AUTH="Authorization: Bearer $TOKEN"
```

### Usuários e autenticação

ADMIN lista, cria, atualiza e desativa contas. `DELETE` desativa a conta sem remover referências históricas.

```bash
curl "$BASE/usuarios?limit=50&offset=0" -H "$AUTH"
curl -X POST "$BASE/usuarios" -H "$AUTH" -H 'Content-Type: application/json' \
  -d '{"nome":"Técnico 1","email":"tecnico@example.com","senha":"SENHA_FORTE_COM_12","perfil":"TECNICO","setor":"TI"}'
curl -X PATCH "$BASE/usuarios/UUID" -H "$AUTH" -H 'Content-Type: application/json' \
  -d '{"setor":"Infraestrutura","ativo":true}'
curl -X DELETE "$BASE/usuarios/UUID" -H "$AUTH"
curl "$BASE/auth/me" -H "$AUTH"
curl -X POST "$BASE/auth/refresh" -H 'Content-Type: application/json' -d '{"refresh_token":"REFRESH_TOKEN"}'
```

### Equipamentos e parque

Para impressoras, informe `modelo_toner_compativel`, `contador_paginas` e `ip_rede`; campos de computador devem ficar nulos. Para computadores, informe `hostname`, `sistema_operacional`, `memoria_ram_gb` e `armazenamento_gb`; campos de impressora devem ficar nulos.

```bash
curl -X POST "$BASE/equipamentos" -H "$AUTH" -H 'Content-Type: application/json' \
  -d '{"tipo":"IMPRESSORA","patrimonio":"PAT-101","numero_serie":"SN-101","marca":"Fabricante","modelo":"Laser 101","localizacao":"TI / sala 1","responsavel_id":"UUID_USUARIO","papel_no_parque":"EM_USO","modelo_toner_compativel":"TN-100","contador_paginas":0,"ip_rede":"10.0.0.10"}'
curl "$BASE/equipamentos?tipo=IMPRESSORA&papel_no_parque=BACKUP&limit=50&offset=0" -H "$AUTH"
curl "$BASE/equipamentos/parque" -H "$AUTH"
curl -X POST "$BASE/equipamentos/UUID_BACKUP/promover-backup" -H "$AUTH"
curl -X PATCH "$BASE/equipamentos/UUID" -H "$AUTH" -H 'Content-Type: application/json' \
  -d '{"status_operacional":"MANUTENCAO"}'
curl -X DELETE "$BASE/equipamentos/UUID" -H "$AUTH"
```

Ao promover um backup, o equipamento em uso do mesmo responsável/localização passa para `BACKUP`. A exclusão é lógica (`DESCARTADO`) para preservar o histórico e é recusada se houver OS aberta.

### Ordens de serviço e SLA

O solicitante abre OS; o ADMIN atribui um técnico; o técnico atribuído conduz as transições. Solicitantes só consultam suas próprias OS e só podem responder enquanto o status for `AGUARDANDO_USUARIO`.

```bash
curl -X POST "$BASE/os" -H "$AUTH" -H 'Content-Type: application/json' \
  -d '{"equipamento_id":"UUID_EQUIPAMENTO","tipo":"CORRETIVA","prioridade":"ALTA","descricao_problema":"Impressora não imprime"}'
curl "$BASE/os?status=ABERTA&prioridade=ALTA&limit=50&offset=0" -H "$AUTH"
curl -X PATCH "$BASE/os/UUID_OS/atribuir-tecnico" -H "$AUTH" -H 'Content-Type: application/json' \
  -d '{"tecnico_id":"UUID_TECNICO"}'
curl -X PATCH "$BASE/os/UUID_OS/status" -H "$AUTH" -H 'Content-Type: application/json' \
  -d '{"status":"EM_ANDAMENTO"}'
curl -X PATCH "$BASE/os/UUID_OS/status" -H "$AUTH" -H 'Content-Type: application/json' \
  -d '{"status":"RESOLVIDA","solucao_aplicada":"Toner substituído e teste concluído"}'
curl "$BASE/os/UUID_OS/historico?limit=50&offset=0" -H "$AUTH"
curl "$BASE/os/dashboard" -H "$AUTH"
```

Um solicitante responde com `PATCH /os/{id}` e body `{"resposta_solicitante":"Pode prosseguir"}`. Uma OS corretiva não pode ser aberta em equipamento `BACKUP`; promova-o primeiro pelo endpoint do parque. As transições permitidas são `ABERTA → EM_ANDAMENTO/CANCELADA`, `EM_ANDAMENTO → AGUARDANDO_USUARIO/AGUARDANDO_PECA/RESOLVIDA/CANCELADA`, estados de espera → `EM_ANDAMENTO/CANCELADA`; `RESOLVIDA` só pode ser reaberta por ADMIN para `EM_ANDAMENTO`, e `CANCELADA` é terminal. Toda mudança gera histórico e resolver exige solução não vazia.

Os SLAs iniciais são BAIXA 24h/72h, MEDIA 8h/48h, ALTA 4h/24h e CRITICA 1h/8h (resposta/resolução). O relógio considera apenas intervalos ativos de expediente, exclui feriados e começa na próxima janela se a OS for aberta fora do horário. Ao aguardar usuário, o relógio pausa e o tempo útil pausado é adicionado aos prazos. As respostas incluem prazos, horas úteis decorridas/restantes, status e excedente; `EM_RISCO` significa menos de 20% do prazo aplicável.

### Toners FIFO

ADMIN cadastra o toner; ADMIN ou técnico registra entrada e consumo. Cada entrada cria lote e movimentação de auditoria. As saídas consomem os lotes por `data_entrada` (e ID para desempate), dividem a quantidade quando necessário e não usam lotes vencidos.

```bash
curl -X POST "$BASE/toners" -H "$AUTH" -H 'Content-Type: application/json' \
  -d '{"modelo":"TN-100","cor":"PRETO","compatibilidade":["Laser 101"],"estoque_minimo":2}'
curl -X POST "$BASE/toners/UUID_TONER/lotes" -H "$AUTH" -H 'Content-Type: application/json' \
  -d '{"numero_lote":"L-2026-01","data_entrada":"2026-11-24T10:00:00Z","quantidade":10,"validade":"2027-12-31","fornecedor":"Fornecedor A"}'
curl -X POST "$BASE/toners/UUID_TONER/consumir" -H "$AUTH" -H 'Content-Type: application/json' \
  -d '{"quantidade":3,"os_id":"UUID_OS","observacao":"Troca preventiva"}'
curl "$BASE/toners/UUID_TONER/fifo?limit=50&offset=0" -H "$AUTH"
curl "$BASE/toners/estoque-critico?limit=50&offset=0" -H "$AUTH"
curl "$BASE/toners/UUID_TONER/movimentacoes?limit=50&offset=0" -H "$AUTH"
```

Se o saldo válido for insuficiente, a API retorna `409` com a quantidade disponível e não grava baixa parcial. Lotes vencidos não entram no saldo consumível. O endpoint FIFO mostra posição e saldo de cada lote.

### Configuração

Somente ADMIN altera SLA, expediente e feriados. O expediente aceita múltiplos intervalos no mesmo dia, sem sobreposição.

```bash
curl "$BASE/sla-config?limit=50&offset=0" -H "$AUTH"
curl -X PUT "$BASE/sla-config" -H "$AUTH" -H 'Content-Type: application/json' \
  -d '[{"prioridade":"BAIXA","horas_limite_resposta":24,"horas_limite_resolucao":72,"considera_horas_uteis":true,"ativo":true}]'
curl -X POST "$BASE/horarios-funcionamento" -H "$AUTH" -H 'Content-Type: application/json' \
  -d '{"dia_semana":0,"hora_inicio":"08:00:00","hora_fim":"12:00:00","ativo":true}'
curl "$BASE/horarios-funcionamento?limit=50&offset=0" -H "$AUTH"
curl -X POST "$BASE/feriados" -H "$AUTH" -H 'Content-Type: application/json' \
  -d '{"data":"2026-12-25","descricao":"Natal"}'
curl "$BASE/feriados?limit=50&offset=0" -H "$AUTH"
```

## Desenvolvimento e testes

Use Python 3.12 ou superior. Para rodar testes unitários e de integração:

```bash
python -m pip install -r requirements.txt
python -m pytest -q
```

Os testes de integração usam banco SQLite temporário para não alterar o PostgreSQL de desenvolvimento. O uso real continua sendo PostgreSQL 16. Antes de produção, configure segredos fortes, backups e origens CORS restritas; restrinja o acesso de rede e monitore os logs JSON.