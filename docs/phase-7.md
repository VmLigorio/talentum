# Fase 7 — Preparação para produção

## Entregas

- Compose de produção separado em `docker-compose.production.yml`;
- PostgreSQL e Redis sem portas públicas, acessíveis somente pela rede interna do Compose;
- API publicada apenas em `127.0.0.1`, atrás de proxy reverso;
- container da API com filesystem somente leitura, volume exclusivo para documentos, `tmpfs` para temporários,
  remoção de capabilities e `no-new-privileges`;
- credenciais, domínio, CORS e segredo JWT fornecidos por `.env.production`, fora do repositório;
- proxy Nginx de referência com redirecionamento HTTP para HTTPS, TLS 1.2/1.3, HSTS e limite de upload;
- backup PostgreSQL em formato customizado, com validação por `pg_restore --list`, checksum SHA-256 e retenção;
- restauração protegida por `CONFIRM_RESTORE=YES` para evitar execução acidental;
- script de pré-verificação que rejeita placeholders, valida o Compose e testa `/health/ready`;
- documentação operacional e critérios de validação.

## Preparação do ambiente

```bash
cp .env.production.example .env.production
# edite .env.production e substitua todos os valores de exemplo
chmod 600 .env.production
```

As senhas usadas dentro de `DATABASE_URL` e `REDIS_URL` precisam estar codificadas para URL quando contiverem
caracteres reservados, como `@`, `:`, `/` ou `#`. O mesmo valor da senha do PostgreSQL deve ser usado em
`POSTGRES_PASSWORD` e na URL do banco.

## Subida do ambiente

```bash
docker compose --env-file .env.production \
  -f docker-compose.production.yml up -d --build

./ops/production_preflight.sh
```

O serviço fica disponível localmente na porta definida por `API_BIND_PORT` (8100 por padrão). O acesso externo
deve acontecer pelo Nginx com certificado válido. Não publique diretamente as portas do banco, Redis ou API na
internet.

## Backup e restauração

Backup manual:

```bash
POSTGRES_PASSWORD='senha-do-banco' \
POSTGRES_USER='talentum_app' \
POSTGRES_DB='talentum' \
BACKUP_DIR='/var/backups/talentum' \
bash ops/backup_postgres.sh
```

O backup é criado com permissão restrita, validado antes de ser disponibilizado e acompanhado de um checksum.
Em produção, copie o dump e o checksum para armazenamento remoto criptografado e retenha pelo menos uma cópia
fora do servidor.

Restauração — somente após validar o arquivo e escolher uma janela de manutenção:

```bash
POSTGRES_PASSWORD='senha-do-banco' \
POSTGRES_USER='talentum_app' \
POSTGRES_DB='talentum' \
CONFIRM_RESTORE=YES \
bash ops/restore_postgres.sh /var/backups/talentum/talentum-talentum-AAAAMMDDTHHMMSSZ.dump
```

Depois da restauração, execute o health check e valide login, leitura de carteira, alertas e documentos em uma
conta de teste antes de reabrir o acesso aos usuários.

## Critérios de conclusão

- [x] configuração de produção separada da configuração local;
- [x] segredos e domínios reais exigidos fora do código;
- [x] API, banco e serviços auxiliares com health checks;
- [x] HTTPS preparado no proxy reverso;
- [x] backup validado e restauração explicitamente protegida;
- [x] checklist de pré-deploy automatizado;
- [x] testes automatizados e validações do ambiente local executados.

## Dependências externas

A ativação final de HTTPS, DNS, armazenamento remoto dos backups e envio de notificações depende do provedor
escolhido e das credenciais reais. Esses itens não podem ser concluídos localmente sem domínio, certificados e
contas de infraestrutura; os arquivos de produção já estão preparados para recebê-los.
