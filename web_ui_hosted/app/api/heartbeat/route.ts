import { NextResponse } from 'next/server';
import { VERSION } from '../../version';

export const dynamic = 'force-dynamic';

export async function GET(request: Request) {
  const isVercelCron = request.headers.get('x-vercel-cron') === '1';
  if (!isVercelCron && process.env.CRON_SECRET) {
    const authHeader = request.headers.get('authorization');
    if (authHeader !== `Bearer ${process.env.CRON_SECRET}`) {
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    }
  }

  const heartbeat = {
    status: 'healthy',
    version: VERSION,
    metadata: {
      project_name: 'podscrape-admin',
      git_commit: process.env.VERCEL_GIT_COMMIT_SHA?.slice(0, 7),
      git_commit_date: process.env.VERCEL_GIT_COMMIT_DATE || '',
      git_branch: process.env.VERCEL_GIT_COMMIT_REF,
      type: 'vercel-cron',
      script_version: '1.1.0',
    },
  };

  await fetch('https://projects.paulrbrown.org/api/heartbeats', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${process.env.PROJECT_DASHBOARD_API_KEY}`,
    },
    body: JSON.stringify(heartbeat),
  });

  return NextResponse.json({ success: true });
}
