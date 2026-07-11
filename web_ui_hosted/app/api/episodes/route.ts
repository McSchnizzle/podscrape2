import { NextRequest, NextResponse } from "next/server";
import { DatabaseClient, Episode } from "@/utils/supabase";
import { requireAuth } from '@/lib/auth-guard'
import { createLogger } from '@/lib/logger'

const log = createLogger('api/episodes')

export const dynamic = 'force-dynamic';

export async function GET(request: NextRequest) {
  const auth = await requireAuth()
  if (!auth.authorized) return auth.error!

  try {
    const { searchParams } = new URL(request.url);
    const q = searchParams.get('q') || '';
    const status = searchParams.get('status') || '';
    const sortBy = searchParams.get('sortBy') || 'scored_at';
    const sortDir = searchParams.get('sortDir') || 'desc';
    const page = parseInt(searchParams.get('page') || '0');
    const pageSize = parseInt(searchParams.get('pageSize') || '25');

    log.debug('Request filters', { q, status, sortBy, sortDir, page, pageSize });

    const db = DatabaseClient.getInstance();

    // Get episodes with filters and pagination
    const result = await db.getEpisodes({
      q,
      status,
      sortBy,
      sortDir,
      page,
      pageSize
    });

    // Log what we got back to debug filtering issues
    if (status) {
      const statusMismatch = result.episodes.filter((ep: Episode) => ep.status !== status);
      if (statusMismatch.length > 0) {
        log.error('Filter status mismatch', {
          requestedStatus: status,
          mismatchCount: statusMismatch.length,
          samples: statusMismatch.slice(0, 3).map((ep: Episode) => ({ id: ep.id, status: ep.status, title: ep.title?.substring(0, 40) }))
        });
      }
    }

    // Process episodes for display
    const processedEpisodes = result.episodes.map((ep: Episode & { feeds?: { title: string } }) => {
      // Create score labels. Keys starting with "_" (e.g. "_harold_rnd",
      // kanban #2855's reserved Harold R&D-applicability rating) are an
      // internal storage detail of episodes.scores, not a podcast topic --
      // exclude them from both the display labels and the raw scores this
      // endpoint returns.
      const scores = ep.scores || {};
      const topicScores = Object.fromEntries(
        Object.entries(scores).filter(([topic]) => !topic.startsWith('_'))
      );
      const scoreLabels = Object.entries(topicScores)
        .map(([topic, score]) => {
          const shortTopic = topic === 'AI and Technology' ? 'Tech'
            : topic === 'Social Movements and Community Organizing' ? 'Organizing'
            : topic.split(' ')[0];
          return `${shortTopic}=${(score as number).toFixed(2)}`;
        })
        .join(', ');

      return {
        id: ep.id,
        title: ep.title,
        status: ep.status,
        published_date: ep.published_date,
        scored_at: ep.scored_at,
        feed_title_display: ep.feeds?.title || 'Unknown Feed',
        score_labels: scoreLabels,
        included: ep.inclusion || [],
        scores: topicScores
      };
    });

    const response = {
      episodes: processedEpisodes,
      total: result.totalCount,
      page,
      pageSize,
      totalPages: Math.ceil(result.totalCount / pageSize)
    };

    log.info('Returning episodes', { count: response.episodes.length, page: page + 1, totalPages: response.totalPages });

    return NextResponse.json(response);
  } catch (error) {
    log.error('Failed to fetch episodes', { error: error instanceof Error ? error.message : 'Unknown error' });
    return NextResponse.json({ error: 'Failed to fetch episodes' }, { status: 500 });
  }
}
