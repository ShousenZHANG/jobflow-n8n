#!/usr/bin/env bash
set -euo pipefail

echo "[init-data] provisioning non-root Postgres user..."

if [[ -n "${POSTGRES_NON_ROOT_USER:-}" && -n "${POSTGRES_NON_ROOT_PASSWORD:-}" ]]; then
psql -v ON_ERROR_STOP=1 --username "${POSTGRES_USER}" --dbname "${POSTGRES_DB}" <<-EOSQL
  DO
  \$do\$
  BEGIN
    IF NOT EXISTS (
      SELECT FROM pg_roles WHERE rolname = '${POSTGRES_NON_ROOT_USER}'
    ) THEN
      CREATE ROLE ${POSTGRES_NON_ROOT_USER} LOGIN PASSWORD '${POSTGRES_NON_ROOT_PASSWORD}';
    END IF;
  END
  \$do\$;

  GRANT ALL PRIVILEGES ON DATABASE ${POSTGRES_DB} TO ${POSTGRES_NON_ROOT_USER};
  ALTER DATABASE ${POSTGRES_DB} OWNER TO ${POSTGRES_NON_ROOT_USER};
  GRANT CREATE ON SCHEMA public TO ${POSTGRES_NON_ROOT_USER};
EOSQL
else
  echo "[init-data] POSTGRES_NON_ROOT_USER/POSTGRES_NON_ROOT_PASSWORD not provided. Skipping."
fi
