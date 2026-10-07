# Fase 9 — Decisão de avanço

**Data:** 2026-09-30  
**Base:** evidências da [matriz de aceitação](phase-9-acceptance-matrix.md), do [plano da fase 9](phase-9-plan.md) e do [roteiro do piloto](phase-9-pilot-runbook.md).

## Decisão

**GO limitado para ensaios internos com dados inteiramente fictícios. NO-GO para convidar clientes ou usar dados financeiros reais.**

O backend demonstrou uma base útil: 71 testes passaram com PostgreSQL, o backup foi restaurado em banco temporário isolado e a API recuperou o estado saudável após reinício. Isso permite continuar validações controladas por equipe interna.

O uso externo ainda não atende aos critérios P0 de distribuição segura, privacidade, operação e suporte. A decisão deve ser reavaliada depois que os bloqueios abaixo forem encerrados e registrados.

## Evidências contra os critérios

| Critério | Evidência atual | Avaliação |
|---|---|---|
| Autorização e fluxos essenciais no backend | 71 testes passaram; nove cenários de autorização/documentos passaram com PostgreSQL isolado | Atendido para backend automatizado; cenários manuais de aceitação ainda pendentes |
| Distribuição Android via HTTPS | O projeto ainda usa identificador `com.example.talentum_mobile` e assinatura de debug; API pública HTTPS de homologação não foi validada | Não atendido |
| Operação após reinício e rotinas | API retomou `healthy`; os monitores iniciam por processo e a implantação requer uma instância | Parcial; restrição documentada, mas execução dos monitores precisa ser observada em homologação |
| Backup e restauração | Dump com checksum restaurado em banco sintético; suíte completa passou após a restauração | Atendido localmente; backup remoto criptografado e restauração do provedor pendentes |
| Privacidade, consentimento e uso de cotações | Textos, canal de suporte e limites/licenças de provedores ainda não aprovados | Não atendido |
| Plano do piloto | Roteiro disponível; público, duração, plataforma, responsável e métricas ainda sem definição | Não atendido |

## Backlog de saída, em ordem

1. **Preparar homologação isolada:** selecionar hospedagem, domínio HTTPS, banco e armazenamento privado; configurar segredos fora do Git; limitar a API a uma instância; configurar backup remoto criptografado e executar restauração nesse ambiente.
2. **Preparar o Android de piloto:** definir identificador exclusivo, assinatura de release protegida, versão e URL HTTPS. Instalar em aparelho físico e completar MOB-01/MOB-02.
3. **Fechar controles de uso:** aprovar textos de privacidade, consentimento e suporte; confirmar permissão, atraso e limitações dos provedores de cotações; definir como retirar participantes e excluir seus dados.
4. **Executar regressões manuais P0:** onboarding Admin/Advisor/cliente, isolamento entre clientes, permissões, relatório publicado/rascunho, upload/download, sessão revogada e cache após logout/troca de conta.
5. **Aprovar o protocolo do piloto:** nomear responsável e suporte; definir quantidade de participantes, duração, plataforma, métricas e limites de aprovação/interrupção antes de qualquer convite.
6. **Revalidar jobs e CI:** observar alertas, snapshots e lembretes em homologação após reinício; confirmar que apenas uma instância opera; executar o workflow no GitHub Actions após push/PR.

## Condição para reabrir a decisão

Mudar para **GO limitado com participantes** somente quando todos os itens P0 acima tiverem evidência anexada, as condições de entrada do roteiro estiverem preenchidas e os responsáveis aprovarem o início. A ampliação além do grupo inicial exige nova decisão baseada nos resultados e nos limites definidos previamente.
