-- Personal shared Supabase schema for this Daedalus project.
-- Operators must allow-list "medley" in Supabase Data API settings.
CREATE SCHEMA IF NOT EXISTS "medley";

GRANT USAGE ON SCHEMA "medley" TO anon, authenticated, service_role;
GRANT ALL ON SCHEMA "medley" TO postgres, service_role;
ALTER DEFAULT PRIVILEGES IN SCHEMA "medley" GRANT ALL ON TABLES TO postgres, service_role;
ALTER DEFAULT PRIVILEGES IN SCHEMA "medley" GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO anon, authenticated;
