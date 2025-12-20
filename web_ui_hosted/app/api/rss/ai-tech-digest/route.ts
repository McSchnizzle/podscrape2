/**
 * PUBLIC ROUTE - No authentication required
 * This endpoint is intentionally public as an RSS feed consumed by podcast apps.
 *
 * AI & Technology Topic RSS Feed API Route (v2.08)
 *
 * ARCHITECTURE: This API route generates a topic-specific RSS feed from Supabase database.
 * Only includes digests from the "AI and Technology" topic.
 *
 * URL Mapping:
 * - Public URL: https://podcast.paulrbrown.org/ai-tech-digest.xml
 * - API Route: /api/rss/ai-tech-digest
 * - Rewrite configured in: web_ui_hosted/vercel.json
 */

import { NextRequest, NextResponse } from 'next/server';
import { supabase } from '@/utils/supabase';

export const dynamic = 'force-dynamic';
export const revalidate = 300; // Cache for 5 minutes

const TOPIC_FILTER = 'AI and Technology';

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
 */
function generateUniquePubDate(digestDate: string, generatedAt: string | null, mp3Path: string | null): string {
  const baseDate = new Date(digestDate + 'T12:00:00-08:00'); // Noon Pacific

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
 * Generate RSS 2.0 XML feed for AI & Technology topic
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
    const guid = `ai-tech-digest-${digest.digest_date}-${mp3Basename}`;

    const pubDate = generateUniquePubDate(digest.digest_date, digest.generated_at, digest.mp3_path);
    const title = digest.mp3_title || `AI & Tech Digest - ${digest.digest_date}`;
    const description = digest.mp3_summary || `Daily AI and Technology digest for ${digest.digest_date}`;

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
    <title>AI &amp; Technology Digest</title>
    <description>AI-curated daily digest focused exclusively on artificial intelligence, machine learning, technology trends, and digital innovation from across the podcast landscape.</description>
    <link>https://podcast.paulrbrown.org</link>
    <language>en-us</language>
    <lastBuildDate>${now.toUTCString()}</lastBuildDate>
    <generator>RSS Podcast Digest System v2.0 (Dynamic API)</generator>
    <copyright>© 2025 Paul Brown</copyright>
    <itunes:category text="Technology"/>
    <itunes:explicit>false</itunes:explicit>${items}
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
 * GET handler - generates RSS feed dynamically from database (AI & Technology only)
 */
export async function GET(request: NextRequest) {
  try {
    console.log(`[RSS API] Generating AI & Technology RSS feed from database...`);

    // Query Supabase for AI & Technology digests with MP3s and GitHub URLs
    const { data: digests, error } = await supabase
      .from('digests')
      .select('id, topic, digest_date, mp3_path, mp3_title, mp3_summary, mp3_duration_seconds, github_url, generated_at')
      .eq('topic', TOPIC_FILTER)
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
      console.warn(`[RSS API] No published ${TOPIC_FILTER} digests found`);
      return new NextResponse(`No published ${TOPIC_FILTER} digests available`, { status: 404 });
    }

    console.log(`[RSS API] Found ${digests.length} ${TOPIC_FILTER} digests, generating XML...`);

    // Generate RSS XML
    const rssXML = generateRSSXML(digests as Digest[]);

    console.log(`[RSS API] AI & Tech RSS feed generated successfully (${rssXML.length} bytes)`);

    // Return with proper caching headers
    return new NextResponse(rssXML, {
      status: 200,
      headers: {
        'Content-Type': 'application/xml; charset=utf-8',
        'Cache-Control': 'public, s-maxage=300, stale-while-revalidate=600', // 5 min cache, 10 min stale
        'X-RSS-Generated': new Date().toISOString(),
        'X-RSS-Episodes': digests.length.toString(),
        'X-RSS-Topic': TOPIC_FILTER,
      },
    });

  } catch (error) {
    console.error('[RSS API] Unexpected error:', error);
    return new NextResponse('Internal server error', { status: 500 });
  }
}
