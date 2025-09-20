import { NextRequest, NextResponse } from "next/server";
import { DatabaseClient } from "@/utils/supabase";

export const dynamic = 'force-dynamic';

export async function GET(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url);
    const q = searchParams.get('q') || '';
    const status = searchParams.get('status') || '';
    const sortBy = searchParams.get('sortBy') || 'scored_at';
    const sortDir = searchParams.get('sortDir') || 'desc';
    const limit = parseInt(searchParams.get('limit') || '100');

    const db = new DatabaseClient();

    // Test database connection first
    const healthCheck = await db.getSystemHealth();
    console.log('Database health check:', healthCheck);

    if (healthCheck.database === 'error') {
      return NextResponse.json({
        error: 'Database connection failed',
        detail: healthCheck.error
      }, { status: 500 });
    }

    // Get episodes with filters
    const episodes = await db.getEpisodes({
      q,
      status,
      sortBy,
      sortDir,
      limit
    });

    console.log(`Found ${episodes.length} episodes with filters:`, { q, status, sortBy, sortDir, limit });

    // Get recent digests to build inclusion map
    const recentDigests = await db.getRecentDigests(14);
    const inclusionMap: Record<number, Array<{ topic: string; date: string }>> = {};

    for (const digest of recentDigests) {
      if (digest.episode_ids) {
        for (const episodeId of digest.episode_ids) {
          if (!inclusionMap[episodeId]) {
            inclusionMap[episodeId] = [];
          }
          inclusionMap[episodeId].push({
            topic: digest.topic,
            date: digest.digest_date || digest.created_at.split('T')[0]
          });
        }
      }
    }

    // Process episodes for display
    const processedEpisodes = episodes.map(ep => {
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
        feed_title_display: 'Unknown Feed', // TODO: Re-add feed join once basic query works
        score_labels: scoreLabels,
        included: inclusionMap[ep.id] || [],
        scores: ep.scores || {}
      };
    });

    return NextResponse.json({
      episodes: processedEpisodes,
      total: processedEpisodes.length
    });
  } catch (error) {
    console.error('Episodes API error:', error);
    return NextResponse.json({ error: 'Failed to fetch episodes' }, { status: 500 });
  }
}