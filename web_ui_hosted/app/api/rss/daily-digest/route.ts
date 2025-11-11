/**
 * Dynamic RSS Feed API Route (v1.49)
 *
 * ARCHITECTURE: This API route generates the RSS feed dynamically from the Supabase database.
 *
 * How it works:
 * 1. Queries Supabase for digests where github_url and mp3_path are set
 * 2. Generates RSS 2.0 XML with proper enclosures pointing to GitHub release assets
 * 3. Returns XML with edge caching headers (5 min cache, 10 min stale-while-revalidate)
 *
 * Benefits over static files:
 * - Instant updates (no git commits or redeployments needed)
 * - Always accurate (reads current database state)
 * - Fast for users (Vercel edge caching, typically 20-50ms response)
 * - Simpler pipeline (publishing just uploads MP3s and updates database)
 *
 * URL Mapping:
 * - Public URL: https://podcast.paulrbrown.org/daily-digest.xml
 * - API Route: /api/rss/daily-digest
 * - Rewrite configured in: web_ui_hosted/vercel.json
 *
 * Publishing Pipeline:
 * - Phase 5 (scripts/run_publishing.py) uploads MP3s to GitHub and updates database
 * - This API route automatically serves the latest episodes from database
 * - No coordination needed between pipeline and RSS generation
 */

import { NextRequest, NextResponse } from 'next/server';
import { supabase } from '@/utils/supabase';

export const dynamic = 'force-dynamic';
export const revalidate = 300; // Cache for 5 minutes

interface Digest {
  id: number;
  topic: string;
  digest_date: string;
  mp3_path: string | null;
  mp3_title: string | null;
  mp3_summary: string | null;
  mp3_duration_seconds: number | null;
  github_url: string | null;
  generated_at: string | null;
}

/**
 * Generate unique pubDate for each episode
 * Uses digest_date as base, topic for offset, and generated_at timestamp for uniqueness
 */
function generateUniquePubDate(digestDate: string, topic: string, generatedAt: string | null, mp3Path: string | null): string {
  const baseDate = new Date(digestDate + 'T12:00:00-08:00'); // Noon Pacific

  // Topic offset (hours) to ensure different topics have different times
  const topicOffsets: Record<string, number> = {
    'AI and Technology': 0,
    'Social Movements and Community Organizing': 3,
    'Psychedelics and Spirituality': 6
  };
  const topicOffset = topicOffsets[topic] || 0;
  baseDate.setHours(baseDate.getHours() + topicOffset);

  // Add generated_at timestamp offset (minutes) for uniqueness
  if (generatedAt) {
    const generatedDate = new Date(generatedAt);
    const minuteOffset = generatedDate.getMinutes();
    baseDate.setMinutes(baseDate.getMinutes() + minuteOffset);
  }

  // Add mp3 filename offset (seconds) for additional uniqueness
  if (mp3Path) {
    const filename = mp3Path.split('/').pop() || '';
    const timestampMatch = filename.match(/_(\d{6})\.mp3$/);
    if (timestampMatch) {
      const timeStr = timestampMatch[1]; // HHMMSS
      const seconds = parseInt(timeStr.slice(4, 6)); // Extract seconds
      baseDate.setSeconds(seconds);
    }
  }

  return baseDate.toUTCString();
}

/**
 * Format duration in HH:MM:SS or MM:SS
 */
function formatDuration(seconds: number): string {
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const secs = seconds % 60;

  if (hours > 0) {
    return `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  }
  return `${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
}

/**
 * Generate RSS 2.0 XML feed
 */
function generateRSSXML(digests: Digest[]): string {
  const now = new Date();
  const repoName = process.env.GITHUB_REPOSITORY || 'McSchnizzle/podscrape2';

  let items = '';

  for (const digest of digests) {
    if (!digest.github_url || !digest.mp3_path) continue;

    const mp3Filename = digest.mp3_path.split('/').pop() || '';
    const mp3Url = `https://github.com/${repoName}/releases/download/daily-${digest.digest_date}/${encodeURIComponent(mp3Filename)}`;

    // Create unique GUID including MP3 filename (which contains timestamp)
    const mp3Basename = mp3Filename.replace('.mp3', '');
    const guid = `digest-${digest.digest_date}-${digest.topic.toLowerCase().replace(/\s+/g, '-')}-${mp3Basename}`;

    const pubDate = generateUniquePubDate(digest.digest_date, digest.topic, digest.generated_at, digest.mp3_path);
    const title = digest.mp3_title || `${digest.topic} - ${digest.digest_date}`;
    const description = digest.mp3_summary || `Daily digest for ${digest.topic}`;

    // Use database ID as episode number for consistency
    items += `
    <item>
      <title>${escapeXML(title)}</title>
      <description>${escapeXML(description)}</description>
      <pubDate>${pubDate}</pubDate>
      <guid isPermaLink="false">${escapeXML(guid)}</guid>
      <itunes:episode>${digest.id}</itunes:episode>
      <enclosure url="${escapeXML(mp3Url)}" length="0" type="audio/mpeg"/>
    </item>`;
  }

  const rss = `<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd">
  <channel>
    <title>Daily AI &amp; Tech Digest</title>
    <description>AI-curated daily digest of podcast conversations about artificial intelligence, technology trends, and digital innovation.</description>
    <link>https://podcast.paulrbrown.org</link>
    <language>en-us</language>
    <lastBuildDate>${now.toUTCString()}</lastBuildDate>
    <generator>RSS Podcast Digest System v2.0 (Dynamic API)</generator>
    <copyright>© 2025 Paul Brown</copyright>${items}
  </channel>
</rss>`;

  return rss;
}

/**
 * Escape special XML characters
 */
function escapeXML(str: string): string {
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&apos;');
}

/**
 * GET handler - generates RSS feed dynamically from database
 */
export async function GET(request: NextRequest) {
  try {
    console.log('[RSS API] Generating RSS feed from database...');

    // Query Supabase for recent digests with MP3s and GitHub URLs
    const { data: digests, error } = await supabase
      .from('digests')
      .select('id, topic, digest_date, mp3_path, mp3_title, mp3_summary, mp3_duration_seconds, github_url, generated_at')
      .not('github_url', 'is', null)
      .not('mp3_path', 'is', null)
      .order('digest_date', { ascending: false })
      .order('generated_at', { ascending: false })
      .limit(50);

    if (error) {
      console.error('[RSS API] Database error:', error);
      return new NextResponse('Error fetching digests from database', { status: 500 });
    }

    if (!digests || digests.length === 0) {
      console.warn('[RSS API] No published digests found');
      return new NextResponse('No published digests available', { status: 404 });
    }

    console.log(`[RSS API] Found ${digests.length} published digests, generating XML...`);

    // Generate RSS XML
    const rssXML = generateRSSXML(digests as Digest[]);

    console.log(`[RSS API] RSS feed generated successfully (${rssXML.length} bytes)`);

    // Return with proper caching headers
    return new NextResponse(rssXML, {
      status: 200,
      headers: {
        'Content-Type': 'application/xml; charset=utf-8',
        'Cache-Control': 'public, s-maxage=300, stale-while-revalidate=600', // 5 min cache, 10 min stale
        'X-RSS-Generated': new Date().toISOString(),
        'X-RSS-Episodes': digests.length.toString(),
      },
    });

  } catch (error) {
    console.error('[RSS API] Unexpected error:', error);
    return new NextResponse('Internal server error', { status: 500 });
  }
}
