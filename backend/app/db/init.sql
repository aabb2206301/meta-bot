-- =============================================================================
-- Postgres init script — auto-loaded by the pgvector image on first start
-- when the data volume is empty. Enables the extensions this app needs.
--
-- If your data volume is already initialized (i.e. you've run this stack
-- before), this script won't re-run. Enable the extensions manually:
--   docker compose exec postgres psql -U postgres -d sales_agent \
--     -c "CREATE EXTENSION IF NOT EXISTS vector;"
--   docker compose exec postgres psql -U postgres -d sales_agent \
--     -c 'CREATE EXTENSION IF NOT EXISTS "uuid-ossp";'
-- =============================================================================

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
