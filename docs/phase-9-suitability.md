# Fase 9 — Questionário e carteira sugerida

## O que foi implementado

- Questionário com objetivo de longevidade, dividendos, longo prazo ou curto prazo.
- Pontuação de risco baseada em horizonte, liquidez, reação a perdas, experiência, reserva de emergência e tolerância a risco.
- Classificação em conservador, moderado ou agressivo.
- Carteira modelo por classes de ativos, com percentuais para cada combinação de objetivo e risco.
- Histórico versionado das respostas, da pontuação e da recomendação.
- Status de validação pendente, aprovada, rejeitada ou substituída.
- Tela mobile para responder, refazer e consultar a carteira sugerida.
- Painel Advisor para revisar, aprovar ou solicitar nova avaliação.

## Atualizar o banco

Na pasta raiz do projeto, com a API parada ou em uma janela separada, execute:

```bash
cd /home/vitor-ligorio/talentum
.venv/bin/alembic -c backend/alembic.ini upgrade head
```

Se a API estiver dentro do Docker, execute o mesmo comando dentro do container responsável pelo backend.

## Rotas principais

- `GET /clients/me/suitability/questionnaire`
- `GET /clients/me/suitability`
- `POST /clients/me/suitability`
- `GET /clients/{client_id}/suitability` — Advisor/Admin
- `POST /clients/{client_id}/suitability/{assessment_id}/review` — Advisor/Admin

As carteiras são referências educacionais por classe de ativo. A implementação não envia ordens e mantém a validação do Advisor como etapa obrigatória.

