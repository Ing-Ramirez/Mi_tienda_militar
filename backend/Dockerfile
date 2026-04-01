FROM python:3.12-slim

# Variables de entorno
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Dependencias del sistema
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Instalar dependencias Python
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copiar código fuente
COPY . .

# Crear usuario antes de crear directorios para que sean suyos desde el inicio
RUN addgroup --system django && adduser --system --ingroup django django

# Crear directorios y dar permisos al entrypoint ya como root, luego ceder todo
RUN mkdir -p logs media staticfiles \
    && chmod +x entrypoint.sh \
    && chown -R django:django /app

USER django

EXPOSE 8000

# Una sola fuente de verdad: migrate, collectstatic (según env) y Gunicorn vía entrypoint.sh
CMD ["sh", "/app/entrypoint.sh"]
