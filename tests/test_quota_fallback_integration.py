"""Provider failure behavior at every scheduled Podcast completion boundary."""
import importlib
import subprocess
from unittest.mock import Mock

import pytest

from src.utils import claude_p_health, claude_quota_fallback
from src.generation.script_generator import ScriptGenerator

BOUNDARIES = [
    ('src.generation.script_generator', 'ScriptGenerator._call_claude_p', ('system', 'source')),
    ('src.scoring.content_scorer', 'ContentScorer._call_claude_p', ('source',)),
    ('src.audio.metadata_generator', 'MetadataGenerator._call_claude_p', ('source',)),
    ('src.topic_tracking.topic_extractor', 'StoryArcExtractor._call_claude_p', ('source',)),
    ('src.topic_tracking.digest_arc_reconciler', 'DigestArcReconciler._call_claude_p', ('source',)),
    ('src.topic_tracking.hot_briefing_generator', '_call_claude_p', ('system', 'source')),
    ('src.generation.dedup_pass', '_call_claude_p', ('system', 'source')),
    ('src.generation.transcript_dedup', '_call_claude_p', ('source',)),
    ('src.generation.transcript_scrubber', '_call_claude_p', ('system', 'source')),
    ('src.watch.theme_scan', '_call_claude_p', ('system', 'source')),
    ('scripts.summarize_watch_digest', 'call_claude_p', ('source',)),
]


def boundary(module_name, dotted_name):
    module = importlib.import_module(module_name)
    function = module
    for component in dotted_name.split('.'):
        function = getattr(function, component)
    return module, function


@pytest.mark.parametrize('module_name,dotted_name,args', BOUNDARIES)
def test_quota_recovers_at_completion_boundary(monkeypatch, module_name, dotted_name, args):
    module, function = boundary(module_name, dotted_name)
    claude = Mock(return_value=subprocess.CompletedProcess(['claude'], 1, '', "You've hit your limit · resets 5pm"))
    codex = Mock(return_value=subprocess.CompletedProcess(['codex'], 0, ' recovered output ', ''))
    monkeypatch.setattr(claude_quota_fallback, '_bounded_run', claude)
    monkeypatch.setattr(claude_quota_fallback, 'run_codex', codex)
    assert function(*args, timeout=300) == 'recovered output'
    assert claude.call_count == 1
    assert codex.call_count == 1
    assert 'source' in claude.call_args.kwargs['input']


@pytest.mark.parametrize('module_name,dotted_name,args', BOUNDARIES)
def test_nonquota_failure_keeps_existing_error(monkeypatch, module_name, dotted_name, args):
    module, function = boundary(module_name, dotted_name)
    monkeypatch.setattr(claude_quota_fallback, '_bounded_run', Mock(return_value=subprocess.CompletedProcess(['claude'], 1, '', 'authentication failed')))
    codex = Mock(side_effect=AssertionError('nonquota must not invoke Codex'))
    monkeypatch.setattr(claude_quota_fallback, 'run_codex', codex)
    with pytest.raises(Exception, match='authentication failed'):
        function(*args, timeout=300)
    codex.assert_not_called()


def test_failed_quota_fallback_never_retries_or_sleeps(monkeypatch):
    generator = object.__new__(ScriptGenerator)
    call = Mock(side_effect=claude_quota_fallback.QuotaFallbackError('Codex unavailable'))
    notify = Mock()
    monkeypatch.setattr(generator, '_call_claude_p', call)
    monkeypatch.setattr(generator, '_notify_claude_p_exhausted', notify)
    monkeypatch.setattr('time.sleep', Mock(side_effect=AssertionError('must not retry quota')))
    with pytest.raises(claude_quota_fallback.QuotaFallbackError):
        generator._call_claude_p_with_retry('system', 'source')
    call.assert_called_once()
    notify.assert_called_once()


@pytest.mark.parametrize('returncode', [0, 1])
def test_quota_probe_keeps_optional_stages_enabled(monkeypatch, returncode):
    monkeypatch.setattr(subprocess, 'run', Mock(return_value=subprocess.CompletedProcess(['claude'], returncode, "You've hit your limit · resets 5pm", '')))
    codex = Mock(side_effect=AssertionError('health probe must not spend Codex budget'))
    monkeypatch.setattr(claude_quota_fallback, 'run_codex', codex)
    assert claude_p_health._run_probe() is True
    codex.assert_not_called()


def test_hung_probe_still_skips_optional_stages(monkeypatch):
    monkeypatch.setattr(subprocess, 'run', Mock(side_effect=subprocess.TimeoutExpired('claude', 20)))
    assert claude_p_health._run_probe() is False


def test_optional_dedup_preserves_original_when_fallback_fails(monkeypatch):
    from src.generation import dedup_pass
    original = 'Existing script. ' * 100
    monkeypatch.setattr(claude_p_health, 'is_claude_p_healthy', lambda: True)
    monkeypatch.setattr(dedup_pass, '_fetch_prior_digests', lambda **kwargs: [{'date': '2026-09-01', 'content': 'Prior digest'}])
    monkeypatch.setattr(dedup_pass, '_call_claude_p', Mock(side_effect=claude_quota_fallback.QuotaFallbackError('Codex unavailable')))
    result = dedup_pass.run_dedup_pass(original, 'AI and Technology')
    assert result.skipped
    assert result.rewritten_script == original


@pytest.fixture(autouse=True)
def reset_provider_quota_circuit():
    claude_quota_fallback.reset_quota_cache()
    yield
    claude_quota_fallback.reset_quota_cache()
