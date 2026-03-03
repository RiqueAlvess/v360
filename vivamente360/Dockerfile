FROM python:3.11-slim

WORKDIR /app

# Instalar dependências do sistema
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Instalar Poetry
RUN pip install --no-cache-dir poetry==1.8.3

# Copiar arquivos de dependências
COPY pyproject.toml poetry.lock* ./

# Instalar dependências (sem virtualenv — container já é isolado)
RUN poetry config virtualenvs.create false && \
    poetry install --no-interaction --no-ansi --without dev

# Copiar código fonte
COPY src/ ./src/
COPY alembic/ ./alembic/
COPY alembic.ini* ./

EXPOSE 8000

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
