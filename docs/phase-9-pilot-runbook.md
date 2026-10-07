# Fase 9 — Roteiro do piloto assistido

Este roteiro prepara o acompanhamento do piloto Talentum. Ele não autoriza o uso de dados reais nem substitui revisão jurídica, de privacidade ou de suitability. Enquanto as condições de entrada abaixo estiverem abertas, use somente contas, valores e documentos fictícios.

## Estado atual

- Roteiro, formulário de feedback, registro de incidentes e modelo de relatório preparados.
- Testes automatizados do backend e restauração local em banco sintético aprovados; consulte a [matriz de aceitação](phase-9-acceptance-matrix.md).
- O piloto externo ainda não está liberado: faltam ambiente de homologação HTTPS, identificador e assinatura Android próprios, revisão dos textos de privacidade/consentimento, definição do suporte, limites de mercado permitidos e critérios numéricos de sucesso.
- A operação do piloto deve manter uma única instância da API até que as rotinas periódicas tenham coordenação distribuída.

## Condições de entrada

Preencha e aprove cada item antes de convidar participantes:

| Decisão ou controle | Preencher/confirmar |
|---|---|
| Responsável pelo piloto | `PENDENTE` |
| Participantes e papéis | `PENDENTE` |
| Data de início e duração | `PENDENTE` |
| Plataforma inicial (Android, web ou ambas) | `PENDENTE` |
| Ambiente isolado, domínio e URL HTTPS | `PENDENTE` |
| Canal de distribuição e versão do app | `PENDENTE` |
| Canal de suporte e horário de atendimento | `PENDENTE` |
| Texto aprovado de privacidade, consentimento e retirada | `PENDENTE` |
| Métricas, linha de base e limites de aprovação/interrupção | `PENDENTE` |
| Permissão de uso e atraso das fontes de cotação | `PENDENTE` |
| Backup remoto criptografado e restauração testada | `PENDENTE` |

Não iniciar onboarding externo enquanto houver `PENDENTE` em ambiente/HTTPS, suporte, consentimento, critérios de parada ou licença/limites das fontes de mercado.

## Onboarding acompanhado

1. Confirmar que a pessoa recebeu a versão correta e o aviso de que participa de um piloto.
2. Explicar o objetivo, o que será observado, o canal de suporte, como retirar a participação e quais dados serão registrados.
3. Usar uma conta de teste individual. Não compartilhar senha, token ou conta entre participantes.
4. Conferir que a conta mostra apenas o cliente e as permissões esperadas.
5. Acompanhar login, tela inicial, navegação e saída da conta.
6. Para testar suitability, usar respostas e situação financeira fictícias. Verificar que a avaliação aguarda revisão do Advisor, que a resposta do cliente fica registrada e que o app não envia ordens.
7. Testar relatório e documentos apenas com conteúdo fictício. Conferir download e acesso entre contas de teste.
8. Testar modo offline, logout e troca de conta. Confirmar que o cache anterior deixa de aparecer.
9. Registrar apenas conclusão da tarefa, duração aproximada e problemas técnicos sem identificar a pessoa.

## Registro de incidente

Abra um registro para cada falha. Não inclua nome, e-mail, CPF, saldo real, senha, token, documento, captura sem tarja ou conteúdo de recomendação individual.

```text
ID do incidente:
Data/hora aproximada e fuso:
Versão do app / ambiente:
Papel de teste (cliente, Advisor ou admin):
Tela ou fluxo:
Gravidade (P0, P1, P2 ou P3):
Passos para reproduzir usando conta fictícia:
Resultado esperado:
Resultado observado:
Frequência (sempre, às vezes, uma vez):
X-Request-ID (se houver):
Evidência sanitizada:
Responsável e estado:
```

### Gravidade

- **P0 — interromper o piloto:** acesso a dados de outra conta, exposição de segredo, corrupção/perda de dados ou comportamento que possa induzir uma ação financeira indevida.
- **P1 — pausar o fluxo afetado:** login, permissões, suitability, relatórios ou documentos não funcionam sem alternativa segura.
- **P2 — corrigir com prioridade:** falha com alternativa segura e sem exposição ou alteração incorreta de dados.
- **P3 — melhoria:** problema visual, texto confuso ou sugestão que não bloqueia as tarefas essenciais.

P0 exige suspensão imediata do fluxo, preservação de evidências sanitizadas e avaliação do responsável antes de qualquer retomada. Não corrigir dados manualmente sem registrar a operação.

## Feedback do participante

Coletar uma resposta por tarefa, sem pedir informação financeira pessoal:

```text
Tarefa testada:
Conseguiu concluir? (sim / parcialmente / não)
Quão fácil foi? (1 a 5)
O que ficou confuso ou demorou?
O que ajudaria a concluir a tarefa?
Encontrou algo que não esperava? (descrever sem dados pessoais)
Autoriza contato de acompanhamento pelo canal combinado? (sim / não)
```

Não coletar opiniões sobre ativos específicos, patrimônio real ou tolerância pessoal a perdas neste formulário de usabilidade. Esses dados pertencem ao fluxo protegido de suitability, com consentimento e revisão apropriados.

## Métricas e decisão

Defina a linha de base e o limite de aceite **antes** de começar; não escolha metas depois de ver os resultados.

| Indicador | Como contar | Linha de base / limite aprovado |
|---|---|---|
| Conclusão de tarefa | tarefas concluídas ÷ tarefas iniciadas | `PENDENTE` |
| Erros de fluxo | falhas reproduzíveis por tarefa | `PENDENTE` |
| Tempo por tarefa | duração aproximada, sem identificar participante | `PENDENTE` |
| Disponibilidade da API | health checks bem-sucedidos ÷ total de verificações | `PENDENTE` |
| Incidentes P0/P1 | contagem por gravidade | `PENDENTE` |
| Clareza de suitability | conclusão e perguntas de compreensão | `PENDENTE` |
| Indisponibilidade/atraso de cotações | ocorrências observadas e fonte | `PENDENTE` |

Qualquer P0 interrompe o piloto. Os demais limites devem ser definidos pelo responsável antes do onboarding. Ao encerrar, classifique cada item como corrigir antes de ampliar, aceitar com justificativa ou acompanhar na próxima fase.

## Relatório de encerramento

```text
Período e versão avaliada:
Ambiente e plataformas:
Número de participantes por papel (agregado):
Tarefas avaliadas e taxa de conclusão:
Incidentes por gravidade e situação:
Problemas de acesso, sessão ou cache:
Resultados do fluxo de suitability:
Limitações observadas em cotações/documentos:
Feedback agregado e sem identificação:
Backlog ordenado por impacto e risco:
Decisão: corrigir / continuar limitado / ampliar após nova aprovação:
Responsável e data:
```

Guarde o relatório e os registros em local com acesso restrito. Remova contas, documentos e dados sintéticos temporários ao concluir os testes, conforme o procedimento do ambiente.
