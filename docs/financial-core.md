# Núcleo financeiro do MVP

O núcleo financeiro começa com três recursos simples e auditáveis:

- `financial_profiles`: renda, despesas e perfil de risco declarados;
- `patrimony_items`: categoria, descrição, instituição, valor e observações;
- `goals`: título, valor-alvo, valor atual, prazo e status.

As informações são sempre vinculadas a um cliente. Administradores e consultores acessam os clientes autorizados; clientes acessam somente os próprios dados. Operações de escrita do cliente dependem de `client_permissions`.

O modelo não executa ordens, movimenta dinheiro nem promete rentabilidade. Essas capacidades permanecem fora do MVP e dependem de validação regulatória antes de qualquer implementação.

O dashboard é calculado a partir desses dados, sem duplicar totais em tabelas: apresenta patrimônio total, distribuição por categoria, progresso das metas e resumo de renda/despesas.

Relatórios começam como registros textuais manuais. O Advisor pode mantê-los em rascunho ou publicá-los; o cliente só recebe relatórios publicados.

O aplicativo Mobile já possui a primeira navegação consumindo esses endpoints: Início, Patrimônio, Metas, Relatórios e Perfil. O endereço da API pode ser definido com `--dart-define=API_URL=...`.
