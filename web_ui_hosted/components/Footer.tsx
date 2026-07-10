'use client';

import { useState, useEffect } from 'react';
import { getBuildInfo } from '@/app/version';

export default function Footer() {
  const [buildInfo, setBuildInfo] = useState<{
    version: string;
    commit: string;
    buildTime: string;
    buildDate: string;
  } | null>(null);

  useEffect(() => {
    setBuildInfo(getBuildInfo());
  }, []);

  if (!buildInfo) {
    return null;
  }

  return (
    <footer className="mt-auto border-t border-border bg-surface-1">
      <div className="mx-auto max-w-7xl px-[var(--space-6)] py-[var(--space-4)]">
        <div className="flex flex-col items-center justify-between gap-[var(--space-2)] text-ink-subtle sm:flex-row" style={{ font: 'var(--t-small)' }}>
          <div className="flex items-center gap-[var(--space-3)]">
            <span className="font-medium text-ink-muted">RSS Podcast Digest System</span>
            <span className="text-ink-faint">|</span>
            <span>v{buildInfo.version}</span>
          </div>

          <div className="flex items-center gap-[var(--space-3)]">
            <span className="font-mono text-ink-faint">{buildInfo.commit}</span>
            <span className="text-ink-faint">|</span>
            <span title={buildInfo.buildTime}>{buildInfo.buildDate}</span>
          </div>
        </div>
      </div>
    </footer>
  );
}
