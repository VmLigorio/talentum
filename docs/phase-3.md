# Talentum — Fase 3

## Objetivo

Entregar uma carteira consolidada por cliente, conectando posições informadas pelo Advisor/Admin às
cotações disponíveis no módulo de pesquisa e exibindo uma visão segura para o cliente no Mobile.

## Entregas

- posições por cliente com ticker, mercado, quantidade, preço médio, instituição e observações;
- valor investido, cotação atual, valor atualizado e resultado por posição;
- alocação por mercado e moeda;
- totais separados por moeda, sem conversão cambial artificial;
- indicação de posições sem cotação disponível;
- criação, edição e remoção autorizadas pelo backend;
- auditoria das alterações;
- visão consolidada no Advisor/Admin;
- visão de acompanhamento no Mobile com cache offline;
- migração, documentação e testes automatizados.

## Limites

Esta fase não executa ordens, importa custódia automaticamente, calcula conversão cambial ou substitui
o extrato da corretora. Os valores dependem das posições informadas e da disponibilidade das fontes de
mercado.
