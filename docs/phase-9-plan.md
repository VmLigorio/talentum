# Talentum — Plano da Fase 9: piloto assistido

## Objetivo

Preparar e validar o MVP atual em um piloto limitado de consultoria, cobrindo o atendimento do cliente no painel Advisor e no aplicativo Mobile. A fase prioriza evidências de uso real, estabilidade operacional e prontidão do Android para distribuição.

Este documento é um plano de trabalho; os itens abaixo ainda não são entregas concluídas.

## Andamento

- Matriz inicial de aceitação criada em `docs/phase-9-acceptance-matrix.md`.
- Cinco testes HTTP de autorização e onboarding foram aprovados no PostgreSQL de teste, conforme execução confirmada por Vitor.
- A CI foi preparada com PostgreSQL temporário e migrations; as alterações ainda precisam chegar ao GitHub para validar o fluxo nela.
- Próximo lote P0: executar os testes manuais do Android físico e validar o workflow de CI após push/PR. Os testes de integração de documentos já passaram em PostgreSQL isolado.
- Etapa 4 verificada localmente: health check, reinício da API, backup com checksum, restauração em banco isolado e suíte completa (71 testes) passaram. A validação em produção e o armazenamento remoto criptografado ainda dependem do provedor.
- Etapa 5 iniciada com roteiro de onboarding, gravidade de incidentes, feedback sem dados sensíveis e modelo de relatório em `docs/phase-9-pilot-runbook.md`. O piloto externo permanece aguardando o preenchimento e aprovação das condições de entrada.
- Etapa 6 decidida em `docs/phase-9-decision.md`: GO limitado somente para ensaios internos com dados fictícios; NO-GO para participantes externos ou dados financeiros reais até fechar todos os bloqueios P0.

## Contexto observado no repositório

- O MVP já contempla contas de cliente, Advisor e administrador, permissões, patrimônio, metas, carteira, plano de ação, relatórios, documentos e notificações dentro do sistema.
- O app Android ainda usa `com.example.talentum_mobile` como `applicationId` e assinatura de debug.
- Alertas, snapshots e lembretes são iniciados junto com o processo da API. A implantação atual deve evitar múltiplas instâncias da API executando essas rotinas simultaneamente.
- Operação do piloto: manter exatamente uma instância da API enquanto as rotinas periódicas forem iniciadas no ciclo de vida de cada processo. Não escalar horizontalmente até implementar e testar um worker dedicado ou exclusão mútua distribuída.
- A Fase 8 recomenda validação com usuários, medição de desempenho e testes de restauração como próximos critérios.
- Fontes de mercado e canais de notificação externos dependem de fornecedores e configurações que ainda precisam ser validados para operação comercial.

## Escopo proposto

### Incluído

1. **Validação dos fluxos essenciais**
   - Administrador cria cliente e Advisor, vincula o responsável e define permissões.
   - Cliente entra no app, consulta os dados autorizados e tenta uma ação bloqueada quando está em modo somente leitura.
   - Advisor registra patrimônio e metas, cria ações e publica um relatório.
   - Cliente visualiza o relatório publicado e não acessa rascunhos nem dados de outro cliente.
   - Cliente e Advisor recebem e conseguem tratar alertas dentro do sistema.
   - Upload, download e exclusão de documentos respeitam as permissões configuradas.

2. **Preparação do Android para piloto**
   - Definir identificador exclusivo, nome, ícone e versão do aplicativo.
   - Configurar assinatura de release sem incluir chaves privadas no Git.
   - Definir como `API_URL` será configurada no pacote e exigir HTTPS fora do ambiente local.
   - Instalar e verificar o pacote em dispositivo Android físico, incluindo login, sessão, cache offline, upload e download de documento.

3. **Operação controlada do piloto**
   - Preparar um ambiente de homologação separado do desenvolvimento e dos dados reais de produção.
   - Escrever um roteiro de onboarding, suporte, registro de problemas e coleta de feedback.
   - Definir métricas e limites de aceite antes de convidar os participantes; não fixar metas numéricas sem uma linha de base.
   - Executar e registrar um teste de backup e restauração antes de usar dados reais.
   - Definir o modo de execução das rotinas automáticas. Para uma única instância, documentar a restrição; antes de escalar, impedir execução duplicada com um worker ou mecanismo de exclusão mútua testado.

4. **Revisão de uso e dados**
   - Revisar textos de privacidade, consentimento, suporte e limites dos dados de mercado antes do piloto.
   - Confirmar que os provedores de cotação permitem o uso pretendido e documentar atrasos, indisponibilidade e limitações.

### Fora do escopo desta fase

- Open Finance ou importação automática de corretoras.
- Execução de ordens, custódia ou gestão discricionária.
- Recomendações de investimento automatizadas por IA.
- Pagamentos, cobrança recorrente e integração com WhatsApp.
- Novos módulos de CRM ou agenda completos; registrar notas de reunião como melhoria futura se o piloto demonstrar essa necessidade.

## Etapas de trabalho

| Etapa | Trabalho | Saída |
|---|---|---|
| 1. Congelar o escopo do piloto | Confirmar papéis, permissões, dados de teste, dispositivo-alvo e critérios de sucesso. | Roteiro e critérios aprovados antes do piloto. |
| 2. Validar regressões | Automatizar ou executar os fluxos essenciais por papel; corrigir falhas de autorização, sessão, upload e visibilidade de relatórios. | Evidência de aprovação dos fluxos e regressões cobertas. |
| 3. Preparar app e homologação | Configurar pacote Android, assinatura, endpoint HTTPS e ambiente de teste. | APK/AAB de release instalável em dispositivo físico. |
| 4. Verificar operação | Testar health checks, logs, rotinas automáticas, backup e restauração; definir a restrição de instância única ou implementar coordenação de tarefas. | Procedimento operacional documentado e resultado dos testes. |
| 5. Rodar piloto assistido | Acompanhar onboarding e uso, registrar problemas e feedback sem usar credenciais ou dados em tickets/logs. | Roteiro preparado; execução com participantes aguarda ambiente de homologação, condições de entrada e responsáveis definidos. |
| 6. Decidir próxima fase | Comparar evidências com critérios definidos e selecionar melhorias necessárias. | Concluída: ensaio interno sintético autorizado; uso externo limitado até fechar os itens P0 da decisão registrada. |

## Critérios de aceite propostos

- Os fluxos essenciais passam para os papéis cliente, Advisor e administrador, incluindo tentativas de acesso não autorizado.
- Permissões somente de visualização são aplicadas pela API; ocultar controles na interface não conta como proteção suficiente.
- O pacote Android de release usa identificador próprio e assinatura de produção, e funciona em aparelho físico com API HTTPS.
- O cache financeiro deixa de estar acessível após logout, troca de conta e expiração de sessão.
- Um backup de homologação pode ser restaurado e os fluxos básicos são conferidos após a restauração.
- As rotinas automáticas têm comportamento definido após reinício e não rodam duplicadas no modo de implantação aprovado.
- O piloto começa somente depois de critérios, responsáveis por suporte, consentimento e limitações de dados estarem documentados.
- Feedback e incidentes do piloto são registrados sem expor senhas, tokens ou documentos pessoais.

## Riscos e dependências

- **Fontes de cotação:** limites, atraso, mudanças de API e licença comercial podem afetar recursos de carteira e alertas.
- **Rotinas no processo da API:** reinícios interrompem a rotina durante a pausa; múltiplas instâncias podem repetir consultas e capturas.
- **Distribuição Android:** assinatura e identificador precisam ser definidos antes de distribuir versões externas.
- **Dados pessoais e financeiros:** ambiente, suporte e backups exigem acesso restrito e procedimentos para incidentes.
- **Notificações externas:** push/e-mail ficam para outra etapa, salvo se o piloto mostrar que alertas internos não bastam e houver fornecedor definido.

## Decisões pendentes para fechar antes da execução

- Quantos clientes participarão e por quanto tempo durará o piloto.
- Se o primeiro piloto será somente Android ou também terá acesso web/mobile web.
- Quem prestará suporte e qual será o canal de contato.
- Qual provedor de hospedagem, domínio, HTTPS e armazenamento de backup será usado.
- Se as rotinas podem permanecer em uma única API durante o piloto ou se será criado um worker dedicado.
- Quais métricas e limites numéricos determinarão aprovação do piloto.

## Próxima tarefa recomendada

Executar o backlog P0 em [phase-9-decision.md](phase-9-decision.md), começando por homologação HTTPS isolada e preparação do Android de piloto. Não convidar participantes até uma nova decisão.
