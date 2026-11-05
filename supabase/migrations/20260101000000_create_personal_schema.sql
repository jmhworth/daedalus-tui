-- Personal shared Supabase schema for this Daedalus project.
-- Operators must allow-list "daedalus-tui" in Supabase Data API settings.
CREATE SCHEMA IF NOT EXISTS "daedalus-tui";

GRANT USAGE ON SCHEMA "daedalus-tui" TO anon, authenticated, service_role;
GRANT ALL ON SCHEMA "daedalus-tui" TO postgres, service_role;
ALTER DEFAULT PRIVILEGES IN SCHEMA "daedalus-tui" GRANT ALL ON TABLES TO postgres, service_role;
ALTER DEFAULT PRIVILEGES IN SCHEMA "daedalus-tui" GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO anon, authenticated;
