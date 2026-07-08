/**
 * Direct Postgres access for public routes (RSS feeds, health).
 *
 * After the Supabase project deletion (kanban #2669) the pipeline database is
 * a local Postgres (podcast-db container, 127.0.0.1:5470). Public read routes
 * query it directly with pg; the Supabase-backed admin routes remain parked
 * until the admin UI gets a new auth + data backend.
 */
import { Pool } from 'pg'

let pool: Pool | null = null

export function getPool(): Pool {
  if (!pool) {
    const connectionString = process.env.DATABASE_URL
    if (!connectionString) {
      throw new Error('DATABASE_URL is not set')
    }
    pool = new Pool({ connectionString, max: 5 })
  }
  return pool
}
