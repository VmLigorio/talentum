# Fase 8 — Avaliação de qualidade baseada na ISO/IEC 25010:2023

## Escopo e método

Esta é uma avaliação interna de qualidade do produto, não uma certificação ISO. Foi utilizada a edição vigente
da ISO/IEC 25010:2023, que define nove características de qualidade de produto para especificação, medição e
avaliação ao longo do ciclo de vida.

As notas abaixo usam uma escala interna de 0 a 5:

- `0` — inexistente ou não avaliado;
- `1` — inicial, com risco alto;
- `2` — parcialmente implementado;
- `3` — funcional, mas requer validação operacional;
- `4` — bem coberto por código, testes e controles;
- `5` — evidência contínua em produção e critérios operacionais monitorados.

## Resultado da avaliação

| Característica | Nota | Evidências no Talentum | Próximo critério de aceite |
|---|---:|---|---|
| Adequação funcional | 4/5 | Fluxos de Cliente, Advisor e Admin; carteira, metas, relatórios, documentos, alertas e pesquisa de ativos; 40 testes de backend | Testes de aceitação com usuários reais e dados representativos |
| Eficiência de desempenho | 3/5 | Timeouts, limites de payload, cache curto, conexões HTTP reutilizáveis e health check | Medir p95 de rotas e consumo com carga representativa |
| Compatibilidade | 4/5 | API HTTP, Compose, PostgreSQL, Redis, ClamAV e Mobile Flutter; configuração por ambiente | Validar Android, iOS, Linux, navegador e ARM64 do provedor escolhido |
| Capacidade de interação | 3/5 | Mensagens em português, estados de erro, formulários e painel responsivo | Rodar roteiro de usabilidade e acessibilidade com usuários |
| Confiabilidade | 3/5 | Migrações, sessão renovável, retry de transporte, fallback de mercado, cache e `/health/ready` | Testar indisponibilidade de cada dependência e restauração de backup |
| Segurança | 4/5 | Argon2, tokens rotativos, rate limit, autorização por vínculo, auditoria, headers, validação de upload e ClamAV preparado | Inserir segredos reais e executar teste externo antes da exposição pública |
| Manutenibilidade | 4/5 | Separação por API, schemas, serviços e modelos; testes; CI com Bandit e pip-audit; documentação por fase | Aumentar cobertura de integração e adotar lint/type-check no CI |
| Flexibilidade | 3/5 | Variáveis de ambiente, Compose dev/prod, proxy separado, fontes de mercado substituíveis | Validar escala horizontal e armazenamento externo de documentos |
| Segurança operacional (safety) | 3/5 | Alertas informativos, limites, fallback, proteção contra restauração acidental e avisos sobre dados de mercado | Formalizar matriz de riscos, limites de uso e procedimento de incidente |

## Implementações da Fase 8

### Eficiência e confiabilidade de mercado

- respostas de pesquisa, detalhamento e histórico possuem cache curto configurável por
  `MARKET_CACHE_TTL_SECONDS`;
- o cliente HTTP reutiliza conexões e limita conexões simultâneas;
- falhas transitórias de conexão usam `MARKET_RETRY_ATTEMPTS`;
- respostas com aviso de indisponibilidade não são mantidas no cache, permitindo nova tentativa;
- o cache pode ser limpo de forma controlada por `clear_market_cache()`.

### Observabilidade segura

- cada requisição recebe ou preserva um `X-Request-ID` validado;
- a API retorna `X-Response-Time-ms`;
- logs registram rota, método, status, duração e identificador, sem corpo, token ou parâmetros de consulta;
- identificadores inválidos ou excessivamente longos são substituídos por um UUID novo.

### Critérios automatizados

- configuração de resiliência não aceita valores negativos;
- pesquisa repetida usa o cache curto;
- Compose de desenvolvimento e produção continuam válidos;
- testes de backend permanecem obrigatórios no CI;
- health check continua validando a conexão com o banco.

## Limitações conhecidas

- a nota não substitui teste de carga, pentest, auditoria independente ou certificação;
- o cache é por processo e não substitui Redis em uma instalação com múltiplos workers;
- as fontes Brapi e Yahoo continuam sujeitas a limites, atraso, mudanças de contrato e disponibilidade externa;
- o funcionamento em ARM64 precisa ser validado no provedor gratuito escolhido;
- a avaliação de interação, inclusividade e acessibilidade precisa de participantes reais, não apenas inspeção de código.

## Critérios de conclusão da fase

- [x] versão vigente da ISO identificada e matriz de nove características criada;
- [x] riscos de indisponibilidade de dados de mercado reduzidos com cache e retry;
- [x] observabilidade de requisições adicionada sem expor dados sensíveis;
- [x] configurações documentadas e ajustáveis por ambiente;
- [x] testes automatizados executados após as alterações;
- [x] limitações e próximos critérios de aceite registrados.
