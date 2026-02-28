#!/usr/bin/env node
// Fetches Portland, OR weather (today + tomorrow) from Open-Meteo and caches it.
// Called by statusline.js in background when cache is stale.
const https = require('https');
const fs = require('fs');
const path = require('path');
const os = require('os');

const CACHE_PATH = path.join(os.homedir(), '.claude', 'cache', 'weather-portland.json');

const url =
  'https://api.open-meteo.com/v1/forecast?' +
  'latitude=45.5152&longitude=-122.6784' +
  '&daily=temperature_2m_max,temperature_2m_min,weather_code' +
  '&temperature_unit=fahrenheit&timezone=America/Los_Angeles&forecast_days=2';

https.get(url, res => {
  let data = '';
  res.on('data', chunk => data += chunk);
  res.on('end', () => {
    try {
      const j = JSON.parse(data);
      const d = j.daily;
      if (!d || !d.time) process.exit(1);
      const out = {
        fetched_at: new Date().toISOString(),
        today: {
          hi: Math.round(d.temperature_2m_max[0]),
          lo: Math.round(d.temperature_2m_min[0]),
          code: d.weather_code[0],
        },
        tomorrow: d.time[1]
          ? {
              hi: Math.round(d.temperature_2m_max[1]),
              lo: Math.round(d.temperature_2m_min[1]),
              code: d.weather_code[1],
            }
          : null,
      };
      fs.mkdirSync(path.dirname(CACHE_PATH), { recursive: true });
      fs.writeFileSync(CACHE_PATH, JSON.stringify(out, null, 2));
    } catch (e) {
      process.exit(1);
    }
  });
}).on('error', () => process.exit(1));
