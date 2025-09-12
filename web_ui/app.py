#!/usr/bin/env python3
"""
Lightweight Web UI for managing core settings.
Runs on localhost:5001 (optional), does not affect CLI unless started.
"""

import sys
from pathlib import Path
try:
    from flask import Flask, render_template, request, redirect, url_for, flash
except ImportError as e:
    print("ERROR: Flask is not installed for this Python interpreter.")
    print("Install with one of these:")
    print("  - python3 -m pip install Flask")
    print("  - python3 -m pip install -r requirements.txt")
    print("Recommended: use a venv → python3 -m venv .venv && source .venv/bin/activate && python -m pip install -r requirements.txt")
    raise

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from config.web_config import WebConfigManager, DEFAULTS


def create_app():
    app = Flask(__name__)
    app.secret_key = 'dev-local-only'
    app.config['TEMPLATES_AUTO_RELOAD'] = True

    web_config = WebConfigManager()

    @app.route('/')
    def dashboard():
        settings = {
            'content_filtering': web_config.get_category('content_filtering'),
            'audio_processing': web_config.get_category('audio_processing'),
        }
        return render_template('dashboard.html', settings=settings)

    @app.route('/settings', methods=['GET', 'POST'])
    def settings():
        current = {
            'content_filtering': web_config.get_category('content_filtering'),
            'audio_processing': web_config.get_category('audio_processing'),
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
            if errors:
                for msg in errors:
                    flash(msg, 'error')
            else:
                flash('Settings saved', 'success')
            return redirect(url_for('settings'))
        return render_template('settings.html', current=current, defaults=DEFAULTS)

    return app


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=5001)
    args = parser.parse_args()
    app = create_app()
    app.run(host='127.0.0.1', port=args.port, debug=True)
