/**
 * Shared constants safe to import from client components.
 *
 * Do NOT add anything here that touches secrets or utils/supabase.ts --
 * this module exists specifically so client pages (app/episodes/page.tsx)
 * don't have to import from utils/supabase.ts just to get a status list,
 * which used to drag the server-only Supabase client (and
 * SUPABASE_SERVICE_ROLE) into the client bundle (kanban #2846 codex review).
 */
/**
 * Valid episode status values - keep in sync with EpisodeStatus Python enum
 * @see src/database/episode_status.py
 */
export const EPISODE_STATUSES = [
  'pending',
  'processing',
  'transcribed',
  'scored',
  'not_relevant',
  'digested',
  'failed',
] as const

export type EpisodeStatusType = (typeof EPISODE_STATUSES)[number]
