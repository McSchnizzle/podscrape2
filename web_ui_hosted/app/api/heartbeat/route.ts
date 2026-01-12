import { NextResponse } from 'next/server';
import { VERSION, getBuildInfo } from '../../version';

export const dynamic = 'force-dynamic';

export async function GET(request: Request) {
  const isVercelCron = request.headers.get('x-vercel-cron') === '1';
  if (!isVercelCron && process.env.CRON_SECRET) {
    const authHeader = request.headers.get('authorization');
    if (authHeader !== `Bearer ${process.env.CRON_SECRET}`) {
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    }
  }

  const buildInfo = getBuildInfo();
  const heartbeat = {
    status: 'healthy',
    version: VERSION,
    metadata: {
      project_name: 'podscrape-admin',
      git_commit: process.env.VERCEL_GIT_COMMIT_SHA?.slice(0, 7) || buildInfo.commit,
      git_commit_date: buildInfo.buildTime,
      git_branch: process.env.VERCEL_GIT_COMMIT_REF || '',
      type: 'vercel-cron',
      script_version: '1.2.0',
    },
  };

  try {
    const response = await fetch('https://projects.paulrbrown.org/api/heartbeats', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${process.env.PROJECT_DASHBOARD_API_KEY}`,
      },
      body: JSON.stringify(heartbeat),
    });

    if (!response.ok) {
      const errorText = await response.text();
      console.error('Heartbeat failed:', response.status, errorText);
      return NextResponse.json({ error: 'Heartbeat failed', details: errorText }, { status: 500 });
    }

    return NextResponse.json({ success: true, timestamp: new Date().toISOString() });
  } catch (error) {
    console.error('Heartbeat error:', error);
    return NextResponse.json({ error: 'Failed to send heartbeat', details: String(error) }, { status: 500 });
  }
}
