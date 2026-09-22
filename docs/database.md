# Banco de dados

O Talentum usa PostgreSQL como banco principal e SQLAlchemy 2 como camada de persistência. O Alembic mantém as alterações de esquema versionadas.

## Desenvolvimento local

```bash
docker compose up -d postgres
cd backend
cp .env.example .env
alembic upgrade head
```

As migrations criam as tabelas `users`, `sessions`, `client_profiles`, `client_permissions`, `audit_logs`, `financial_profiles`, `patrimony_items`, `goals`, `reports`, `action_items`, `documents` e `notifications`.

As credenciais presentes no `docker-compose.yml` são somente para desenvolvimento local. Nunca reutilize essas credenciais em staging ou produção.
