# Fase 6 — Produção e auditoria de segurança

## Correções implementadas

- rate limit de login por origem e e-mail, com resposta `429` e `Retry-After`;
- validação obrigatória de configurações sensíveis quando `ENVIRONMENT=production`;
- correção do nome da variável do segredo JWT no Docker Compose (`JWT_SECRET`);
- bloqueio de banco de dados com credenciais de desenvolvimento em produção;
- possibilidade de desligar Swagger, ReDoc e OpenAPI com `API_DOCS_ENABLED=false`;
- lista de hosts confiáveis configurável por `TRUSTED_HOSTS`;
- cabeçalhos `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, `Permissions-Policy` e `Cross-Origin-Resource-Policy`;
- HSTS ativado no modo de produção;
- limite global de corpo de requisição para reduzir abuso de payload;
- upload de documentos com extensão compatível com MIME, assinatura binária e validação UTF-8 para TXT;
- nome original de arquivo sanitizado contra quebra de cabeçalho, traversal e caracteres de controle;
- tokens exigindo `sub`, `type`, `iat`, `exp` e `jti`;
- aplicativo Mobile usando `flutter_secure_storage` para tokens e cache financeiro, sem persistência sensível em `SharedPreferences`;
- testes automatizados específicos da fase 6.

## Medidas de produção configuradas

- Redis opcional para compartilhar o rate limit entre múltiplos workers, com `REDIS_REQUIRED=true` para falhar fechado;
- ClamAV opcional para verificar arquivos antes de gravá-los, com `CLAMAV_REQUIRED=true` para bloquear quando o scanner estiver indisponível;
- serviços Redis e ClamAV adicionados ao `docker-compose.yml`, com volumes persistentes;
- script `bash ops/backup_postgres.sh` para backup customizado do PostgreSQL e retenção configurável;
- proxy HTTPS de referência em [deploy/nginx/talentum-api.conf.example](/home/vitor-ligorio/talentum/deploy/nginx/talentum-api.conf.example);
- workflow de CI em [.github/workflows/security.yml](/home/vitor-ligorio/talentum/.github/workflows/security.yml), executando testes, compilação, Bandit e pip-audit.

## Auditoria realizada

### Autenticação e sessão

O fluxo usa Argon2 para senhas, access token curto, refresh token rotativo armazenado apenas como hash,
revogação por sessão e invalidação global por `session_version`. O login mantém resposta genérica para
credenciais inválidas e agora possui proteção contra tentativas repetidas.

### Autorização

As rotas de cliente exigem vínculo do Advisor ou papel de administrador. Alterações de patrimônio, perfil,
metas, documentos e permissões passam por permissões explícitas e registram auditoria. Não foi encontrado
acesso direto por `client_id` sem uma verificação correspondente nas rotas revisadas.

### Dados e arquivos

Os documentos ficam fora do banco, com nome interno aleatório, caminho resolvido dentro do diretório de storage,
limite de 10 MB, MIME permitido e validação básica de assinatura. A origem do nome apresentado ao usuário agora
é sanitizada. Em produção, recomenda-se acrescentar antivírus e armazenamento privado com URLs temporárias.

No Mobile, o refresh token, o access token e o cache financeiro usam o armazenamento seguro da plataforma. O Android
foi elevado para API mínima 23, requisito do plugin de armazenamento seguro adotado.

### API e transporte

CORS continua restrito às origens configuradas. O modo de produção rejeita origens HTTP, exige segredo JWT forte,
credenciais de banco não desenvolvimentais e hosts confiáveis. TLS deve ser terminado no proxy reverso ou balanceador
de produção; o Uvicorn local não substitui HTTPS.

### Dependências e operação

As dependências estão fixadas no ambiente virtual utilizado para os testes, e a aplicação passa por compilação,
testes e verificação de sintaxe. O Bandit foi executado sem achados após a revisão dos falsos positivos de claims JWT,
e o `pip-audit` não encontrou vulnerabilidades conhecidas nas dependências declaradas.

## Configuração antes do deploy

- preencher os valores reais de `.env.production.example` usando o gerenciador de segredos do provedor;
- instalar os certificados no proxy e trocar o domínio de exemplo;
- agendar o `ops/backup_postgres.sh` e testar restauração em uma base isolada;
- configurar armazenamento remoto e criptografado para os backups;
- revisar limites, alertas e retenção do Redis/ClamAV;
- configurar provedor de e-mail/push e observabilidade centralizada.
