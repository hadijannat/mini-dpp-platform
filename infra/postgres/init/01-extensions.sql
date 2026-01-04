-- Enable required PostgreSQL extensions

-- UUID generation (for UUIDv7)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Cryptographic functions
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Full-text search optimization
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- Create custom function for UUIDv7 generation
-- UUIDv7 provides time-ordered UUIDs for better DB locality
CREATE OR REPLACE FUNCTION uuid_generate_v7()
RETURNS uuid AS $$
DECLARE
    unix_ts_ms bytea;
    uuid_bytes bytea;
BEGIN
    unix_ts_ms = substring(int8send(floor(extract(epoch from clock_timestamp()) * 1000)::bigint) from 3);
    uuid_bytes = unix_ts_ms || gen_random_bytes(10);

    -- Set version 7
    uuid_bytes = set_byte(uuid_bytes, 6, (get_byte(uuid_bytes, 6) & 15) | 112);
    -- Set variant (RFC 4122)
    uuid_bytes = set_byte(uuid_bytes, 8, (get_byte(uuid_bytes, 8) & 63) | 128);

    RETURN encode(uuid_bytes, 'hex')::uuid;
END;
$$ LANGUAGE plpgsql VOLATILE;

-- Audit log trigger function
CREATE OR REPLACE FUNCTION audit_trigger_func()
RETURNS TRIGGER AS $$
BEGIN
    IF (TG_OP = 'DELETE') THEN
        INSERT INTO audit_events (action, resource_type, resource_id, metadata, created_at)
        VALUES (TG_OP, TG_TABLE_NAME, OLD.id::text, to_jsonb(OLD), NOW());
        RETURN OLD;
    ELSIF (TG_OP = 'UPDATE') THEN
        INSERT INTO audit_events (action, resource_type, resource_id, metadata, created_at)
        VALUES (TG_OP, TG_TABLE_NAME, NEW.id::text, jsonb_build_object('old', to_jsonb(OLD), 'new', to_jsonb(NEW)), NOW());
        RETURN NEW;
    ELSIF (TG_OP = 'INSERT') THEN
        INSERT INTO audit_events (action, resource_type, resource_id, metadata, created_at)
        VALUES (TG_OP, TG_TABLE_NAME, NEW.id::text, to_jsonb(NEW), NOW());
        RETURN NEW;
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;
