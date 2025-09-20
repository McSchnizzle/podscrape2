import { NextRequest, NextResponse } from "next/server";
import { DatabaseClient } from "@/utils/supabase";

export async function POST(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  try {
    const episodeId = parseInt(params.id);
    const body = await request.json();
    const { action } = body;

    if (!episodeId || isNaN(episodeId)) {
      return NextResponse.json({ error: 'Invalid episode ID' }, { status: 400 });
    }

    const db = new DatabaseClient();

    if (action === 'undigest') {
      // Reset episode to 'scored' status
      await db.updateEpisodeStatus(episodeId, 'scored');
      return NextResponse.json({
        success: true,
        message: 'Episode reset to scored status'
      });
    } else if (action === 'reset_to_pending') {
      // Reset episode to 'pending' status
      await db.updateEpisodeStatus(episodeId, 'discovered');
      return NextResponse.json({
        success: true,
        message: 'Episode reset to pending status'
      });
    } else {
      return NextResponse.json({ error: 'Invalid action' }, { status: 400 });
    }
  } catch (error) {
    console.error('Episode action error:', error);
    return NextResponse.json({ error: 'Failed to process episode action' }, { status: 500 });
  }
}