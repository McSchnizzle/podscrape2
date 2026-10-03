"""Reserved topic for one-off script-model bakeoff episodes.

Bakeoff episodes are generated, voiced and published by an explicit,
digest-id-targeted tool, never by the nightly pipeline. Every nightly
selector that could otherwise pick them up excludes this topic:

- TTS pending selection   (src/database/models.py get_digests_pending_tts)
- nightly publishing      (scripts/run_publishing.py)
- Phase 8 briefing source (src/publishing/creator_briefing.py select_digest)

They still appear in the public feed (/daily-digest.xml) once published,
because that is the point. Retention treats them like any other digest.
"""

BAKEOFF_TOPIC = "Bakeoff"
