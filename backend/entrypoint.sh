#!/bin/sh
# ──────────────────────────────────────────────────
#  Franja Pixelada — Script de arranque del backend
# ──────────────────────────────────────────────────
set -e

echo "==> Esperando PostgreSQL..."
python manage.py wait_for_db

echo "==> Ejecutando migraciones..."
python manage.py migrate --noinput

echo "==> Verificando tablas..."
python manage.py check_db

if [ "${SKIP_COLLECTSTATIC_ON_START}" = "true" ] || [ "${SKIP_COLLECTSTATIC_ON_START}" = "True" ]; then
  echo "==> Omitiendo collectstatic (SKIP_COLLECTSTATIC_ON_START=true)."
else
  echo "==> Recopilando archivos estáticos..."
  python manage.py collectstatic --noinput
fi

GUNICORN_WORKERS="${GUNICORN_WORKERS:-3}"
GUNICORN_THREADS="${GUNICORN_THREADS:-2}"
GUNICORN_TIMEOUT="${GUNICORN_TIMEOUT:-120}"

echo "==> Iniciando Gunicorn (workers=${GUNICORN_WORKERS}, threads=${GUNICORN_THREADS})..."
if [ "$GUNICORN_THREADS" -gt 0 ] 2>/dev/null; then
  exec gunicorn franja_pixelada.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers "$GUNICORN_WORKERS" \
    --worker-class gthread \
    --threads "$GUNICORN_THREADS" \
    --timeout "$GUNICORN_TIMEOUT" \
    --access-logfile - \
    --error-logfile -
else
  exec gunicorn franja_pixelada.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers "$GUNICORN_WORKERS" \
    --timeout "$GUNICORN_TIMEOUT" \
    --access-logfile - \
    --error-logfile -
fi
