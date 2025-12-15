import { NextRequest, NextResponse } from "next/server";
import { DatabaseClient, Episode } from "@/utils/supabase";

export const dynamic = 'force-dynamic';

export async function GET(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url);
    const q = searchParams.get('q') || '';
    const status = searchParams.get('status') || '';
    const sortBy = searchParams.get('sortBy') || 'scored_at';
    const sortDir = searchParams.get('sortDir') || 'desc';
    const limit = parseInt(searchParams.get('limit') || '100');

    console.log(`[Episodes API] Request filters:`, { q, status, sortBy, sortDir, limit });

    const db = DatabaseClient.getInstance();

    // Get episodes with filters
    const episodes = await db.getEpisodes({
      q,
      status,
      sortBy,
      sortDir,
      limit
    });

    // Log what we got back to debug filtering issues
    if (status) {
      const statusMismatch = episodes.filter((ep: Episode) => ep.status !== status);
      if (statusMismatch.length > 0) {
        console.error(`[Episodes API] BUG: Filter requested status='${status}' but got ${statusMismatch.length} episodes with different status:`,
          statusMismatch.map((ep: Episode) => ({ id: ep.id, status: ep.status, title: ep.title?.substring(0, 40) }))
        );
      }
    }

    // Process episodes for display
    const processedEpisodes = episodes.map((ep: Episode & { feeds?: { title: string } }) => {
      // Create score labels
      const scores = ep.scores || {};
      const scoreLabels = Object.entries(scores)
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
        scores: ep.scores || {}
      };
    });

    const result = {
      episodes: processedEpisodes,
      total: processedEpisodes.length
    };

    console.log(`Returning ${result.episodes.length} episodes`);

    return NextResponse.json(result);
  } catch (error) {
    console.error('Episodes API error:', error);
    return NextResponse.json({ error: 'Failed to fetch episodes' }, { status: 500 });
  }
}
