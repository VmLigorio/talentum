# Fase 9 — Matriz inicial de aceitação

Esta matriz define os fluxos a validar antes e durante o piloto. Casos marcados como **Pendente** ainda não foram executados. Não usar dados reais de clientes nesta etapa.

## Pré-requisitos de execução

- Ambiente de homologação com banco isolado e migrations aplicadas.
- Contas sintéticas: administrador, Advisor A, Advisor B, Cliente A atribuído ao Advisor A e Cliente B atribuído ao Advisor B.
- App Flutter executável e dispositivo Android físico disponível para os casos Mobile.
- API alcançável pelo dispositivo; usar endereço HTTPS no ambiente de homologação.
- Dados e arquivos fictícios, sem segredos ou informações pessoais reais.

## Casos de aceitação

| ID | Prioridade | Cenário | Resultado esperado | Status |
|---|---|---|---|---|
| INT-ADM-01 | P0 | Administrador cria um Advisor e um cliente, atribui o Advisor e o cliente consulta suas permissões iniciais. | Contas e vínculo são criados; edição de patrimônio começa desativada. | Aprovado no PostgreSQL de teste, conforme informado pelo usuário |
| INT-ACL-01 | P0 | Advisor lista clientes e tenta abrir o dashboard de cliente atribuído e não atribuído. | Só o cliente atribuído aparece e é acessível; o outro retorna `403`. | Aprovado no PostgreSQL de teste, conforme informado pelo usuário |
| INT-ACL-02 | P0 | Cliente consulta o próprio patrimônio, tenta ler dados de outro cliente e tenta gravar sem permissão. | Leitura própria funciona; acesso cruzado e gravação não autorizada retornam `403`. | Aprovado no PostgreSQL de teste, conforme informado pelo usuário |
| INT-PERM-01 | P0 | Administrador habilita edição patrimonial e o cliente cria um item. | Criação autorizada funciona e fica registrada na auditoria. | Aprovado no PostgreSQL de teste, conforme informado pelo usuário |
| INT-RPT-01 | P0 | Advisor publica um relatório e mantém outro em rascunho. | Cliente vê o publicado; o rascunho retorna `404`. | Aprovado no PostgreSQL de teste, conforme informado pelo usuário |
| INT-DOC-01 | P0 | Advisor envia PDF ao cliente atribuído; cliente lista e baixa; outro Advisor tenta listar. | Download retorna o conteúdo correto, acesso cruzado retorna `403` e upload gera auditoria. | Aprovado no PostgreSQL isolado em 2026-09-30 |
| INT-DOC-02 | P1 | Enviar arquivo com extensão incompatível, assinatura inválida ou tamanho acima do limite. | API rejeita com `415`/`413`, sem arquivo parcial ou registro no banco. | Aprovado no PostgreSQL isolado em 2026-09-30 |
| ADM-01 | P0 | Administrador cria Cliente A e os Advisors A/B. | Contas são criadas com papéis corretos; senha não aparece em logs ou respostas posteriores. | Aprovado no teste de integração PostgreSQL isolado em 2026-10-02; fluxo de criação validado, senha e hash ausentes da resposta. |
| ADM-02 | P0 | Administrador atribui Cliente A ao Advisor A e configura permissões de edição. | Vínculo e permissões persistem e aparecem no painel. | Parcial: atribuição e permissão inicial desativada aprovadas na integração PostgreSQL em 2026-10-02; conferência visual no painel pendente. |
| ACL-01 | P0 | Advisor A consulta Cliente A. | Operação permitida. | Aprovado no teste de integração PostgreSQL isolado em 2026-10-02. |
| ACL-02 | P0 | Advisor A tenta consultar, alterar dados ou baixar documento de Cliente B. | API nega acesso; nenhum dado de Cliente B é retornado. | Parcial: leitura do dashboard negada em 2026-10-02; tentativa de alteração e download cruzado ainda precisa ser coberta/validada. |
| ACL-03 | P0 | Cliente A tenta consultar dados de Cliente B. | API nega acesso, inclusive quando o ID do outro cliente é informado diretamente. | Aprovado para leitura de patrimônio no teste PostgreSQL isolado em 2026-10-02; outros recursos precisam de cobertura específica. |
| PERM-01 | P0 | Cliente A com permissões financeiras desativadas tenta criar ou alterar patrimônio e metas. | API retorna acesso negado e os dados permanecem inalterados. | Parcial: criação de patrimônio negada em 2026-10-02; alteração e metas ainda sem cobertura específica. |
| PERM-02 | P0 | Administrador habilita a permissão correspondente; Cliente A repete a operação. | Operação permitida somente para os campos autorizados; alteração gera auditoria. | Parcial: criação de patrimônio permitida e auditada em 2026-10-02; edição, metas e escopo de campos ainda precisam de cobertura específica. |
| RPT-01 | P0 | Advisor A cria um relatório em rascunho e outro publicado para Cliente A. | Cliente A vê somente o publicado; Advisor A pode consultar ambos. | Aprovado no teste de integração PostgreSQL isolado em 2026-10-02 para visibilidade do cliente; consulta de ambos pelo Advisor ainda requer validação. |
| DOC-01 | P0 | Advisor A envia um PDF válido para Cliente A; Cliente A lista e baixa o documento. | Arquivo é armazenado e baixado pela API autenticada; operação respeita vínculo e auditoria. | Aprovado no teste de integração PostgreSQL isolado em 2026-10-02. |
| DOC-02 | P1 | Enviar arquivo com extensão e MIME incompatíveis, assinatura inválida ou tamanho acima do limite. | API rejeita o arquivo e não deixa arquivo parcial ou registro órfão no banco. | Aprovado no teste de integração PostgreSQL isolado em 2026-10-02 para extensão, assinatura e limite de tamanho. |
| SUIT-01 | P0 | Cliente confirma dados financeiros atuais, envia o questionário, Advisor atribuído revisa e cliente solicita ajuste. | Snapshot desatualizado é recusado; recomendação persistida soma 100%; Advisor sem vínculo recebe `403`; revisão, resposta e auditoria são persistidas. | Aprovado no teste de integração PostgreSQL isolado em 2026-10-02. |
| AUTH-01 | P0 | Cliente A encerra sessão; depois tenta reutilizar a sessão revogada. | A sessão deixa de autorizar chamadas e tokens locais são removidos pelo app. | Pendente |
| MOB-01 | P0 | Instalar o app em Android físico, autenticar e acessar o painel pela API HTTPS. | Instalação, autenticação, navegação e chamadas de API funcionam no dispositivo. | Parcial em 2026-10-07: APK debug do commit `2d4831e` instalado em Android físico; o usuário confirmou acesso à API local por `http://192.168.10.16:8001/health`. Login e navegação autenticados ainda aguardam confirmação; HTTPS de homologação, identificador exclusivo e assinatura de release continuam pendentes. |
| MOB-02 | P0 | Acessar dados, entrar em modo offline, sair da conta e trocar para outro usuário. | Cache offline indica última sincronização e não fica acessível após logout/troca de conta. | Pendente: teste manual em Android físico ainda não executado nesta fase. |
| OPS-01 | P0 | Reiniciar API durante operação com rotinas automáticas ativas. | Comportamento de alertas, snapshots e lembretes é documentado e consistente após reinício. | Parcial: API voltou a `healthy` e `/health/ready` confirmou o banco após reinício. As três rotinas iniciam por processo; manter uma instância até haver coordenação distribuída. |
| OPS-02 | P0 | Restaurar backup de homologação e validar login, relatório, carteira e documento fictícios. | Dados são recuperados e fluxos essenciais passam após a restauração. | Aprovado em banco sintético isolado: backup com checksum, restauração validada e suíte PostgreSQL completa aprovada (71 testes). Armazenamento remoto e criptografado continua pendente. |

## Evidências a registrar

Para cada execução, registrar data, versão/commit, ambiente, resultado, observação e referência de log por `X-Request-ID` quando aplicável. Não incluir tokens, senhas, conteúdo de documentos ou dados de clientes nos registros.

## Resultado inicial da execução

- Checkout inspecionado: commit `243b445`.
- Ambiente virtual `backend/.venv` criado e dependências de `backend/requirements.txt` instaladas; o ambiente é ignorado pelo Git.
- Execução dos cinco testes iniciais em PostgreSQL: **aprovada**, conforme informado pelo usuário. Neste checkout, `TEST_DATABASE_URL` não está configurada; por isso não reproduzimos essa execução aqui.
- Em 2026-09-30, os nove cenários da suíte de autorização/documentos passaram em PostgreSQL temporário isolado.
- O backup customizado foi criado com checksum, restaurado no banco isolado e validado com a suíte completa de backend: **71 testes passaram**.
- A verificação encontrou e corrigiu a leitura de stdin em `ops/backup_postgres.sh`; sem a correção, `pg_restore --list` tratava `-` como nome de arquivo e abortava o backup.
- API, PostgreSQL, Redis e ClamAV estavam saudáveis; após reinício controlado, `/health/ready` voltou a responder com banco `ok`. Os logs confirmaram o startup. As rotinas periódicas são criadas por processo, então o piloto deve usar uma única instância.
- A CI precisa rodar no GitHub Actions após push/PR. A validação de retenção remota criptografada e a restauração do provedor de homologação continuam pendentes.
- `bash -n`, `compileall` e `git diff --check` passaram. A suíte automatizada não substitui o teste do APK em aparelho Android físico; esse teste ainda está pendente.

## Reteste deste checkout — 2026-10-02

- Branch `codex/prototipo-react-native`, commit-base `c3d56c3`, com alterações locais ainda não commitadas.
- O PostgreSQL 16 temporário e isolado foi iniciado na porta `55432`, sem volume persistente; as migrations foram aplicadas até `0019_suitability_finance`.
- `backend/.venv/bin/pytest -q` com `TEST_DATABASE_URL` apontando exclusivamente para esse banco: **73 passaram, 0 falharam, 0 foram pulados**. Isso inclui os testes PostgreSQL de autorização, suitability, relatórios e documentos.
- A suíte foi executada novamente após alinhar o esquema de autorização do OpenAPI com o token Bearer emitido pelo login JSON, além das verificações de criação administrativa e do fluxo integrado de suitability.
- O workflow `.github/workflows/security.yml` está configurado para iniciar PostgreSQL 16 isolado, aplicar `alembic upgrade head` e executar `pytest -q` em push e pull request. A execução desse workflow no GitHub ainda precisa ser observada após o push/PR.
- Os resultados de 2026-09-30 acima permanecem como evidência histórica daquela execução; o resultado atual é uma reprodução independente neste checkout.
- Permanecem pendentes a validação manual do painel/app e os subfluxos explicitados como parciais na matriz. Não usar dados reais de clientes nesta etapa.
