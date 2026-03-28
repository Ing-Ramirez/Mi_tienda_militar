-- ============================================================
--  Franja Pixelada — Inicialización de Base de Datos
--  Este script se ejecuta automáticamente la primera vez que
--  el contenedor de PostgreSQL arranca (docker-entrypoint-initdb.d)
-- ============================================================

-- Habilitar extensión UUID (necesaria para los campos UUIDField de Django)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Habilitar extensión pg_trgm (búsqueda de texto con trigrams)
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Configurar zona horaria de la base de datos
SET timezone = 'America/Bogota';

-- ── Verificar y crear la base de datos principal ─────────────────────────
-- Nota: Docker Postgres crea automáticamente la DB definida en POSTGRES_DB.
-- Este bloque solo aplica si se necesita crear DBs adicionales.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT FROM pg_database WHERE datname = 'franja_pixelada_store'
    ) THEN
        PERFORM dblink_exec(
            'dbname=postgres',
            'CREATE DATABASE franja_pixelada_store
             WITH ENCODING=''UTF8''
             LC_COLLATE=''es_CO.UTF-8''
             LC_CTYPE=''es_CO.UTF-8''
             TEMPLATE=template0'
        );
        RAISE NOTICE 'Base de datos franja_pixelada_store creada.';
    ELSE
        RAISE NOTICE 'Base de datos franja_pixelada_store ya existe.';
    END IF;
END $$;

-- ── Configuración de búsqueda de texto en español ────────────────────────
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT FROM pg_ts_config WHERE cfgname = 'spanish'
    ) THEN
        -- La configuración 'spanish' viene incluida en PostgreSQL
        RAISE NOTICE 'Configuracion de texto spanish disponible.';
    END IF;
END $$;

-- ── Mensaje de confirmación ───────────────────────────────────────────────
DO $$
BEGIN
    RAISE NOTICE '=====================================================';
    RAISE NOTICE '  Franja Pixelada Store — Base de datos inicializada';
    RAISE NOTICE '  Las tablas seran creadas por Django (migrate)';
    RAISE NOTICE '=====================================================';
END $$;
