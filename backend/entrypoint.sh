#!/bin/sh
# ──────────────────────────────────────────────────
#  Franja Pixelada — Script de arranque del backend
# ──────────────────────────────────────────────────
set -e

# Si arrancamos como root (UID 0), fijar permisos en los volúmenes montados
# y re-lanzar este mismo script como usuario "django" usando gosu.
# Esto resuelve que los volúmenes Docker se monten con ownership root
# después de que el Dockerfile ejecutó su chown.
if [ "$(id -u)" = "0" ]; then
  mkdir -p /app/media /app/staticfiles /app/logs
  chown -R django:django /app/media /app/staticfiles /app/logs
  chmod -R 755 /app/media /app/staticfiles /app/logs
  exec gosu django "$0" "$@"
fi

echo "==> Esperando PostgreSQL..."
python manage.py wait_for_db

echo "==> Ejecutando migraciones..."
python manage.py migrate --noinput

echo "==> Verificando tablas..."
python manage.py check_db

# DEBUG=True: no llenar STATIC_ROOT; WhiteNoise usa finders + archivos en backend/static/.
# Si quedan copias viejas en el volumen, WhiteNoise las serviría antes que el código fuente.
if [ "${DEBUG:-False}" = "True" ] || [ "${DEBUG:-False}" = "true" ]; then
  echo "==> DEBUG: limpiando staticfiles (si existe) — estáticos vía WhiteNoise/finders en /static/."
  if [ -d /app/staticfiles ]; then
    find /app/staticfiles -mindepth 1 -delete 2>/dev/null || true
  fi
elif [ "${SKIP_COLLECTSTATIC_ON_START}" = "true" ] || [ "${SKIP_COLLECTSTATIC_ON_START}" = "True" ]; then
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
