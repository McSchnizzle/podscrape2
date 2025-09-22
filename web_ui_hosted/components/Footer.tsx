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
    <footer className="mt-auto border-t border-gray-200 bg-gray-50">
      <div className="max-w-7xl mx-auto px-4 py-4">
        <div className="flex flex-col sm:flex-row justify-between items-center text-sm text-gray-600">
          <div className="flex items-center space-x-4">
            <span className="font-medium">RSS Podcast Digest System</span>
            <span className="text-gray-400">|</span>
            <span>v{buildInfo.version}</span>
          </div>

          <div className="flex items-center space-x-4 mt-2 sm:mt-0">
            <span className="text-gray-500">
              Build: {buildInfo.commit}
            </span>
            <span className="text-gray-400">|</span>
            <span className="text-gray-500" title={buildInfo.buildTime}>
              {buildInfo.buildDate}
            </span>
          </div>
        </div>
      </div>
    </footer>
  );
}