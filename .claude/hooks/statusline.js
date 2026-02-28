#!/usr/bin/env node
// Custom statusline — Shows: model | task | commit age | Portland weather | dir | context
const fs = require('fs');
const path = require('path');
const os = require('os');
const { execSync, spawn } = require('child_process');

const homeDir = os.homedir();
const WEATHER_CACHE = path.join(homeDir, '.claude', 'cache', 'weather-portland.json');
const WEATHER_TTL_MS = 30 * 60 * 1000; // 30 minutes
const WEATHER_SCRIPT = path.join(__dirname, 'weather-refresh.js');

// WMO weather code → emoji
const WMO = {
  0:'☀️',1:'🌤️',2:'⛅',3:'☁️',45:'🌫️',48:'🌫️',
  51:'🌧️',53:'🌧️',55:'🌧️',61:'🌧️',63:'🌧️',65:'⛈️',
  71:'❄️',73:'❄️',75:'❄️',77:'❄️',80:'🌧️',81:'🌧️',82:'⛈️',
  85:'❄️',86:'❄️',95:'⛈️',96:'⛈️',99:'⛈️'
};

function getWeather() {
  try {
    if (!fs.existsSync(WEATHER_CACHE)) {
      refreshWeather();
      return '';
    }
    const stat = fs.statSync(WEATHER_CACHE);
    if (Date.now() - stat.mtimeMs > WEATHER_TTL_MS) refreshWeather();

    const cache = JSON.parse(fs.readFileSync(WEATHER_CACHE, 'utf8'));
    const { today, tomorrow } = cache;
    if (!today) return '';

    let s = `${WMO[today.code] || '❓'}${today.hi}/${today.lo}°`;
    if (tomorrow) s += ` tmw ${WMO[tomorrow.code] || '❓'}${tomorrow.hi}/${tomorrow.lo}°`;
    return s;
  } catch (e) { return ''; }
}

function refreshWeather() {
  try {
    if (!fs.existsSync(WEATHER_SCRIPT)) return;
    const child = spawn('node', [WEATHER_SCRIPT], { detached: true, stdio: 'ignore' });
    child.unref();
  } catch (e) {}
}

function getCommitAge(dir) {
  try {
    const ts = parseInt(
      execSync('git log -1 --format=%ct', { cwd: dir, encoding: 'utf8', timeout: 2000 }).trim(),
      10
    );
    const sec = Math.floor(Date.now() / 1000) - ts;
    let label, color;
    if (sec < 3600) {
      label = `${Math.max(1, Math.floor(sec / 60))}m`;
      color = '\x1b[92m'; // bright green
    } else if (sec < 86400) {
      label = `${Math.floor(sec / 3600)}h`;
      color = '\x1b[92m'; // bright green
    } else {
      const d = Math.floor(sec / 86400);
      label = `${d}d`;
      color = d > 3 ? '\x1b[91m' : '\x1b[93m'; // bright red or bright yellow
    }
    return `${color}⏱${label}\x1b[0m`;
  } catch (e) { return ''; }
}

// ── Main ───────────────────────────────
let input = '';
process.stdin.setEncoding('utf8');
process.stdin.on('data', chunk => input += chunk);
process.stdin.on('end', () => {
  try {
    const data = JSON.parse(input);
    const model = data.model?.display_name || 'Claude';
    const dir = data.workspace?.current_dir || process.cwd();
    const session = data.session_id || '';
    const remaining = data.context_window?.remaining_percentage;

    // Context window bar (scaled to 80% limit)
    let ctx = '';
    if (remaining != null) {
      const rawUsed = Math.max(0, Math.min(100, 100 - Math.round(remaining)));
      const used = Math.min(100, Math.round((rawUsed / 80) * 100));
      const filled = Math.floor(used / 10);
      const bar = '█'.repeat(filled) + '░'.repeat(10 - filled);
      if (used < 63)       ctx = ` \x1b[32m${bar} ${used}%\x1b[0m`;
      else if (used < 81)  ctx = ` \x1b[33m${bar} ${used}%\x1b[0m`;
      else if (used < 95)  ctx = ` \x1b[38;5;208m${bar} ${used}%\x1b[0m`;
      else                 ctx = ` \x1b[5;31m💀 ${bar} ${used}%\x1b[0m`;
    }

    // Current task from todos
    let task = '';
    const todosDir = path.join(homeDir, '.claude', 'todos');
    if (session && fs.existsSync(todosDir)) {
      try {
        const files = fs.readdirSync(todosDir)
          .filter(f => f.startsWith(session) && f.includes('-agent-') && f.endsWith('.json'))
          .map(f => ({ name: f, mtime: fs.statSync(path.join(todosDir, f)).mtime }))
          .sort((a, b) => b.mtime - a.mtime);
        if (files.length > 0) {
          const todos = JSON.parse(fs.readFileSync(path.join(todosDir, files[0].name), 'utf8'));
          const ip = todos.find(t => t.status === 'in_progress');
          if (ip) task = ip.activeForm || '';
        }
      } catch (e) {}
    }

    // Assemble — all text uses bright colors (no dim \x1b[2m) for dark terminals
    const parts = [`\x1b[96m${model}\x1b[0m`];
    if (task) parts.push(`\x1b[97;1m${task}\x1b[0m`);
    const commit = getCommitAge(dir);
    if (commit) parts.push(commit);
    const weather = getWeather();
    if (weather) parts.push(weather);
    parts.push(`\x1b[96m${path.basename(dir)}\x1b[0m`);

    process.stdout.write(parts.join(' │ ') + ctx);
  } catch (e) {}
});
