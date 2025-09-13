#!/usr/bin/env python3
"""
Lightweight Web UI for managing core settings.
Runs on localhost:5001 (optional), does not affect CLI unless started.
"""

import sys
import time
import os
import shutil
import threading
from pathlib import Path
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime
try:
    from flask import Flask, render_template, request, redirect, url_for, flash
except ImportError as e:
    print("ERROR: Flask is not installed for this Python interpreter.")
    print("Install with one of these:")
    print("  - python3 -m pip install Flask")
    print("  - python3 -m pip install -r requirements.txt")
    print("Recommended: use a venv → python3 -m venv .venv && source .venv/bin/activate && python -m pip install -r requirements.txt")
    raise

# Ensure project root and src are importable
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / 'src'))

from config.web_config import WebConfigManager, DEFAULTS
from config.config_manager import ConfigManager
from podcast.rss_models import get_feed_repo, get_podcast_episode_repo, PodcastFeed
from web_ui.utils import is_valid_feed_url, save_instruction_upload, digest_instructions_dir

try:
    import feedparser  # type: ignore
except Exception:
    feedparser = None
    
try:
    import requests  # type: ignore
except Exception:
    requests = None


def create_app():
    app = Flask(__name__)
    app.secret_key = 'dev-local-only'
    app.config['TEMPLATES_AUTO_RELOAD'] = True

    web_config = WebConfigManager()
    config_manager = ConfigManager(web_config=web_config)
    feed_repo = get_feed_repo()
    episode_repo = get_podcast_episode_repo()

    # Utility: start a background maintenance task that writes to a dedicated log
    def _start_maintenance_task(name: str, worker_func):
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        log_path = PROJECT_ROOT / f'maintenance_{name}_{ts}.log'
        try:
            with open(log_path, 'a', encoding='utf-8') as fh:
                fh.write(f"[web-ui] Starting maintenance: {name} at {datetime.now().isoformat()}\n")
                fh.flush()
        except Exception:
            pass
        t = threading.Thread(target=worker_func, args=(log_path,), daemon=True)
        t.start()
        return log_path

    def _find_latest_log():
        # Search only for full pipeline logs in project root
        logs = sorted(PROJECT_ROOT.glob('pipeline_run_*.log'), key=lambda p: p.stat().st_mtime, reverse=True)
        return logs[0] if logs else None

    def _list_recent_logs(limit=10):
        pats = ['pipeline_run_*.log', 'publishing_pipeline_*.log']
        logs = []
        for pat in pats:
            logs.extend(PROJECT_ROOT.glob(pat))
        logs.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        return logs[:limit]

    def _parse_log_summary(log_path: Path):
        summary = {
            'episodes': [],  # list of {title, feed, scores: {topic: score}, qualifying: [topic]}
            'digests': [],   # list of {topic, word_count, episode_titles: [], mp3_duration: int}
            'errors': []
        }
        # Build recent scored episodes from DB to ensure correct feed association
        try:
            from database.models import get_database_manager
            dbm = get_database_manager()
            # Time window: entries scored within last 6 hours of log mtime
            try:
                mtime = datetime.fromtimestamp(log_path.stat().st_mtime)
                since = (mtime - timedelta(hours=6)).isoformat()
            except Exception:
                since = None
            if since:
                rows = dbm.execute_query(
                    """
                    SELECT e.id as e_id, e.title as e_title, e.scores, e.scored_at, e.transcript_path, f.title AS f_title
                    FROM episodes e JOIN feeds f ON e.feed_id = f.id
                    WHERE e.scores IS NOT NULL AND e.scored_at >= ?
                    ORDER BY e.scored_at DESC LIMIT 10
                    """,
                    (since,)
                )
            else:
                rows = dbm.execute_query(
                    """
                    SELECT e.id as e_id, e.title as e_title, e.scores, e.scored_at, e.transcript_path, f.title AS f_title
                    FROM episodes e JOIN feeds f ON e.feed_id = f.id
                    WHERE e.scores IS NOT NULL
                    ORDER BY e.scored_at DESC LIMIT 10
                    """
                )
            # Threshold from ConfigManager/Web UI
            try:
                threshold = float(web_config.get_setting('content_filtering', 'score_threshold', 0.65))
            except Exception:
                threshold = 0.65
            import json as _json
            import os
            for r in rows:
                scores = _json.loads(r['scores']) if r['scores'] else {}
                # Use DB feed title as-is; avoid mutating feed_id here
                f_title = r['f_title']
                tpath = r['transcript_path']
                qualifying = [t for t, s in scores.items() if isinstance(s, (int, float)) and s >= threshold]
                summary['episodes'].append({
                    'title': r['e_title'],
                    'feed': f_title,
                    'scores': scores,
                    'qualifying': qualifying,
                })
        except Exception as e:
            summary['errors'].append(f'Failed to load recent scored episodes: {e}')

        # Digests created from DB (latest digest_date)
        try:
            # Pick latest digest_date in DB to represent most recent run
            # Fallback: use today
            # We'll query by max date across digests
            from database.models import get_database_manager
            dbm = get_database_manager()
            rows = dbm.execute_query("SELECT MAX(digest_date) as d FROM digests")
            latest_date = None
            if rows and rows[0]['d']:
                latest_date = rows[0]['d']
            if latest_date:
                rows = dbm.execute_query("SELECT * FROM digests WHERE digest_date = ?", (latest_date,))
                # Build map topic->digest info
                digests_info = {r['topic']: r for r in rows}
                # If no digests parsed from log, build from DB
                if not summary['digests']:
                    for topic, info in digests_info.items():
                        d = {
                            'topic': topic,
                            'word_count': info['script_word_count'],
                            'episode_count': info['episode_count'],
                        }
                        d['mp3_duration'] = info['mp3_duration_seconds']
                        try:
                            secs = int(d['mp3_duration'] or 0)
                            d['mp3_hms'] = f"{secs//60}:{secs%60:02d}"
                        except Exception:
                            d['mp3_hms'] = None
                        import json as _json
                        ids = _json.loads(info['episode_ids']) if info['episode_ids'] else []
                        titles = []
                        if ids:
                            placeholders = ','.join('?' for _ in ids)
                            q = f"SELECT title FROM episodes WHERE id IN ({placeholders})"
                            rows2 = dbm.execute_query(q, tuple(ids))
                            titles = [row['title'] for row in rows2]
                        d['episode_titles'] = titles
                        summary['digests'].append(d)
                else:
                    # Enrich parsed digests
                    for d in summary['digests']:
                        info = digests_info.get(d['topic'])
                        if info:
                            d['mp3_duration'] = info['mp3_duration_seconds']
                            try:
                                secs = int(d['mp3_duration'] or 0)
                                d['mp3_hms'] = f"{secs//60}:{secs%60:02d}"
                            except Exception:
                                d['mp3_hms'] = None
                            import json as _json
                            ids = _json.loads(info['episode_ids']) if info['episode_ids'] else []
                            titles = []
                            if ids:
                                placeholders = ','.join('?' for _ in ids)
                                q = f"SELECT title FROM episodes WHERE id IN ({placeholders})"
                                rows2 = dbm.execute_query(q, tuple(ids))
                                titles = [row['title'] for row in rows2]
                            d['episode_titles'] = titles
        except Exception as e:
            summary['errors'].append(f'Failed to enrich digest info: {e}')

        return summary

    @app.route('/')
    def dashboard():
        settings = {
            'content_filtering': web_config.get_category('content_filtering'),
            'audio_processing': web_config.get_category('audio_processing'),
            'pipeline': web_config.get_category('pipeline'),
        }
        # Last run info (from latest log)
        latest_log = _find_latest_log()
        last_run = None
        if latest_log:
            # Build best-effort metadata; don't block summary if stat fails
            last_run = {'name': latest_log.name, 'path': str(latest_log)}
            try:
                last_run.update({
                    'modified': datetime.fromtimestamp(latest_log.stat().st_mtime).isoformat(timespec='seconds'),
                    'size_kb': int(latest_log.stat().st_size / 1024),
                })
            except Exception:
                # Leave modified/size unset; summary can still render
                pass

        # Canonical RSS items from public/daily-digest.xml
        rss_items = []
        rss_path = PROJECT_ROOT / 'public' / 'daily-digest.xml'
        if rss_path.exists() and feedparser:
            try:
                parsed = feedparser.parse(str(rss_path))
                for entry in (parsed.entries or [])[:6]:
                    raw_date = entry.get('published') or entry.get('pubDate') or ''
                    date_disp = raw_date
                    try:
                        dt = parsedate_to_datetime(raw_date) if raw_date else None
                        if dt is not None:
                            date_disp = dt.strftime('%Y-%m-%d')
                    except Exception:
                        pass
                    rss_items.append({
                        'title': entry.get('title', 'Untitled'),
                        'date': date_disp,
                        'enclosure': (entry.enclosures[0].href if hasattr(entry, 'enclosures') and entry.enclosures else None)
                    })
            except Exception:
                pass

        # Episodes that are transcribed but not digested
        undigested = []
        try:
            transcribed = episode_repo.get_by_status('transcribed')
            scored = episode_repo.get_by_status('scored')
            for ep in (transcribed + scored):
                undigested.append(ep)
            undigested = undigested[:10]
            # Attach feed titles and compact score labels for display
            feed_cache = {}
            for ep in undigested:
                try:
                    fid = getattr(ep, 'feed_id', None)
                    if fid is not None:
                        if fid not in feed_cache:
                            f = feed_repo.get_by_id(fid)
                            feed_cache[fid] = f.title if f else 'Unknown Feed'
                        setattr(ep, 'feed_title', feed_cache[fid])
                    else:
                        setattr(ep, 'feed_title', 'Unknown Feed')
                    # Parse scores JSON to dict and create compact labels
                    import json as _json
                    scores = None
                    try:
                        raw = getattr(ep, 'scores', None)
                        if isinstance(raw, str) and raw:
                            scores = _json.loads(raw)
                        elif isinstance(raw, dict):
                            scores = raw
                    except Exception:
                        scores = None
                    if scores:
                        labels = {'AI and Technology': 'Tech', 'Social Movements and Community Organizing': 'Organizing'}
                        parts = []
                        for k, v in scores.items():
                            try:
                                parts.append(f"{labels.get(k, k.split()[0])}={float(v):.2f}")
                            except Exception:
                                continue
                        setattr(ep, 'score_labels', ', '.join(parts))
                    else:
                        setattr(ep, 'score_labels', '')
                except Exception:
                    setattr(ep, 'feed_title', 'Unknown Feed')
            # Do not auto-correct DB feed_id based on transcript headers here
        except Exception:
            undigested = []

        # Failed episodes (retry candidates)
        failed_eps = []
        try:
            failed_eps = episode_repo.get_by_status('failed')[:10]
        except Exception:
            pass

        log_summary = None
        if latest_log:
            log_summary = _parse_log_summary(latest_log)

        # System health
        def get_system_health():
            items = { 'tools': [], 'apis': [] }
            # ffmpeg
            ff = shutil.which('ffmpeg')
            items['tools'].append({ 'name': 'ffmpeg', 'ok': bool(ff), 'detail': ff or 'not found in PATH' })
            # gh CLI and auth
            gh_path = shutil.which('gh')
            gh_ok = False
            gh_detail = gh_path or 'not found'
            if gh_path:
                try:
                    import subprocess
                    r = subprocess.run(['gh','auth','status'], capture_output=True, text=True)
                    gh_ok = (r.returncode == 0)
                    if gh_ok:
                        gh_detail = 'authenticated via gh'
                    else:
                        gh_detail = (r.stderr or r.stdout).strip() or 'gh installed, auth not detected'
                except Exception as e:
                    gh_detail = f'gh error: {e}'
            items['tools'].append({ 'name': 'GitHub CLI (gh)', 'ok': gh_ok, 'detail': gh_detail })
            # parakeet-mlx
            try:
                import parakeet_mlx  # noqa: F401
                items['tools'].append({ 'name': 'parakeet-mlx', 'ok': True, 'detail': 'available' })
            except Exception as e:
                items['tools'].append({ 'name': 'parakeet-mlx', 'ok': False, 'detail': str(e) })
            # API keys/auth
            items['apis'].append({ 'name': 'OPENAI_API_KEY', 'ok': bool(os.getenv('OPENAI_API_KEY')), 'detail': 'present' if os.getenv('OPENAI_API_KEY') else 'missing' })
            items['apis'].append({ 'name': 'ELEVENLABS_API_KEY', 'ok': bool(os.getenv('ELEVENLABS_API_KEY')), 'detail': 'present' if os.getenv('ELEVENLABS_API_KEY') else 'missing' })
            gh_token_ok = bool(os.getenv('GITHUB_TOKEN'))
            items['apis'].append({ 'name': 'GitHub Auth', 'ok': gh_token_ok or gh_ok, 'detail': 'GITHUB_TOKEN present' if gh_token_ok else ('gh authenticated' if gh_ok else 'no token/gh auth') })
            items['apis'].append({ 'name': 'GITHUB_REPOSITORY', 'ok': bool(os.getenv('GITHUB_REPOSITORY')), 'detail': os.getenv('GITHUB_REPOSITORY') or 'missing' })
            return items

        health = get_system_health()
        # Auto-start stream if requested
        from flask import request as _req
        autostream = bool(_req.args.get('autostream'))
        stream_file = _req.args.get('stream_file')

        return render_template('dashboard.html', settings=settings, last_run=last_run,
                               rss_items=rss_items, undigested=undigested, failed_eps=failed_eps,
                               log_summary=log_summary, health=health, autostream=autostream, stream_file=stream_file)

    @app.route('/settings', methods=['GET', 'POST'])
    def settings():
        current = {
            'content_filtering': web_config.get_category('content_filtering'),
            'audio_processing': web_config.get_category('audio_processing'),
            'pipeline': web_config.get_category('pipeline'),
        }
        if request.method == 'POST':
            errors = []
            # Collect posted values
            try:
                th = float(request.form.get('score_threshold', current['content_filtering'].get('score_threshold', 0.65)))
                web_config.set_setting('content_filtering', 'score_threshold', th)
            except Exception as e:
                errors.append(f'score_threshold: {e}')
            try:
                max_eps = int(request.form.get('max_episodes_per_digest', current['content_filtering'].get('max_episodes_per_digest', 5)))
                web_config.set_setting('content_filtering', 'max_episodes_per_digest', max_eps)
            except Exception as e:
                errors.append(f'max_episodes_per_digest: {e}')
            try:
                cmin = int(request.form.get('chunk_duration_minutes', current['audio_processing'].get('chunk_duration_minutes', 10)))
                web_config.set_setting('audio_processing', 'chunk_duration_minutes', cmin)
            except Exception as e:
                errors.append(f'chunk_duration_minutes: {e}')
            try:
                all_chunks = True if request.form.get('transcribe_all_chunks') == 'on' else False
                web_config.set_setting('audio_processing', 'transcribe_all_chunks', all_chunks)
            except Exception as e:
                errors.append(f'transcribe_all_chunks: {e}')
            try:
                max_chunks = int(request.form.get('max_chunks_per_episode', current['audio_processing'].get('max_chunks_per_episode', 3)))
                web_config.set_setting('audio_processing', 'max_chunks_per_episode', max_chunks)
            except Exception as e:
                errors.append(f'max_chunks_per_episode: {e}')
            try:
                max_run_eps = int(request.form.get('max_episodes_per_run', current['pipeline'].get('max_episodes_per_run', 3)))
                web_config.set_setting('pipeline', 'max_episodes_per_run', max_run_eps)
            except Exception as e:
                errors.append(f'max_episodes_per_run: {e}')
            if errors:
                for msg in errors:
                    flash(msg, 'error')
            else:
                flash('Settings saved', 'success')
            return redirect(url_for('settings'))
        return render_template('settings.html', current=current, defaults=DEFAULTS)

    @app.get('/maintenance')
    def maintenance_page():
        return render_template('maintenance.html')

    # --------------
    # Pipeline Actions
    # --------------
    import subprocess, shlex

    @app.post('/pipeline/run')
    def pipeline_run():
        kind = request.form.get('kind', 'publishing')
        phase = request.form.get('phase')
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        # Build command safely without relying on shell tools like `timeout`
        if kind == 'full':
            log_path = PROJECT_ROOT / f'pipeline_run_{ts}.log'
            # Pre-create the log file to ensure SSE can attach immediately
            try:
                log_path.touch(exist_ok=True)
            except Exception:
                pass
            cmd_args = [sys.executable, 'run_full_pipeline.py', '--log', log_path.name]
            if phase:
                cmd_args.extend(['--phase', phase])
        else:
            # Publishing: do not create a separate log file; stream main console output only
            log_path = None
            cmd_args = [sys.executable, 'run_publishing_pipeline.py', '-v']
        try:
            extra_env = os.environ.copy()
            extra_env.setdefault('PYTHONUNBUFFERED', '1')
            if log_path is not None:
                # Capture stdout/stderr into the log file so early import errors are visible
                with open(log_path, 'a', encoding='utf-8', errors='ignore') as fh:
                    fh.write(f"[web-ui] Launching: {' '.join(cmd_args)}\n")
                    fh.flush()
                    subprocess.Popen(cmd_args, cwd=str(PROJECT_ROOT), stdout=fh, stderr=fh, env=extra_env)
            else:
                subprocess.Popen(cmd_args, cwd=str(PROJECT_ROOT), env=extra_env)
            if log_path:
                flash(f'Started {kind} pipeline. Logging to {log_path.name}', 'success')
            else:
                flash(f'Started {kind} pipeline.', 'success')
        except Exception as e:
            flash(f'Failed to start pipeline: {e}', 'error')
        # Redirect with autostream to auto-start live log view
        if log_path is not None:
            return redirect(url_for('dashboard', autostream=1, stream_file=log_path.name))
        return redirect(url_for('dashboard', autostream=1))

    @app.post('/episodes/<int:episode_id>/retry')
    def episode_retry(episode_id: int):
        try:
            ep = episode_repo.get_by_id(episode_id)
            if not ep:
                flash('Episode not found', 'error')
            else:
                episode_repo.update_status(ep.episode_guid, 'pending')
                flash('Episode marked for retry', 'success')
        except Exception as e:
            flash(f'Failed to retry episode: {e}', 'error')
        return redirect(url_for('dashboard'))

    @app.post('/maintenance/repair_digested')
    def repair_digested():
        def worker(log_path: Path):
            repaired = moved = errors = 0
            try:
                from database.models import get_database_manager
                dbm = get_database_manager()
                rows = dbm.execute_query("SELECT id, topic, episode_ids FROM digests")
                import json as _json
                all_ids = set()
                for r in rows:
                    ids = _json.loads(r['episode_ids']) if r['episode_ids'] else []
                    all_ids.update(ids)
                with open(log_path, 'a', encoding='utf-8') as fh:
                    fh.write(f"Found {len(all_ids)} episodes across digests to repair\n")
                    for eid in all_ids:
                        ep = episode_repo.get_by_id(eid)
                        if not ep:
                            continue
                        try:
                            if getattr(ep, 'status', '') != 'digested':
                                episode_repo.update_status_by_id(eid, 'digested')
                                repaired += 1
                                fh.write(f"  status→digested: episode {eid}\n")
                            tpath = getattr(ep, 'transcript_path', None)
                            if tpath and os.path.exists(tpath):
                                from pathlib import Path as _P
                                p = _P(tpath)
                                dig_dir = p.parent / 'digested'
                                dig_dir.mkdir(exist_ok=True)
                                new_p = dig_dir / p.name
                                if not new_p.exists():
                                    p.replace(new_p)
                                episode_repo.update_transcript_path(eid, str(new_p))
                                moved += 1
                                fh.write(f"  moved transcript→{new_p}\n")
                            fh.flush()
                    fh.write(f"Done. repaired={repaired}, moved={moved}, errors={errors}\n")
            except Exception as e:
                with open(log_path, 'a', encoding='utf-8') as fh:
                    fh.write(f"Error: {e}\n")
        log_path = _start_maintenance_task('repair_digested', worker)
        return redirect(url_for('dashboard', autostream=1, stream_file=log_path.name))

    @app.post('/maintenance/repair_feeds')
    def repair_feeds():
        def worker(log_path: Path):
            repaired = checked = skipped = errors = 0
            header_corrections = {
                'Kultural': 'The Malcolm Effect',
                'Anchor': None,
                'Anchor Feed': None,
            }
            try:
                from database.models import get_database_manager
                dbm = get_database_manager()
                rows = dbm.execute_query(
                    """
                    SELECT e.id AS e_id, e.transcript_path, f.title AS db_feed_title
                    FROM episodes e JOIN feeds f ON e.feed_id = f.id
                    WHERE e.transcript_path IS NOT NULL
                    """
                )
                import os
                with open(log_path, 'a', encoding='utf-8') as fh:
                    for r in rows:
                        checked += 1
                        tpath = r['transcript_path']
                        if not tpath or not os.path.exists(tpath):
                            skipped += 1
                            continue
                        header_title = None
                        try:
                            with open(tpath, 'r', encoding='utf-8', errors='ignore') as th:
                                for _ in range(12):
                                    line = th.readline()
                                    if not line:
                                        break
                                    if 'Feed:' in line:
                                        parts = line.split(':', 1)
                                        if len(parts) == 2:
                                            header_title = parts[1].strip()
                                            break
                        except Exception:
                            errors += 1
                            continue
                        if not header_title:
                            skipped += 1
                            continue
                        if header_title in header_corrections:
                            corrected = header_corrections[header_title]
                            if corrected is None:
                                skipped += 1
                                continue
                            header_title = corrected
                        if header_title == r['db_feed_title']:
                            continue
                        f = feed_repo.get_by_title(header_title)
                        if f and f.id:
                            try:
                                episode_repo.update_feed_id(r['e_id'], f.id)
                                repaired += 1
                                fh.write(f"episode {r['e_id']}: {r['db_feed_title']} -> {f.title}\n")
                                fh.flush()
                            except Exception as ex:
                                errors += 1
                                fh.write(f"episode {r['e_id']}: failed to update: {ex}\n")
                                fh.flush()
                        else:
                            skipped += 1
                    fh.write(f"Done. repaired={repaired}, checked={checked}, skipped={skipped}, errors={errors}\n")
            except Exception as e:
                with open(log_path, 'a', encoding='utf-8') as fh:
                    fh.write(f"Error: {e}\n")
        log_path = _start_maintenance_task('repair_feeds', worker)
        return redirect(url_for('dashboard', autostream=1, stream_file=log_path.name))
    # Episodes admin page
    @app.route('/episodes', methods=['GET'])
    def episodes_admin():
        q = (request.args.get('q') or '').strip()
        status = (request.args.get('status') or '').strip()
        sort_by = (request.args.get('sort_by') or '').strip() or 'scored_at'
        sort_dir = (request.args.get('sort_dir') or '').strip() or 'desc'
        # Map sort keys
        sort_map = {
            'title': 'e.title',
            'feed': 'f.title',
            'published': 'e.published_date',
            'status': 'e.status',
            'scored_at': 'e.scored_at'
        }
        order_col = sort_map.get(sort_by, 'e.scored_at')
        order_dir = 'ASC' if sort_dir.lower() == 'asc' else 'DESC'
        try:
            from database.models import get_database_manager
            dbm = get_database_manager()
            wheres = []
            params: list = []
            if q:
                wheres.append("(e.title LIKE ? OR f.title LIKE ?)")
                params.extend([f"%{q}%", f"%{q}%"])
            if status:
                wheres.append("e.status = ?")
                params.append(status)
            where_clause = (" WHERE " + " AND ".join(wheres)) if wheres else ""
            sql = (
                "SELECT e.*, f.title AS feed_title FROM episodes e "
                "JOIN feeds f ON e.feed_id = f.id "
                + where_clause +
                f" ORDER BY {order_col} {order_dir} LIMIT 100"
            )
            rows = dbm.execute_query(sql, tuple(params))
            # Build digest inclusion map (recent 14 days)
            digests = dbm.execute_query("SELECT id, topic, digest_date, episode_ids FROM digests WHERE digest_date >= date('now','-14 days')")
            incl_map = {}
            import json as _json
            for d in digests:
                ids = _json.loads(d['episode_ids']) if d['episode_ids'] else []
                for eid in ids:
                    incl_map.setdefault(eid, []).append({ 'topic': d['topic'], 'date': d['digest_date'] })
            items = []
            for r in rows:
                ep = dict(r)
                ep['included'] = incl_map.get(r['id'], [])
                # Display the DB feed title only
                ep['feed_title_display'] = r['feed_title']
                # Compact scores string
                try:
                    scores = _json.loads(r['scores']) if r['scores'] else {}
                except Exception:
                    scores = {}
                labels = {'AI and Technology': 'Tech', 'Social Movements and Community Organizing': 'Organizing'}
                score_labels = ', '.join(f"{labels.get(k, k.split()[0])}={float(v):.2f}" for k,v in scores.items()) if scores else ''
                ep['score_labels'] = score_labels
                items.append(ep)
            return render_template('episodes.html', q=q, status=status, sort_by=sort_by, sort_dir=sort_dir, items=items)
        except Exception as e:
            flash(f'Failed to load episodes: {e}', 'error')
            return render_template('episodes.html', q=q, status=status, sort_by=sort_by, sort_dir=sort_dir, items=[])

    @app.post('/episodes/<int:episode_id>/undigest')
    def episode_undigest(episode_id: int):
        try:
            ep = episode_repo.get_by_id(episode_id)
            if not ep:
                flash('Episode not found', 'error')
                return redirect(url_for('episodes_admin'))
            # Move transcript back if in digested/
            tpath = getattr(ep, 'transcript_path', None)
            if tpath and os.path.exists(tpath):
                p = Path(tpath)
                if p.parent.name == 'digested':
                    target = p.parent.parent / p.name
                    if not target.exists():
                        p.replace(target)
                    episode_repo.update_transcript_path(ep.id, str(target))
            # Reset status to scored
            episode_repo.update_status_by_id(ep.id, 'scored')
            flash('Episode reset to scored and transcript restored (if needed)', 'success')
        except Exception as e:
            flash(f'Failed to undigest episode: {e}', 'error')
        return redirect(url_for('episodes_admin'))
    

    # --------------
    # Logs
    # --------------
    @app.get('/logs/latest')
    def logs_latest():
        latest = _find_latest_log()
        if not latest:
            return 'No logs found', 404
        try:
            text = latest.read_text(errors='ignore')
            tail = '\n'.join(text.splitlines()[-200:])
            return f"<pre style='white-space: pre-wrap'>{tail}</pre>"
        except Exception as e:
            return f'Failed to read log: {e}', 500

    @app.get('/logs/stream')
    def logs_stream():
        from flask import request as _req
        latest = None
        file_arg = _req.args.get('file')
        if file_arg:
            from pathlib import Path as _P
            base = _P(file_arg).name
            if base.startswith(('pipeline_run_', 'publishing_pipeline_')) and base.endswith('.log'):
                candidate = PROJECT_ROOT / base
                if candidate.exists():
                    latest = candidate
        if latest is None:
            latest = _find_latest_log()
            if not latest or not latest.exists():
                return 'No logs found', 404

        def generate(path: Path):
            try:
                with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                    # Emit an initial tail so users see immediate context even if the process exited fast
                    try:
                        content = f.read()
                        tail_lines = content.splitlines()[-200:]
                        for tl in tail_lines:
                            yield f"data: {tl}\n\n"
                    except Exception:
                        pass
                    # Now continue streaming new lines from the end
                    f.seek(0, 2)  # end
                    while True:
                        line = f.readline()
                        if not line:
                            time.sleep(0.5)
                            continue
                        yield f"data: {line.rstrip()}\n\n"
            except Exception as e:
                yield f"data: [stream ended: {e}]\n\n"

        from flask import Response
        return Response(generate(latest), mimetype='text/event-stream')

    @app.post('/maintenance/repair_publishing')
    def repair_publishing():
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        log_path = PROJECT_ROOT / f'maintenance_repair_publishing_{ts}.log'
        try:
            with open(log_path, 'a', encoding='utf-8') as fh:
                fh.write(f"[web-ui] Launching: {sys.executable} run_publishing_pipeline.py -v\n")
                fh.flush()
                extra_env = os.environ.copy()
                extra_env.setdefault('PYTHONUNBUFFERED', '1')
                import subprocess
                subprocess.Popen([sys.executable, 'run_publishing_pipeline.py', '-v'], cwd=str(PROJECT_ROOT), stdout=fh, stderr=fh, env=extra_env)
        except Exception as e:
            try:
                with open(log_path, 'a', encoding='utf-8') as fh:
                    fh.write(f"[web-ui] Failed to launch: {e}\n")
            except Exception:
                pass
        return redirect(url_for('dashboard', autostream=1, stream_file=log_path.name))

    # -----------------
    # Feeds Management
    # -----------------
    @app.route('/feeds', methods=['GET', 'POST'])
    def feeds():
        if request.method == 'POST':
            action = request.form.get('action')
            if action == 'add':
                feed_url = (request.form.get('feed_url') or '').strip()
                title = (request.form.get('title') or '').strip()
                if not is_valid_feed_url(feed_url):
                    flash('Invalid URL. Must start with http(s):// or file://', 'error')
                    return redirect(url_for('feeds'))
                # Duplicate guard
                try:
                    existing = feed_repo.get_by_url(feed_url)
                    if existing:
                        flash('Feed already exists', 'error')
                        return redirect(url_for('feeds'))
                except Exception:
                    pass
                # Try to parse to auto-fill title
                parsed_title = None
                parse_error = None
                if feedparser:
                    try:
                        content = None
                        if feed_url.lower().startswith('file://'):
                            from urllib.parse import urlparse, unquote
                            p = urlparse(feed_url)
                            path = unquote(p.path)
                            with open(path, 'rb') as fh:
                                content = fh.read()
                        elif requests is not None:
                            resp = requests.get(feed_url, timeout=10, verify=True, headers={
                                'User-Agent': 'PodcastDigest/1.0 (+https://github.com/McSchnizzle/podscrape2)'
                            })
                            resp.raise_for_status()
                            content = resp.content
                        if content is not None:
                            parsed = feedparser.parse(content)
                        else:
                            parsed = feedparser.parse(feed_url)
                        parsed_title = (getattr(parsed, 'feed', None) or {}).get('title') if hasattr(parsed, 'feed') else None
                    except Exception as e:
                        parse_error = str(e)
                # Fall back to provided title
                final_title = (parsed_title or title or '').strip()
                if not final_title:
                    flash('Could not determine feed title. Provide a title or a valid feed URL.', 'error')
                    return redirect(url_for('feeds'))
                # Create via repository
                try:
                    feed_id = feed_repo.create(
                        PodcastFeed(
                            feed_url=feed_url,
                            title=final_title,
                            description=None,
                            active=True,
                        )
                    )
                    flash(f'Feed added: {final_title}', 'success')
                except Exception as e:
                    flash(f'Failed to add feed: {e}', 'error')
            return redirect(url_for('feeds'))

        feeds = feed_repo.get_all()
        yt = []
        rss = []
        for f in feeds:
            url = (f.feed_url or '').lower()
            if 'youtube.com' in url or 'youtu.be' in url:
                yt.append(f)
            else:
                rss.append(f)
        # Attach latest episode info to RSS feeds
        try:
            for f in rss:
                try:
                    eps = episode_repo.get_by_feed_id(f.id, limit=1)
                    if eps:
                        le = eps[0]
                        setattr(f, 'latest_episode_title', le.title)
                        setattr(f, 'latest_episode_date', le.published_date.strftime('%Y-%m-%d'))
                    else:
                        setattr(f, 'latest_episode_title', None)
                        setattr(f, 'latest_episode_date', None)
                except Exception:
                    setattr(f, 'latest_episode_title', None)
                    setattr(f, 'latest_episode_date', None)
        except Exception:
            pass
        return render_template('feeds.html', rss_feeds=rss, yt_feeds=yt)

    @app.post('/feeds/<int:feed_id>/toggle')
    def feed_toggle(feed_id: int):
        try:
            feed = feed_repo.get_by_id(feed_id)
            if not feed:
                flash('Feed not found', 'error')
                return redirect(url_for('feeds'))
            new_active = not bool(feed.active)
            feed_repo.set_active(feed_id, new_active)
            flash('Feed activated' if new_active else 'Feed deactivated', 'success')
        except Exception as e:
            flash(f'Failed to toggle feed: {e}', 'error')
        return redirect(url_for('feeds'))

    @app.post('/feeds/<int:feed_id>/delete')
    def feed_delete(feed_id: int):
        # Soft delete: set inactive
        try:
            feed = feed_repo.get_by_id(feed_id)
            if not feed:
                flash('Feed not found', 'error')
            else:
                feed_repo.set_active(feed_id, False)
                flash('Feed deactivated (soft delete)', 'success')
        except Exception as e:
            flash(f'Failed to deactivate feed: {e}', 'error')
        return redirect(url_for('feeds'))

    @app.post('/feeds/<int:feed_id>/check')
    def feed_check(feed_id: int):
        try:
            feed = feed_repo.get_by_id(feed_id)
            if not feed:
                flash('Feed not found', 'error')
                return redirect(url_for('feeds'))
            if not feedparser:
                flash('Feedparser not installed', 'error')
                return redirect(url_for('feeds'))
            # Strict check: verify TLS and ability to reach at least one audio enclosure
            if requests is None:
                flash('Requests library not installed', 'error')
                return redirect(url_for('feeds'))

            # Fetch feed content (https/file schemes supported)
            try:
                content = None
                if feed.feed_url.lower().startswith('file://'):
                    from urllib.parse import urlparse, unquote
                    p = urlparse(feed.feed_url)
                    path = unquote(p.path)
                    with open(path, 'rb') as fh:
                        content = fh.read()
                else:
                    resp = requests.get(feed.feed_url, timeout=12, verify=True, headers={
                        'User-Agent': 'PodcastDigest/1.0 (+https://github.com/McSchnizzle/podscrape2)'
                    })
                    resp.raise_for_status()
                    content = resp.content
                parsed = feedparser.parse(content)
            except Exception as ex:
                feed_repo.increment_failures(feed_id)
                feed_repo.update_last_checked(feed_id)
                flash(f'Check failed: cannot fetch feed: {ex}', 'error')
                return redirect(url_for('feeds'))

            # Extract candidate enclosure URLs (latest few entries)
            entries = list(getattr(parsed, 'entries', []) or [])[:3]
            enclosure_urls = []
            for e in entries:
                urls = []
                if hasattr(e, 'enclosures') and e.enclosures:
                    for enc in e.enclosures:
                        url = enc.get('url') or enc.get('href')
                        if url:
                            urls.append(url)
                # fallback: links rel=enclosure
                if not urls and hasattr(e, 'links'):
                    for ln in e.links:
                        if ln.get('rel') == 'enclosure' and ln.get('href'):
                            urls.append(ln['href'])
                if urls:
                    enclosure_urls.extend(urls)

            if not enclosure_urls:
                feed_repo.increment_failures(feed_id)
                feed_repo.update_last_checked(feed_id)
                flash('Check failed: feed has no audio enclosures in recent items', 'error')
                return redirect(url_for('feeds'))

            def _looks_audio(url: str, ctype: str | None) -> bool:
                if ctype and 'audio' in ctype.lower():
                    return True
                lower = url.lower()
                return any(lower.endswith(ext) for ext in ('.mp3', '.m4a', '.aac', '.ogg', '.wav'))

            # Probe first enclosure that looks like audio
            reachable = False
            last_err = None
            for url in enclosure_urls:
                try:
                    # Prefer HEAD
                    r = requests.head(url, timeout=12, allow_redirects=True, verify=True, headers={'User-Agent': 'PodcastDigest/1.0'})
                    if r.status_code >= 400 or not _looks_audio(url, r.headers.get('Content-Type')):
                        # Some servers don’t support HEAD; try GET small chunk
                        rg = requests.get(url, timeout=12, stream=True, verify=True, headers={'User-Agent': 'PodcastDigest/1.0'})
                        rg.raise_for_status()
                        ctype = rg.headers.get('Content-Type')
                        if not _looks_audio(url, ctype):
                            raise RuntimeError(f'Not audio content-type ({ctype})')
                        # read a tiny amount to confirm stream
                        next(rg.iter_content(chunk_size=1024))
                        reachable = True
                        break
                    else:
                        reachable = True
                        break
                except Exception as exi:
                    last_err = exi
                    continue

            if not reachable:
                feed_repo.increment_failures(feed_id)
                feed_repo.update_last_checked(feed_id)
                msg = f'no audio enclosure reachable; last error: {last_err}' if last_err else 'no audio enclosure reachable'
                flash(f'Check failed: {msg}', 'error')
                return redirect(url_for('feeds'))

            # Success path
            feed_repo.reset_failures(feed_id)
            feed_repo.update_last_checked(feed_id)
            try_title = getattr(parsed.feed, 'title', None) if hasattr(parsed, 'feed') else None
            if try_title and try_title.strip() and try_title.strip() != feed.title:
                feed_repo.db.execute_update("UPDATE feeds SET title=? WHERE id=?", (try_title.strip(), feed_id))
            flash('Feed OK', 'success')
        except Exception as e:
            flash(f'Check failed: {e}', 'error')
        return redirect(url_for('feeds'))

    # --------------
    # Topics Manager
    # --------------
    @app.route('/topics', methods=['GET', 'POST'])
    def topics():
        topics = config_manager.get_all_topics()
        if request.method == 'POST':
            # Build updated topics from form fields
            names = request.form.getlist('name')
            voice_ids = request.form.getlist('voice_id')
            instruction_files = request.form.getlist('instruction_file')
            descriptions = request.form.getlist('description')
            actives = request.form.getlist('active')  # contains indices for checked

            updated = []
            errors = []
            for idx, name in enumerate(names):
                name = (name or '').strip()
                if not name:
                    errors.append(f'Topic at row {idx+1} has empty name')
                    continue
                # Handle file upload override
                upload_key = f'instruction_upload_{idx}'
                uploaded_file = request.files.get(upload_key)
                instr_file = (instruction_files[idx] if idx < len(instruction_files) else '').strip()
                try:
                    saved = save_instruction_upload(uploaded_file)
                    if saved:
                        instr_file = saved
                except Exception as e:
                    errors.append(f'{name}: {e}')
                # Validate instruction_file exists under digest_instructions/
                if instr_file:
                    fpath = digest_instructions_dir() / instr_file
                    if not fpath.exists():
                        errors.append(f'{name}: instruction file not found: {instr_file}')
                topic_obj = {
                    'name': name,
                    'instruction_file': instr_file,
                    'voice_id': (voice_ids[idx] if idx < len(voice_ids) else '').strip(),
                    'active': str(idx) in actives,  # checkbox mapping
                    'description': (descriptions[idx] if idx < len(descriptions) else '').strip(),
                }
                updated.append(topic_obj)

            if errors:
                for msg in errors:
                    flash(msg, 'error')
                # Re-render with original topics to avoid partial updates
                return render_template('topics.html', topics=topics)
            try:
                config_manager.save_topics(updated)
                flash('Topics saved', 'success')
            except Exception as e:
                flash(f'Failed to save topics: {e}', 'error')
            return redirect(url_for('topics'))

        return render_template('topics.html', topics=topics)

    return app


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=5001)
    args = parser.parse_args()
    app = create_app()
    app.run(host='127.0.0.1', port=args.port, debug=True)
