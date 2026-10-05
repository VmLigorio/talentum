# Fase 9 — Questionário e carteira sugerida

## O que foi implementado

- Questionário com objetivo de longevidade, dividendos, longo prazo ou curto prazo.
- Pontuação de risco baseada em horizonte, liquidez, reação a perdas, experiência, reserva de emergência e tolerância a risco.
- Classificação em conservador, moderado ou agressivo.
- Carteira modelo por classes de ativos, com percentuais para cada combinação de objetivo e risco.
- Subcategorias de bancos, energia, FIIs de papel/CRI, imóveis diversificados, shopping e logística, com tickers apenas como exemplos para revisão do Advisor.
- Resposta do cliente após aprovação do Advisor: aceita, recusada ou ajustes solicitados, com data, observação e trilha de auditoria.
- Histórico versionado das respostas, da pontuação e da recomendação.
- Status de validação pendente, aprovada, rejeitada ou substituída.
- Tela mobile para responder, refazer e consultar a carteira sugerida.
- Painel Advisor para revisar, aprovar ou solicitar nova avaliação.
- Resumo de renda, despesas, patrimônio cadastrado e metas ativas exibido ao cliente antes do envio.
- Confirmação explícita da situação financeira, protegida por uma versão dos dados para evitar confirmar um resumo desatualizado.
- Cópia da situação confirmada anexada à avaliação e exibida ao Advisor na revisão.
- Sinalizações de saldo mensal não positivo, metas próximas, ausência de patrimônio cadastrado e passivos não registrados.
- Perguntas separadas sobre produtos conhecidos e já utilizados, tempo de experiência, frequência e volume aproximado das operações e formação/experiência profissional financeira.
- Respostas de conhecimento e histórico exibidas ao Advisor com sinalizações de revisão; elas não elevam automaticamente o perfil de risco nem contam como comprovação documental.
- Lista de próximas ações para a revisão, gerada por objetivo, reserva de emergência, metas próximas, fluxo mensal, experiência declarada e frequência de operações.
- O plano de ações não altera silenciosamente os percentuais base; recomenda-se separar recursos de curto prazo e revisar capacidade antes da aprovação do Advisor.

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
- `POST /clients/me/suitability/{assessment_id}/response` — o cliente registra a resposta somente depois da aprovação do Advisor.
- `GET /clients/{client_id}/suitability` — Advisor/Admin
- `POST /clients/{client_id}/suitability/{assessment_id}/review` — Advisor/Admin

As carteiras são referências educativas por objetivo e perfil. Os tickers são exemplos para análise, não ordens nem recomendação automática de compra. Objetivos de curto prazo não recebem alocação em ações ou FIIs. O aceite do cliente registra sua resposta; não envia ordens. A validação do Advisor continua obrigatória. O patrimônio mostrado soma os itens cadastrados e não desconta dívidas; o sistema ainda não mantém dados de passivos. O cliente deve pedir ao Advisor que atualize renda, patrimônio ou metas incompletas antes de confirmar. O bloco de conhecimento registra declarações do cliente sobre produtos, operações e formação; o Advisor deve avaliar a adequação desses dados antes de validar a carteira.
