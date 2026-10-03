#!/usr/bin/env python3
"""Five-episode script-model bakeoff (Paul, 2026-10-03).

One frozen research packet and one prompt; five authors, each at medium
effort, each verified to be the model that actually answered. No fallback:
Claude authors bypass run_claude (whose quota path answers with Codex) and
GPT authors call `codex exec` directly. Audio is Eleven v4 Text-to-Dialogue
with the selected voices. Publication is by explicit digest id under the
reserved "Bakeoff" topic, which every nightly selector excludes.

Every step is idempotent and records its evidence in RUN_DIR/state.json:

    run_bakeoff.py packet            # freeze the packet (once)
    run_bakeoff.py script N          # write episode N's script (skips if done)
    run_bakeoff.py tts N             # voice it (skips if done)
    run_bakeoff.py publish N         # insert-if-absent + upload + publish
    run_bakeoff.py verify            # check the live RSS for all five
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from datetime import date, datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

LIVE_ENV = os.environ.get("PODCAST_ENV_FILE", "/srv/projects/podcast/.env")
RUN_DIR = Path(os.environ.get("BAKEOFF_RUN_DIR", "/srv/projects/podcast/data/bakeoff/2026-10-03"))
DIGEST_DATE = date(2026, 10, 3)
SOURCE_DIGEST_ID = 776                      # last published AI digest (Oct 2)
PACKET_EPISODES = [1934, 1929, 1938, 1936]  # news roundup, agents risk, business use, Vergecast
PER_EPISODE_CHARS = 20000
EFFORT = "medium"

AUTHORS = {
    1: ("Claude Sonnet 5.5", "claude", "claude-sonnet-5-5"),
    2: ("Claude Opus 5.5", "claude", "claude-opus-5-5"),
    3: ("GPT-6.1-Sol", "codex", "gpt-6.1-sol"),
    4: ("GPT-6-Astra", "codex", "gpt-6-astra"),
    5: ("GPT-5.6-Terra", "codex", "gpt-5.6-terra"),
}
VOICES = {
    "speaker_1": {"name": "Alexis", "voice_id": "ojFyGQgYMiSn66RY5Wyk"},
    "speaker_2": {"name": "Brandon", "voice_id": "VlUmeC1Uzj3NnwiVR9K9"},
}
TTS_MODEL = "eleven_v4"
ALLOWED_TAGS = {"laughs", "laughs harder", "sighs", "exhales", "whispers", "sarcastic",
                "curious", "excited", "mischievously", "pause", "long pause"}
MIN_CHARS, MAX_CHARS = 3800, 5500


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _state() -> dict:
    p = RUN_DIR / "state.json"
    return json.loads(p.read_text()) if p.exists() else {}


def _save(state: dict) -> None:
    """Merge this process's packet/episode records into state.json under a
    lock, so episodes run in parallel never overwrite each other."""
    import fcntl
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    with open(RUN_DIR / "state.lock", "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        current = _state()
        if state.get("packet"):
            current["packet"] = state["packet"]
        current.setdefault("episodes", {}).update(state.get("episodes", {}))
        tmp = RUN_DIR / f"state.json.{os.getpid()}.tmp"
        tmp.write_text(json.dumps(current, indent=2, default=str))
        tmp.replace(RUN_DIR / "state.json")


def _env() -> None:
    from dotenv import load_dotenv
    load_dotenv(LIVE_ENV)


# --------------------------------------------------------------------------
# Packet and prompt
# --------------------------------------------------------------------------

def cmd_packet(_args) -> None:
    state = _state()
    if state.get("packet"):
        print(f"packet exists: sha256 {state['packet']['sha256']}")
        return
    _env()
    from sqlalchemy import text
    from src.database.models import get_database_manager
    s = get_database_manager().get_session()
    try:
        parts = []
        for eid in PACKET_EPISODES:
            r = s.execute(text(
                "select e.id, e.title, f.title, e.published_date, e.transcript_content "
                "from episodes e left join feeds f on f.id = e.feed_id where e.id = :i"), {"i": eid}).one()
            body = (r[4] or "")[:PER_EPISODE_CHARS]
            parts.append(f"### Episode: \"{r[1]}\" ({r[2]}, published {r[3]:%B %d, %Y})\n\n{body}\n")
    finally:
        s.close()
    packet = "\n".join(parts)
    (RUN_DIR).mkdir(parents=True, exist_ok=True)
    (RUN_DIR / "packet.md").write_text(packet)
    state["packet"] = {"source_digest_id": SOURCE_DIGEST_ID, "episodes": PACKET_EPISODES,
                       "per_episode_chars": PER_EPISODE_CHARS, "chars": len(packet),
                       "sha256": _sha(packet)}
    _save(state)
    print(f"packet: {len(packet):,} chars, sha256 {state['packet']['sha256']}")


def build_prompt() -> str:
    from src.generation.anti_ai_rules import compact_banned_list
    template = (REPO / "scripts" / "bakeoff" / "prompt.md").read_text()
    packet = (RUN_DIR / "packet.md").read_text()
    return template.replace("{BANNED_LIST}", compact_banned_list()).replace("{PACKET}", packet)


def validate_script(script: str) -> dict:
    lines = [l for l in script.splitlines() if l.strip()]
    bad = [l[:60] for l in lines if not re.match(r"^SPEAKER_[12]: \S", l)]
    tags = re.findall(r"\[([a-zA-Z ]+)\]", script)
    turns = len(lines)
    tagged = sum(1 for l in lines if re.search(r"\[[a-zA-Z ]+\]", l))
    return {
        "chars": len(script), "turns": turns, "tags": len(tags),
        "tag_set": sorted(set(t.lower() for t in tags)),
        "unknown_tags": sorted(set(t.lower() for t in tags) - ALLOWED_TAGS),
        "tagged_turn_share": round(tagged / turns, 2) if turns else 0,
        "non_dialogue_lines": bad, "angle_markup": "<" in script,
        "in_length_bounds": MIN_CHARS <= len(script) <= MAX_CHARS,
    }


# --------------------------------------------------------------------------
# Authors: direct calls, verified model identity, no fallback
# --------------------------------------------------------------------------

def run_claude_author(model_id: str, prompt: str) -> dict:
    claude = os.path.expanduser("~/.local/bin/claude")
    env = {k: v for k, v in os.environ.items() if k not in ("ANTHROPIC_API_KEY", "CLAUDECODE")}
    started = time.monotonic()
    r = subprocess.run(
        [claude, "-p", "--model", model_id, "--effort", EFFORT, "--tools", "",
         "--no-session-persistence", "--output-format", "json"],
        input=prompt, capture_output=True, text=True, timeout=1800, env=env)
    took = round(time.monotonic() - started, 1)
    try:
        env_json = json.loads(r.stdout)
    except ValueError:
        raise SystemExit(f"{model_id}: no JSON envelope (exit {r.returncode}): "
                         f"{(r.stderr or r.stdout)[:300]}")
    if r.returncode != 0 or env_json.get("is_error"):
        raise SystemExit(f"{model_id}: refused or failed: {str(env_json.get('result'))[:300]}")
    used = sorted((env_json.get("modelUsage") or {}).keys())
    return {"text": (env_json.get("result") or "").strip(), "observed_models": used,
            "verified": used == [model_id], "seconds": took,
            "session_id": env_json.get("session_id"), "usage": env_json.get("usage")}


def _codex_session_context(thread_id: str) -> dict:
    root = Path.home() / ".codex" / "sessions"
    for path in sorted(root.rglob(f"*{thread_id}*.jsonl")):
        for line in path.read_text().splitlines():
            try:
                ev = json.loads(line)
            except ValueError:
                continue
            payload = ev.get("payload") or {}
            if ev.get("type") == "turn_context" or "effort" in payload and "model" in payload:
                return {"file": str(path), "model": payload.get("model"),
                        "effort": payload.get("effort") or payload.get("reasoning_effort")}
    return {}


def run_codex_author(model_id: str, prompt: str) -> dict:
    codex = os.path.expanduser("~/.local/bin/codex")
    with tempfile.TemporaryDirectory(prefix="bakeoff-codex-") as d:
        out = Path(d) / "answer.txt"
        argv = [codex, "exec", "--ignore-user-config", "--ignore-rules", "--skip-git-repo-check",
                "--sandbox", "read-only", "--cd", d, "--json", "--model", model_id,
                "-c", f'model_reasoning_effort="{EFFORT}"', "-c", 'web_search="disabled"']
        for feature in ("shell_tool", "unified_exec", "apps", "browser_use", "browser_use_external",
                        "browser_use_full_cdp_access", "computer_use", "image_generation",
                        "multi_agent", "multi_agent_v2", "hooks", "code_mode", "code_mode_host",
                        "view_image"):
            argv += ["--disable", feature]
        argv += ["--enable", "skip_host_skill_discovery", "--output-last-message", str(out), "-"]
        started = time.monotonic()
        r = subprocess.run(argv, input=prompt, capture_output=True, text=True, timeout=1800)
        took = round(time.monotonic() - started, 1)
        thread_id, completed, usage = None, False, {}
        for line in r.stdout.splitlines():
            try:
                ev = json.loads(line)
            except ValueError:
                continue
            if ev.get("type") == "thread.started":
                thread_id = ev.get("thread_id")
            if ev.get("type") in ("turn.failed", "error"):
                raise SystemExit(f"{model_id}: {json.dumps(ev)[:300]}")
            if ev.get("type") == "turn.completed":
                completed, usage = True, ev.get("usage") or {}
            item = ev.get("item") or {}
            if isinstance(item, dict) and item.get("type") in (
                    "command_execution", "mcp_tool_call", "web_search", "file_change"):
                raise SystemExit(f"{model_id}: unexpected tool use")
        if r.returncode != 0 or not completed or not out.exists():
            raise SystemExit(f"{model_id}: failed (exit {r.returncode}): {r.stderr[-300:]}")
        text_out = out.read_text().strip()
    ctx = _codex_session_context(thread_id) if thread_id else {}
    return {"text": text_out, "observed_models": [ctx.get("model")] if ctx.get("model") else [],
            "observed_effort": ctx.get("effort"), "session_file": ctx.get("file"),
            "verified": ctx.get("model") == model_id and ctx.get("effort") == EFFORT,
            "seconds": took, "session_id": thread_id, "usage": usage}


def cmd_script(args) -> None:
    n = args.n
    state = _state()
    eps = state.setdefault("episodes", {})
    if eps.get(str(n), {}).get("script_sha256"):
        print(f"episode {n}: script exists")
        return
    _env()
    label, kind, model_id = AUTHORS[n]
    prompt = build_prompt()
    res = (run_claude_author if kind == "claude" else run_codex_author)(model_id, prompt)
    script = res.pop("text")
    path = RUN_DIR / f"script_{n}.txt"
    path.write_text(script)
    rec = {"author": label, "requested_model": model_id, "effort": EFFORT,
           "prompt_sha256": _sha(prompt), "packet_sha256": state["packet"]["sha256"],
           "script_sha256": _sha(script), "script_path": str(path),
           "validation": validate_script(script), **res}
    _save({"episodes": {str(n): rec}})
    print(json.dumps({k: rec[k] for k in ("author", "requested_model", "observed_models",
                                          "verified", "seconds", "validation")}, default=str))
    if not rec["verified"]:
        raise SystemExit(f"episode {n}: observed model does not match {model_id}; not usable")


# --------------------------------------------------------------------------
# Audio
# --------------------------------------------------------------------------

def _credits() -> dict:
    import urllib.request
    req = urllib.request.Request("https://api.elevenlabs.io/v1/user/subscription",
                                 headers={"xi-api-key": os.environ["ELEVENLABS_API_KEY"]})
    s = json.load(urllib.request.urlopen(req, timeout=30))
    return {"used": s["character_count"], "limit": s["character_limit"]}


def _duration(path: Path) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                          "-of", "default=nw=1:nk=1", str(path)],
                         capture_output=True, text=True, stdin=subprocess.DEVNULL, check=True)
    return float(out.stdout.strip())


def cmd_tts(args) -> None:
    n = args.n
    state = _state()
    rec = state["episodes"][str(n)]
    if rec.get("mp3_path") and Path(rec["mp3_path"]).exists():
        print(f"episode {n}: audio exists")
        return
    if not rec.get("verified"):
        raise SystemExit(f"episode {n}: script not verified; refusing to voice it")
    _env()
    script = Path(rec["script_path"]).read_text()
    before = _credits()
    budget_left = before["limit"] - before["used"]
    if len(script) * 2 > budget_left:                     # generous margin, never exceed
        raise SystemExit(f"episode {n}: credit headroom {budget_left} too small")
    from src.audio.audio_generator import AudioGenerator
    gen = AudioGenerator()
    gen.audio_dir = RUN_DIR
    meta = gen._generate_chunked_dialogue_audio(
        script_content=script, topic="Bakeoff", voice_config=VOICES,
        dialogue_model=TTS_MODEL, timestamp=f"{DIGEST_DATE:%Y%m%d}_12000{n}")
    after = _credits()
    mp3 = Path(meta.file_path)
    rec.update({"mp3_path": str(mp3), "duration_seconds": round(_duration(mp3), 1),
                "mp3_bytes": mp3.stat().st_size, "tts_model": TTS_MODEL, "voices": VOICES,
                "credits_before": before["used"], "credits_after": after["used"],
                "credits_spent": after["used"] - before["used"]})
    _save({"episodes": {str(n): rec}})
    print(json.dumps({k: rec[k] for k in ("mp3_path", "duration_seconds", "credits_spent",
                                          "credits_after")}))


def cmd_check(args) -> None:
    """Whisper the audio back and compare it to the script (quality check)."""
    import difflib
    import whisper
    state = _state()
    rec = state["episodes"][str(args.n)]
    model = whisper.load_model("base.en")
    heard = model.transcribe(rec["mp3_path"], language="en", fp16=False)["text"]
    script = Path(rec["script_path"]).read_text()
    spoken = re.sub(r"SPEAKER_[12]:|\[[a-zA-Z ]+\]", " ", script)
    norm = lambda t: re.sub(r"[^a-z0-9 ]", " ", t.lower()).split()
    ratio = difflib.SequenceMatcher(None, norm(spoken), norm(heard), autojunk=False).ratio()
    tag_words = [t for t in ALLOWED_TAGS if re.search(rf"\b{t}\b", heard.lower())]
    rec["quality"] = {"whisper_match_ratio": round(ratio, 3), "tag_words_heard": tag_words,
                      "heard_chars": len(heard)}
    (RUN_DIR / f"heard_{args.n}.txt").write_text(heard)
    _save({"episodes": {str(args.n): rec}})
    print(json.dumps(rec["quality"]))


# --------------------------------------------------------------------------
# Publication: exactly one row per episode, by explicit id
# --------------------------------------------------------------------------

def cmd_publish(args) -> None:
    n = args.n
    state = _state()
    rec = state["episodes"][str(n)]
    if not (rec.get("verified") and rec.get("mp3_path")):
        raise SystemExit(f"episode {n}: not verified or not voiced")
    _env()
    from sqlalchemy.dialects.postgresql import insert
    from src.database.models import get_database_manager, get_digest_repo
    from src.database.sqlalchemy_models import Digest
    from src.generation.script_attribution import AuthorshipTracker, append_attribution
    from src.publishing.bakeoff import BAKEOFF_TOPIC
    from src.publishing.github_publisher import create_github_publisher

    label, kind, model_id = AUTHORS[n]
    script = Path(rec["script_path"]).read_text()
    if kind == "codex":            # the house marker: Codex-written script text
        t = AuthorshipTracker()
        t.start(script, "draft", ("codex", model_id))
        script = append_attribution(script, t)
    titles = ", ".join(f'"{x}"' for x in _packet_titles())
    stamp = datetime(DIGEST_DATE.year, DIGEST_DATE.month, DIGEST_DATE.day, 12, 0, n)
    title = f"Bakeoff {n} of 5: written by {label}"
    summary = (f"Script-model bakeoff, episode {n} of 5. Script written by {label} "
               f"({model_id}, {EFFORT} effort). Voiced by ElevenLabs v4 (Alexis and Brandon). "
               f"All five episodes share one research packet: {titles}.")
    values = dict(topic=BAKEOFF_TOPIC, digest_date=DIGEST_DATE, digest_timestamp=stamp,
                  generated_at=stamp, script_content=script, script_word_count=len(script.split()),
                  episode_count=len(PACKET_EPISODES), mp3_path=rec["mp3_path"],
                  mp3_duration_seconds=int(round(rec["duration_seconds"])),
                  mp3_title=title, mp3_summary=summary, status="audio_generated")
    db = get_database_manager()
    with db.get_session() as s:
        row_id = s.execute(insert(Digest).values(**values)
                           .on_conflict_do_nothing(constraint="uq_digests_topic_date_timestamp")
                           .returning(Digest.id)).scalar()
        s.commit()
        if row_id is None:
            row_id = s.query(Digest.id).filter_by(topic=BAKEOFF_TOPIC, digest_date=DIGEST_DATE,
                                                  digest_timestamp=stamp).scalar()
        existing = s.get(Digest, row_id)
        github_url = existing.github_url
    rec["digest_id"] = row_id
    if not github_url:
        release = create_github_publisher().create_daily_release(DIGEST_DATE, [rec["mp3_path"]])
        names = {a.get("name") for a in (release.assets or [])}
        github_url = release.html_url
        repo = get_digest_repo()
        repo.update_digest(row_id, {"github_url": github_url})
        repo.update_published(digest_id=row_id, github_url=github_url)
        rec["asset_listed"] = Path(rec["mp3_path"]).name in names
    rec.update({"github_url": github_url, "title": title})
    _save({"episodes": {str(n): rec}})
    print(json.dumps({"n": n, "digest_id": row_id, "title": title, "github_url": github_url}))


def _packet_titles():
    _env()
    from sqlalchemy import text
    from src.database.models import get_database_manager
    s = get_database_manager().get_session()
    try:
        return [s.execute(text("select title from episodes where id = :i"), {"i": i}).scalar()
                for i in PACKET_EPISODES]
    finally:
        s.close()


def cmd_verify(_args) -> None:
    import urllib.request
    import xml.etree.ElementTree as ET
    state = _state()
    feed = urllib.request.urlopen("http://localhost:3050/daily-digest.xml", timeout=30).read()
    items = ET.fromstring(feed).findall("./channel/item")
    found = {}
    for it in items:
        t = it.findtext("title") or ""
        enc = it.find("enclosure")
        if t.startswith("Bakeoff "):
            found[t] = enc.get("url") if enc is not None else None
    report = []
    for n, rec in sorted(state.get("episodes", {}).items()):
        title = rec.get("title")
        url = found.get(title)
        ok_head = None
        if url:
            try:
                req = urllib.request.Request(url, method="HEAD")
                ok_head = urllib.request.urlopen(req, timeout=30).status
            except Exception as e:
                ok_head = f"error {e}"
        report.append({"n": n, "title": title, "in_feed": bool(url), "enclosure": url,
                       "enclosure_status": ok_head})
    print(json.dumps({"bakeoff_items_in_feed": len(found), "episodes": report}, indent=1))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("packet").set_defaults(fn=cmd_packet)
    for name, fn in (("script", cmd_script), ("tts", cmd_tts), ("check", cmd_check),
                     ("publish", cmd_publish)):
        p = sub.add_parser(name)
        p.add_argument("n", type=int, choices=sorted(AUTHORS))
        p.set_defaults(fn=fn)
    sub.add_parser("verify").set_defaults(fn=cmd_verify)
    args = ap.parse_args()
    args.fn(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
