# Talentum — backend/Dockerfile
# Responsabilidade: define a imagem de execução da API dentro do Docker.
FROM python:3.12-slim

# Evita arquivos .pyc e envia logs imediatamente para o coletor do container.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Instala dependências antes de copiar a aplicação para aproveitar cache de camadas.
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

# Inclui o código da API e as revisões necessárias ao comando de migração.
COPY backend/app /app/backend/app
COPY backend/alembic /app/backend/alembic
COPY backend/alembic.ini /app/backend/alembic.ini

# Executa migrações e servidor a partir da raiz do pacote backend.
WORKDIR /app/backend

# Atualiza o esquema e inicia a API no endereço interno do container.
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
