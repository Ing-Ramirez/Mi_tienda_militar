#!/bin/bash
# ============================================================
#  Franja Pixelada — Script de Respaldo de Base de Datos
#
#  Uso:
#    ./scripts/backup_db.sh              → respaldo manual
#    Configurar en crontab para automático:
#      0 2 * * * /ruta/scripts/backup_db.sh   # diario a las 2am
#      0 1 * * 0 /ruta/scripts/backup_db.sh   # semanal los domingos
# ============================================================
set -euo pipefail

# ── Variables de configuración ────────────────────────────
DB_NAME="${DB_NAME:-franja_pixelada_store}"
DB_USER="${DB_USER:-franja_pixelada_user}"
DB_HOST="${DB_HOST:-db}"
DB_PORT="${DB_PORT:-5432}"

BACKUP_DIR="${BACKUP_DIR:-/backups}"
RETENTION_DAYS="${RETENTION_DAYS:-30}"   # Días a conservar respaldos diarios
RETENTION_WEEKS="${RETENTION_WEEKS:-12}" # Semanas a conservar respaldos semanales

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
DAY_OF_WEEK=$(date +%u)  # 1=lunes … 7=domingo
BACKUP_FILE="${BACKUP_DIR}/franja_pixelada_${TIMESTAMP}.sql.gz"

# ── Crear directorio si no existe ─────────────────────────
mkdir -p "${BACKUP_DIR}"

echo "=============================================="
echo " Franja Pixelada — Respaldo de Base de Datos"
echo " Fecha: $(date '+%d/%m/%Y %H:%M:%S')"
echo "=============================================="
echo " Base de datos : ${DB_NAME}"
echo " Destino       : ${BACKUP_FILE}"

# ── Ejecutar respaldo ─────────────────────────────────────
PGPASSWORD="${DB_PASSWORD:-}" \
  pg_dump \
  -h "${DB_HOST}" \
  -p "${DB_PORT}" \
  -U "${DB_USER}" \
  -F p \
  --no-password \
  "${DB_NAME}" \
  | gzip > "${BACKUP_FILE}"

SIZE=$(du -sh "${BACKUP_FILE}" | cut -f1)
echo " Tamaño        : ${SIZE}"
echo " Estado        : OK"

# ── Limpiar respaldos antiguos ────────────────────────────
echo ""
echo "Limpiando respaldos con más de ${RETENTION_DAYS} días..."
find "${BACKUP_DIR}" -name "franja_pixelada_*.sql.gz" \
  -mtime "+${RETENTION_DAYS}" -delete
echo "Limpieza completada."

echo "=============================================="
echo " Respaldo finalizado correctamente."
echo "=============================================="
