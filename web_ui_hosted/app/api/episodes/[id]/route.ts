import { NextRequest, NextResponse } from "next/server";
import { DatabaseClient } from "@/utils/supabase";
import { revalidateTag } from 'next/cache';
import { requireAuth } from '@/lib/auth-guard'
import { createLogger } from '@/lib/logger'

const log = createLogger('api/episodes/[id]')

export async function POST(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  const auth = await requireAuth()
  if (!auth.authorized) return auth.error!

  try {
    const episodeId = parseInt(params.id);
    const body = await request.json();
    const { action } = body;

    if (!episodeId || isNaN(episodeId)) {
      return NextResponse.json({ error: 'Invalid episode ID' }, { status: 400 });
    }

    const db = DatabaseClient.getInstance();

    if (action === 'undigest') {
      // Reset episode to 'scored' status
      await db.updateEpisodeStatus(episodeId, 'scored');

      // Invalidate episodes cache
      revalidateTag('episodes-data');
      log.info('Episodes cache invalidated after undigest action', { episodeId });

      return NextResponse.json({
        success: true,
        message: 'Episode reset to scored status'
      });
    } else if (action === 'reset_to_pending') {
      // Reset episode to 'pending' status, clear scores, and remove from digests
      const result = await db.resetEpisodeToPending(episodeId);

      // Invalidate episodes cache
      revalidateTag('episodes-data');
      log.info('Episodes cache invalidated after reset_to_pending action', { episodeId });

      return NextResponse.json({
        success: true,
        message: result.message,
        digestsAffected: result.digestsAffected
      });
    } else {
      return NextResponse.json({ error: 'Invalid action' }, { status: 400 });
    }
  } catch (error) {
    log.error('Episode action error', { error: error instanceof Error ? error.message : 'Unknown error' });
    return NextResponse.json({ error: 'Failed to process episode action' }, { status: 500 });
  }
}