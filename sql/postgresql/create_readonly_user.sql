-- MR. HEALTH - Read-only user for Cloud Function extraction
-- Run as superuser (mrhealth_admin) after tables are created

DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'mrh_extractor') THEN
        CREATE ROLE mrh_extractor WITH LOGIN PASSWORD 'CHANGE_ME_extractor_readonly_2026';
    END IF;
END
$$;

GRANT CONNECT ON DATABASE mrhealth TO mrh_extractor;
GRANT USAGE ON SCHEMA public TO mrh_extractor;
GRANT SELECT ON produto, unidade, estado, pais TO mrh_extractor;

ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO mrh_extractor;
