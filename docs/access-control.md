# Controle de acesso

## Papéis

- `admin`: administra todos os clientes e suas permissões;
- `advisor`: acessa somente clientes vinculados ao seu `advisor_id`;
- `client`: acessa apenas os próprios dados.

## Permissões do cliente

As permissões são aplicadas na API, não apenas na interface:

- editar perfil;
- editar perfil financeiro;
- editar patrimônio;
- editar metas;
- enviar documentos.

Quando não existe uma configuração para o cliente, todas as permissões começam desativadas por segurança.

Alterações de permissões geram um registro em `audit_logs` com o usuário responsável, cliente, operação e campos alterados.

## Documentos

- clientes só podem enviar documentos quando `can_upload_documents` estiver habilitada;
- Advisors só acessam documentos de clientes vinculados;
- administradores acessam todos os documentos;
- downloads passam pela API autenticada e não expõem a pasta de armazenamento;
- uploads aceitam PDF, PNG, JPG e TXT, com limite de 10 MB;
- uploads e exclusões são registrados em `audit_logs`.

## Alertas

Alertas são vinculados ao usuário autenticado e ao cliente relacionado. O sistema deduplica eventos para não repetir o mesmo aviso e permite marcar notificações individualmente ou em lote como lidas.

## Carteira de investimentos

Clientes, Advisors vinculados e administradores podem consultar a carteira do cliente. A criação, edição e
remoção de posições usa a permissão `can_edit_patrimony` para clientes e o vínculo normal de acesso para
Advisors; administradores mantêm acesso global. Cada alteração gera auditoria em `audit_logs`.
