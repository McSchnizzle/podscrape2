import { NextResponse } from 'next/server'
import { getPool } from '@/utils/db'
import { requireAuth } from '@/lib/auth-guard'
import { createLogger } from '@/lib/logger'

const log = createLogger('api/dashboard/summary')

export const dynamic = 'force-dynamic'

/**
 * Lean, hand-verified dashboard summary (kanban #2846 Phase 2).
 *
 * Replaces the old /api/dashboard/analytics panels (workflow/transcript/
 * performance/error "analytics" that were never accurate per Paul). Every
 * query here was run by hand against podcast-db and cross-checked before
 * being wired in -- see the Phase 2 report for the verification table.
 *
 * "Latest published episode" intentionally mirrors the exact WHERE/ORDER BY
 * used by /api/rss/ai-tech-digest (topic = 'AI and Technology' AND
 * github_url IS NOT NULL AND mp3_path IS NOT NULL, ordered by digest_date
 * then generated_at) instead of MAX(published_at). digests.published_at was
 * bulk-backfilled to a single migration timestamp for every historical row
 * (kanban #2669 Supabase-to-local-Postgres cutover), so ORDER BY
 * published_at DESC returns whichever row the backfill touched last, not
 * the actual newest release -- that was one of the "never accurate" old
 * dashboard numbers.
 */
export async function GET() {
  const auth = await requireAuth()
  if (!auth.authorized) return auth.error!

  try {
    const pool = getPool()

    const [latestEpisodeRes, statusNowRes, statusTodayRes, lastOutcomeRes, feedsRes, failingFeedsRes, watchThemesRes] =
      await Promise.all([
        pool.query(`
          SELECT id, topic, to_char(digest_date, 'YYYY-MM-DD') AS digest_date,
                 mp3_title, mp3_duration_seconds, mp3_path, github_url, generated_at
          FROM digests
          WHERE topic = 'AI and Technology'
            AND github_url IS NOT NULL
            AND mp3_path IS NOT NULL
          ORDER BY digest_date DESC, generated_at DESC NULLS LAST
          LIMIT 1
        `),
        pool.query(`SELECT status, COUNT(*)::int AS count FROM episodes GROUP BY status`),
        pool.query(`
          SELECT status, COUNT(*)::int AS count
          FROM episodes
          WHERE updated_at::date = CURRENT_DATE
          GROUP BY status
        `),
        pool.query(`
          SELECT id, topic, to_char(digest_date, 'YYYY-MM-DD') AS digest_date, status,
                 generated_at, LENGTH(script_content) AS script_chars,
                 (github_url IS NOT NULL AND mp3_path IS NOT NULL) AS published
          FROM digests
          ORDER BY generated_at DESC NULLS LAST
          LIMIT 1
        `),
        pool.query(`
          SELECT COUNT(*) FILTER (WHERE active)::int AS active_count, COUNT(*)::int AS total_count
          FROM feeds
        `),
        pool.query(`
          SELECT id, title, consecutive_failures, last_checked
          FROM feeds
          WHERE consecutive_failures > 0
          ORDER BY consecutive_failures DESC
        `),
        pool.query(`
          SELECT id, name, scope
          FROM watch_themes
          WHERE active = true
          ORDER BY sort_order, id
        `),
      ])

    const statusNow: Record<string, number> = {}
    for (const row of statusNowRes.rows) statusNow[row.status] = row.count

    const statusToday: Record<string, number> = {}
    for (const row of statusTodayRes.rows) statusToday[row.status] = row.count

    const outcome = lastOutcomeRes.rows[0] || null

    return NextResponse.json({
      latestEpisode: latestEpisodeRes.rows[0] || null,
      pipelineReadiness: {
        // Current backlog snapshot, by status, right now.
        now: statusNow,
        // Episodes whose status changed today (freshness signal).
        updatedToday: statusToday,
      },
      lastOutcome: outcome
        ? {
            ...outcome,
            script_chars: outcome.script_chars === null ? null : Number(outcome.script_chars),
          }
        : null,
      feeds: {
        active: feedsRes.rows[0]?.active_count ?? 0,
        total: feedsRes.rows[0]?.total_count ?? 0,
        failing: failingFeedsRes.rows,
      },
      activeWatchThemes: watchThemesRes.rows,
      generatedAt: new Date().toISOString(),
    })
  } catch (error) {
    log.error('Failed to load dashboard summary', {
      error: error instanceof Error ? error.message : 'Unknown error',
    })
    return NextResponse.json({ error: 'Failed to load dashboard summary' }, { status: 500 })
  }
}
