# Row Level Security

Moved out of `CLAUDE.md` (2026-07-31). RLS is enabled on every table in the
`public` schema, per Supabase requirements.

## Policies

| Policy | Grants |
|---|---|
| `service_role_policy` | full CRUD, for backend operations and migrations |
| `authenticated_read_policy` | read-only, for the web UI where applicable |

## Connection requirements

- **Python backend**: `postgres` user (service role) via `DATABASE_URL` /
  `SUPABASE_PASSWORD`
- **Next.js web UI**: `SUPABASE_SERVICE_ROLE`
- **Alembic**: service role credentials; bypasses RLS automatically

Every path uses the service role, which is why RLS never blocks normal
operation. If database access fails, check in this order: service-role
credentials present in the environment, `DATABASE_URL` actually using the
`postgres` user, `SUPABASE_SERVICE_ROLE` set for the web UI.

## Adding a new table

RLS must be enabled in the SAME migration that creates the table, or the table
ships unprotected.

```python
# in your Alembic migration's upgrade()
op.execute("ALTER TABLE your_new_table ENABLE ROW LEVEL SECURITY;")
op.execute('''
    CREATE POLICY "service_role_policy" ON your_new_table
    FOR ALL TO service_role
    USING (true) WITH CHECK (true);
''')
op.execute('''
    CREATE POLICY "authenticated_read_policy" ON your_new_table
    FOR SELECT TO authenticated
    USING (true);
''')
```

## Checking state

```bash
python3 -m alembic current       # migration status
python3 -m alembic upgrade head  # apply pending migrations
```
