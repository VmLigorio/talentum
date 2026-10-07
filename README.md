# Talentum

Plataforma de organização, planejamento e acompanhamento patrimonial.

## MVP v0.1

O primeiro produto será um Concierge MVP para os primeiros clientes pagantes:

- autenticação e perfis;
- dashboard básico;
- patrimônio;
- metas;
- relatórios;
- permissões configuráveis por cliente;
- operação interna pelo Talentum Advisor.

Integrações bancárias, cotações em tempo real, IA, home broker, pagamentos e gestão discricionária ficam fora do primeiro ciclo.

## Estrutura

```text
talentum/
├── backend/   API FastAPI e domínio do produto
├── mobile/    aplicativo Flutter do cliente
├── advisor/   painel web do Advisor
├── docs/      decisões e documentação do produto
└── README.md
```

## Backend

```bash
cd backend
source .venv/bin/activate
uvicorn app.main:app --reload
```

Endpoints iniciais:

- `GET /health` — verifica se a API está disponível;
- `GET /docs` — documentação interativa da API.
- `POST /auth/login` — inicia uma sessão;
- `POST /auth/refresh` — gira o refresh token;
- `POST /auth/logout` — revoga as sessões do usuário autenticado;
- `POST /auth/change-password` — altera a senha e revoga as sessões anteriores;
- `POST /admin/users` — cria clientes ou Advisors pelo painel administrativo;
- `GET /admin/users` — lista contas internas para administração;
- `PATCH /admin/users/{id}/status` — ativa ou desativa o acesso de um usuário;
- `POST /admin/users/{id}/reset-password` — define uma nova senha temporária e revoga sessões anteriores;
- `GET /auth/me` — retorna o usuário autenticado.
- `GET /clients` — lista clientes para administradores e consultores;
- `GET /clients/{id}` — consulta um cliente autorizado;
- `GET/PUT /clients/{id}/profile` — consulta ou atualiza nome e telefone do cliente;
- `GET /clients/advisors` — lista Advisors ativos para administradores;
- `PUT /clients/{id}/assignment` — vincula ou desvincula um cliente de um Advisor;
- `GET /clients/{id}/audit-log` — consulta o histórico de alterações autorizado;
- `GET /clients/{id}/permissions` — consulta permissões;
- `PUT /clients/{id}/permissions` — atualiza permissões e registra auditoria;
- `GET /clients/me/permissions` — consulta as próprias permissões.
- `GET/PUT /clients/{id}/financial-profile` — consulta ou atualiza o perfil financeiro;
- `GET/POST /clients/{id}/patrimony` — consulta ou cadastra patrimônio;
- `PATCH/DELETE /clients/{id}/patrimony/{item_id}` — altera ou remove patrimônio;
- `GET/POST /clients/{id}/goals` — consulta ou cadastra metas;
- `PATCH/DELETE /clients/{id}/goals/{goal_id}` — altera ou remove metas.
- `GET /clients/{id}/dashboard` — consolida patrimônio, distribuição e metas;
- `GET /clients/{id}/action-plan` — consulta o plano de ação do cliente;
- `POST/PATCH/DELETE /clients/{id}/action-plan` — gerencia ações do cliente pelo Advisor;
- `GET /clients/{id}/reports` — lista relatórios autorizados;
- `POST/PATCH /clients/{id}/reports` — cria ou atualiza relatórios pelo Advisor.
- `DELETE /clients/{id}/reports/{report_id}` — remove rascunhos; relatórios publicados são preservados.
- `GET /clients/{id}/documents` — lista documentos autorizados;
- `POST /clients/{id}/documents` — envia PDF, PNG, JPG ou TXT de até 10 MB;
- `GET /clients/{id}/documents/{document_id}/download` — baixa um documento autorizado;
- `DELETE /clients/{id}/documents/{document_id}` — remove documentos pelo Advisor ou administrador.
- `GET /notifications` — lista alertas do usuário autenticado;
- `GET /notifications/unread-count` — retorna somente a quantidade de alertas não lidos;
- `PATCH /notifications/{id}/read` — marca um alerta como lido;
- `PATCH /notifications/read-all` — marca todos os alertas como lidos.
- `GET/PATCH /notifications/preferences` — consulta ou atualiza preferências por categoria.
- `GET /market/search?q=PETR4&market=br` — pesquisa ativos da B3 para administradores e Advisors;
- `GET /market/search?q=AAPL&market=global` — pesquisa ativos internacionais;
- `GET /market/search?q=PETR4&market=all` — pesquisa nos dois mercados com avisos por fonte.
- `GET /market/details?symbol=MXRF11&market=br` — indicadores ampliados e relatório mensal de FII baseado em dados enviados à CVM.
- `GET /market/history?symbol=PETR4&market=br&period=1y` — histórico diário e comparação com o Ibovespa ou S&P 500.
- `GET/POST /market/alerts` — consulta ou cria alertas de preço vinculados a um cliente.
- `PATCH/DELETE /market/alerts/{alert_id}` — pausa, reativa, altera ou desativa um alerta.
- `GET/POST /market/watchlist` — consulta ou adiciona ativos à lista de acompanhamento de um cliente.
- `DELETE /market/watchlist/{item_id}` — remove um ativo da lista de acompanhamento.
- `GET /clients/{id}/investment-portfolio` — consolida posições, cotações, resultado e alocação do cliente.
- `GET/POST /clients/{id}/investment-transactions` — consulta ou registra compras e vendas; o registro atualiza o saldo e o custo médio, incluindo taxas e resultado realizado de vendas.
- `POST /clients/{id}/investment-positions` — cadastra uma posição de investimento.
- `PATCH/DELETE /clients/{id}/investment-positions/{position_id}` — altera ou remove uma posição.
- `GET /clients/{id}/investment-analytics?period=1y` — calcula retorno histórico, contribuição, benchmarks e alertas de leitura.

Para criar o primeiro usuário administrativo depois de aplicar as migrations:

```bash
cd backend
.venv/bin/python -m app.seed --name "Administrador" --email admin@talentum.local --role admin
```

O comando solicitará a senha sem exibi-la no terminal.

Se esquecer a senha, redefina-a pelo e-mail:

```bash
cd backend
.venv/bin/python -m app.reset_password --email admin@talentum.local
```

## Banco de dados

Com Docker instalado, suba o PostgreSQL de desenvolvimento:

```bash
docker compose up -d postgres
cd backend
alembic upgrade head
```

Ao executar a API diretamente no host, use o `.env.example` do backend: o Compose publica o PostgreSQL na porta `5433` do host. Dentro do Compose, a API usa o nome do serviço `postgres` e a porta interna `5432`.

Para subir PostgreSQL e a API juntos pelo Docker Compose:

```bash
docker compose up -d --build
```

A API do Compose local fica disponível em `http://127.0.0.1:8001` neste ambiente, pois a porta `8000` pode estar
sendo usada pela API executada diretamente no host. Dentro do Docker, a API continua ouvindo na porta `8000`.
Antes de um ambiente real, use o Compose de produção descrito em [docs/phase-7.md](docs/phase-7.md).

O arquivo `.env.example` contém a configuração esperada. Copie-o para `.env` e altere os segredos antes de executar a aplicação.

O módulo de pesquisa de investimentos consulta a Brapi para ativos da B3 e o endpoint de busca do
Yahoo Finance para o mercado internacional. As credenciais, URLs e timeout ficam no backend; nenhuma
chave de provedor é exposta no navegador. Os dados são informativos e podem ter atraso. Antes de uso
comercial em produção, valide licenciamento, limites e estabilidade da fonte internacional ou troque-a
por um provedor contratado.

O histórico também retorna volatilidade anualizada, maior drawdown, volume médio e quantidade de
observações para apoiar a leitura do Advisor. Essas métricas são descritivas e não substituem análise
profissional.

O painel também permite selecionar até três ativos e comparar seus retornos históricos normalizados.
Após carregar a comparação, a análise pode ser exportada para impressão ou salva como PDF pelo navegador.

O escopo concluído da fase 2 está documentado em [docs/phase-2.md](docs/phase-2.md).

Alertas de preço podem ser criados pelo cliente ou pelo Advisor/Admin para um cliente autorizado. A condição
pode ser “atingir ou ficar abaixo” ou “atingir ou superar”. A cotação é verificada quando o Talentum atualiza
as notificações; ao atingir o alvo, o alerta muda para disparado e gera uma notificação deduplicada para o
cliente e seu Advisor. Em produção, essa rotina deve ser executada também por um agendador de tarefas para
verificação contínua.

Enquanto a API estiver em execução, o monitor automático verifica os alertas ativos a cada 300 segundos por
padrão. O intervalo pode ser ajustado por `MARKET_ALERT_CHECK_INTERVAL_SECONDS`; valores menores que 30
segundos são protegidos para evitar excesso de consultas aos provedores.

O painel Advisor/Admin também oferece uma lista de acompanhamento por cliente, com cotação atual, fonte do dado
e atalho para abrir novamente a pesquisa do ativo.

A fase 3 adiciona a carteira consolidada por cliente no [docs/phase-3.md](docs/phase-3.md). O valor atualizado
é calculado por posição com as cotações disponíveis; carteiras com BRL e USD exibem totais separados por moeda,
sem conversão cambial implícita.

A fase 4 adiciona a análise histórica da carteira no [docs/phase-4.md](docs/phase-4.md), incluindo comparação
com benchmarks e relatório imprimível no painel Advisor/Admin.

A fase 5 adiciona snapshots persistentes da carteira por moeda, histórico de evolução no painel Advisor/Admin,
captura manual, captura automática configurável por `PORTFOLIO_SNAPSHOT_INTERVAL_SECONDS` e o endpoint
`/health/ready`, que valida a conexão com o banco. Consulte [docs/phase-5.md](docs/phase-5.md) para o fluxo
operacional e as limitações atuais de notificações externas.

A fase 6 adiciona endurecimento para produção e auditoria de segurança: rate limit de login, validação de segredos,
cabeçalhos HTTP, limite de requisições, hosts confiáveis, desligamento opcional da documentação pública e validação
mais rígida de uploads. O relatório está em [docs/phase-6.md](docs/phase-6.md).

As medidas operacionais complementares estão preparadas no Compose: Redis, ClamAV e healthcheck da API. O backup
manual pode ser executado com `POSTGRES_PASSWORD=... bash ops/backup_postgres.sh`; configure armazenamento remoto,
TLS e segredos reais antes de expor o sistema na internet.

A fase 7 adiciona o Compose de produção, pré-verificação, restauração protegida, checksum de backups, isolamento
de portas e endurecimento do container da API. Consulte [docs/phase-7.md](docs/phase-7.md).

A fase 8 aplica uma avaliação interna baseada na ISO/IEC 25010:2023, adiciona resiliência às consultas de mercado,
cache curto, retry de transporte, observabilidade segura por request ID e critérios de qualidade documentados em
[docs/phase-8.md](docs/phase-8.md).

## Testes

```bash
cd backend
pytest
```

Os testes de integração de autorização usam PostgreSQL e exigem `TEST_DATABASE_URL` apontando para um banco descartável cujo nome termine em `_test` ou `_testing`. Nunca aponte essa variável para o banco de desenvolvimento ou produção. A CI sobe um PostgreSQL temporário e aplica as migrations antes dos testes; sem essa variável, os testes de integração são pulados.

## Status do MVP

O backend, o painel Advisor e o aplicativo Mobile já estão integrados para o fluxo do cliente:
login, dashboard, patrimônio, metas, plano de ação, relatórios, documentos e alertas. A lista
de recursos fora do MVP continua em `docs/mvp-v0.1.md`.
