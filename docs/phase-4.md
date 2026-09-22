# Talentum — Fase 4

## Objetivo

Transformar a carteira consolidada em uma camada de análise histórica para o Advisor/Admin, mantendo
uma leitura informativa, auditável e sem execução de ordens.

## Entregas

- retorno histórico por posição para 1 mês, 3 meses, 6 meses, 1 ano ou 5 anos;
- retorno ponderado por moeda e contribuição de cada posição;
- comparação com Ibovespa para ativos brasileiros e S&P 500 para ativos internacionais;
- alertas de concentração superior a 40%, dados ausentes e mistura de moedas;
- relatório imprimível da carteira com período, posições, retornos e alertas de leitura;
- endpoint protegido por cliente e vínculo de Advisor;
- tratamento de indisponibilidade dos provedores sem interromper a análise inteira;
- documentação, validação de sintaxe e testes automatizados.

## Limites

Os retornos dependem do histórico fornecido pelos provedores e das posições informadas. A análise não
é recomendação de investimento, não converte moedas e não executa ordens.
