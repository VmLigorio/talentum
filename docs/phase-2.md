# Talentum — Fase 2

## Objetivo

Entregar o módulo Desktop de pesquisa e acompanhamento de investimentos para Advisor e administrador,
com dados informativos da B3 e do mercado internacional, controles por cliente e uma experiência segura
para apoiar a análise profissional.

## Critérios de conclusão

- [x] Pesquisa por ticker ou nome no Brasil, exterior ou nos dois mercados.
- [x] Detalhamento do ativo com preço, variação, volume, indicadores disponíveis e moeda.
- [x] Referências regulatórias e informe mensal de FIIs quando a fonte disponibilizar os dados.
- [x] Histórico com períodos configuráveis, benchmark, escala lateral, volatilidade e drawdown.
- [x] Comparação de até três ativos com ranking e exportação para impressão/PDF.
- [x] Tratamento de indisponibilidade e resultados parciais dos provedores.
- [x] Alertas de preço por cliente, com condições de alta/baixa, pausa, reativação e rearmamento.
- [x] Monitor automático de alertas e notificações deduplicadas para cliente e Advisor.
- [x] Lista de acompanhamento por cliente, com cotação atual, fonte, atalho de pesquisa e remoção.
- [x] Autorização por papel e vínculo de Advisor aplicada no backend.
- [x] Auditoria das operações de alertas e lista de acompanhamento.
- [x] Migrações, documentação, testes automatizados e validação da API em execução.

## Entrega técnica

O módulo é servido pela API FastAPI e consumido pelo painel web do Advisor. Os provedores continuam
isolados no backend; credenciais não chegam ao navegador. O PostgreSQL local está na revisão
`0011_create_market_watchlist`.

Os dados de mercado são informativos e podem ter atraso. A fase não inclui execução de ordens,
custódia, Open Finance, recomendação automática ou cotação em tempo real licenciada.
