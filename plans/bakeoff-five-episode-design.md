# Five-episode script-model bakeoff: design checkpoint (NOT YET RUN)

Status 2026-10-03: research and design only. No script generation, TTS,
voice-library change, DB write, or publication has happened. Everything below
waits for Paul's go-ahead after the cost checkpoint.

## 1. Authors (exact ids, medium effort, no fallback)

| # | Author (title text) | Exact id | Effort | Evidence |
|---|---|---|---|---|
| 1 | Claude Sonnet 5.5 | `claude-sonnet-5-5` | `--effort medium` | Claude Code 2.1.288 binary carries the id; its alias table maps `sonnet` -> `claude-sonnet-5-5`; `--effort` accepts low/medium/high/xhigh/max |
| 2 | Claude Opus 5.5 | `claude-opus-5-5` | `--effort medium` | id present in the same binary |
| 3 | GPT-6.1-Sol | `gpt-6.1-sol` | `model_reasoning_effort="medium"` | `~/.codex/models_cache.json` (fetched 2026-10-03 20:10Z), efforts low..ultra |
| 4 | GPT-6-Astra | `gpt-6-astra` | medium | same catalog |
| 5 | GPT-5.6-Terra | `gpt-5.6-terra` | medium | same catalog |

Not provable without a call: account access to each id. The first real call
per author is the proof; a refusal aborts THAT author with no substitute.

No silent fallback, by construction:
- Claude authors are invoked directly (`claude -p --model <id> --effort medium
  --tools "" --no-session-persistence --output-format json`), NOT through
  `run_claude`, whose quota path would answer with Codex. The JSON envelope's
  `modelUsage` keys must equal exactly `{<id>}` or the script is discarded.
- GPT authors use `codex exec` with the same tool-disabled flags as
  `run_codex`, but `-m <id> -c model_reasoning_effort="medium"`.
  `run_codex` itself hardcodes `low`, so it is NOT used.
- Each result is stored with: requested id, effort, observed model id,
  provider, session/thread id, prompt sha256, packet sha256.

## 2. Common research packet

One frozen JSON file, identical bytes for all five, sha256 recorded:
- Source: AI and Technology episodes already transcribed and scored, chosen
  read-only (no `mark_episode_as_digested`, no DB writes).
- DECISION FOR PAUL: (a) episodes from the last published digest (known
  material, fair comparison, repeats stories listeners heard), or
  (b) the newest undigested scored episodes (fresh, but tonight's normal
  digest would cover the same stories). Recommendation: (a) or a fixed past
  date, so the bakeoff does not consume tonight's material.
- 3-4 episodes, transcripts trimmed to a fixed budget per episode so every
  model gets the same context and none is truncated differently.

## 3. Common prompt (outline)

- Hosts: SPEAKER_1 = Alexis, SPEAKER_2 = Brandon (on-air names; see voice
  blockers). Output only `SPEAKER_n:` lines.
- Length: 4,300-4,900 characters including tags (about 5 minutes at the
  current pacing, roughly 750 spoken words). Hard floor 3,800, ceiling 5,500.
- Range: at least one genuinely funny beat, at least one story given real
  weight, and a change of energy across the episode. Reuse the house
  attribution, analytical-depth and anti-AI rules from
  `.claude/commands/generate-digest.md` and `src/generation/anti_ai_rules.py`.
- v4 delivery (official v4 guide): tags such as [laughs], [sighs],
  [exhales], [whispers], [sarcastic], [curious], [excited], [mischievously],
  plus pacing via ellipses and [pause] / [long pause]. No SSML `<break>` (not
  supported in v3 or v4). No sound-effect tags. Budget: 8-14 tags, max one per
  turn, no tag on more than 35% of turns.
- No title, no self-reference, no attribution line: authorship is recorded by
  the harness, not by the model.

## 4. Audio

- Model `eleven_v4` via Text-to-Dialogue (docs: "available on the Eleven v4
  and Eleven v3 models"; v4_turbo not listed for dialogue).
- Chunk at <= 2,000 characters per request (API reference guidance; the
  production chunker uses 2,500).
- The dialogue payload sends no voice settings, so v3 stability snapping is
  not involved.

## 5. Voices (read-only checks, 2026-10-03)

- `VlUmeC1Uzj3NnwiVR9K9` (for Brandon): exists in the account, but its
  ElevenLabs name is "Julius" (professional clone, young male, chill,
  social media). High-quality model list has no v3/v4 entry.
- `ojFyGQgYMiSn66RY5Wyk` (for Alexis): NOT in the account
  (`voice_not_found`). The public shared library has it as "Shay Professional
  Voice" (female, sassy, social media). Using it requires adding it to the
  account library, which is a change not yet made.
- v4 FAQ: professional clones made before v4 should be retrained for v4 to
  work well. Neither voice shows v4 training. Retraining is a separate,
  unapproved change.

## 6. Cost (read-only)

- ElevenLabs: tier growing_business, 143,882 of 6,000,000 characters used
  this cycle (resets 2026-10-26 21:38 PT). v4 cost multiplier 1.0.
  Five episodes at about 4,900 characters each is about 24,500 credits,
  0.4% of the cycle, within the plan (no overage). No retakes assumed;
  each retake costs one episode's characters again.
- Script generation: Claude Max and Codex subscription quotas, not
  per-token billing. Five single calls; Opus uses the most quota.
- No metadata model calls: titles and descriptions are fixed text.

## 7. Publication plan (exactly five, idempotent)

Facts (read-only review of the publishing path):
- RSS `/daily-digest.xml` includes any topic with `github_url` and
  `mp3_path`; title is `mp3_title` verbatim. `/ai-tech-digest.xml` includes
  only "AI and Technology".
- Unique key `(topic, digest_date, digest_timestamp)`. Release per date
  (`daily-YYYY-MM-DD`); asset upload skips an existing filename silently.
- Nightly TTS picks rows with a script and no MP3 (a "Bakeoff" topic with no
  voice config would be retried and skipped every night). Nightly publishing
  publishes any row with an MP3 in the last 30 days, regardless of topic.
- Phase 8 briefing `select_digest` has NO topic filter: a published bakeoff
  row can become the night's briefing source.
- Retention deletes digest rows and `daily-*` releases after 14 days unless
  `is_favorite`.

Plan:
1. Generate five scripts (harness above), store them with provenance in a
   scratch run directory, verify observed author ids. Stop on any mismatch.
2. Generate five MP3s offline (eleven_v4, Text-to-Dialogue, <=2,000-char
   chunks), named `Bakeoff_YYYYMMDD_12000N.mp3`.
3. Insert five rows only after the audio exists: topic "Bakeoff",
   `mp3_path` set, `episode_count` = packet episode count, final `mp3_title`
   ("Bakeoff N of 5: written by <actual model>"), fixed
   `digest_timestamp` 12:0N:00 as the idempotency key,
   `INSERT ... ON CONFLICT DO NOTHING`. Nightly TTS never selects them.
4. Publish by explicit digest id (small script: release upload + 
   `github_url` + `update_published`); re-runs skip rows with `github_url`.
5. Briefing guard: publish after tonight's 21:00 run finishes and its
   briefing is sent, or add a topic filter to `select_digest` (code change,
   needs approval).
6. Decide `is_favorite` (keeps them past 14 days, and keeps that date's
   whole release).
