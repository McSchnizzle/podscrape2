-- PostgREST role setup for podcast-db (local Supabase-compatible stack,
-- kanban #2846). Mirrors the role shape used by /srv/projects/assistant's
-- local-db stack, minus the vector/RLS extensions this project doesn't need.
--
-- podcast-db is a pre-existing, already-initialized container, so this does
-- NOT run via docker-entrypoint-initdb.d -- apply it with apply-roles.sh,
-- which is safe to re-run (roles are created only if missing; the
-- authenticator password and grants are always re-applied).
--
-- Invoke via psql with -v authpass='<AUTHENTICATOR_PASSWORD>' (apply-roles.sh
-- does this for you); it is not meant to be run with a bare `psql -f`.

DO $$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'authenticator') THEN
    CREATE ROLE authenticator NOINHERIT LOGIN;
  END IF;

  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'anon') THEN
    CREATE ROLE anon NOLOGIN;
  END IF;

  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'authenticated') THEN
    CREATE ROLE authenticated NOLOGIN;
  END IF;

  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'service_role') THEN
    CREATE ROLE service_role NOLOGIN BYPASSRLS;
  END IF;
END
$$;

-- Outside the DO block on purpose: psql's `:'var'` interpolation does not
-- expand inside dollar-quoted (`$$ ... $$`) bodies, so the password has to
-- be set here. Always re-applied, which also makes password rotation just
-- a re-run of this script.
ALTER ROLE authenticator PASSWORD :'authpass';

-- Let PostgREST switch from the authenticator login role into whichever role
-- a request resolves to (anon by default, or the JWT's "role" claim).
GRANT anon TO authenticator;
GRANT authenticated TO authenticator;
GRANT service_role TO authenticator;

GRANT USAGE ON SCHEMA public TO anon, authenticated, service_role;

-- service_role is the ONLY role this app's server code authenticates as
-- (via the minted JWT in SUPABASE_SERVICE_ROLE). It needs full read/write
-- on everything the admin UI touches, now and on tables added later.
GRANT ALL ON ALL TABLES IN SCHEMA public TO service_role;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO service_role;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO service_role;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO service_role;

-- anon and authenticated stay empty-privileged on purpose: nothing in this
-- app calls PostgREST as anon/authenticated today (Next.js middleware/
-- session cookie is the only auth boundary; both browser pages and API
-- routes reach the data layer server-side via service_role). Do not grant
-- anon table access without a corresponding RLS policy and an explicit
-- reason -- SCHEMA USAGE alone does not expose any row or column data.
