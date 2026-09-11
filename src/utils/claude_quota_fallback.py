"""Quota-only Claude to Codex completion transport.

Canonical source: Harold tools/claude_quota_fallback.py. Other projects vendor
this file verbatim with its SHA-256; no host checkout is a runtime dependency.
This module performs completions, never publication, queue acknowledgement, or
agentic work. Callers retain their validators and side-effect boundaries.
"""
from __future__ import annotations

import asyncio
from contextlib import contextmanager
import hashlib
import json
import logging
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import tempfile
import threading
import time

DEFAULT_MODEL = 'gpt-6-astra'
MAX_OUTPUT_BYTES = 1_048_576
LOG = logging.getLogger(__name__)
_QUOTA_RE = re.compile(
    r"(?:you(?:'ve| have)?\s+(?:hit|reached)\s+your\s+(?:usage\s+)?limit"
    r'|(?:usage|(?:weekly|session|subscription)(?:\s+usage)?)\s+limit\s+(?:has been\s+)?(?:reached|exceeded|exhausted)'
    r'|(?:reached|exceeded|exhausted)\s+(?:your\s+|the\s+)?(?:usage|(?:weekly|session|subscription)(?:\s+usage)?)\s+limit'
    r'|out of extra usage|credit balance is too low|insufficient[_ ]quota'
    r'|usage_limit_reached|quota[_ ]exhausted)', re.I)
_NONQUOTA_RE = re.compile(r'oauth|token expired|invalid api key|authentication|prompt is too long|context.{0,25}(?:limit|exceed)', re.I)
_quota_lock = threading.Lock()
_quota_until: dict[str, float] = {}


class QuotaFallbackError(RuntimeError):
    """Claude allowance was exhausted and Codex could not finish safely.

    Callers must not restart a Claude retry loop for this failure.
    Messages deliberately exclude provider output and prompts.
    """


def _text(value):
    return value.decode('utf-8', errors='replace') if isinstance(value, bytes) else str(value or '')


def is_quota_exhausted(result) -> bool:
    """Recognize explicit failure evidence, never arbitrary successful prose."""
    stdout, stderr = _text(result.stdout), _text(result.stderr)
    envelope = None
    try:
        value = json.loads(stdout)
        if isinstance(value, dict): envelope = value
    except ValueError:
        # Also accept the terminal result of Claude --output-format stream-json.
        for line in stdout.splitlines():
            try:
                value = json.loads(line)
                if isinstance(value, dict) and value.get('type') == 'result': envelope = value
            except ValueError:
                pass
    if envelope is not None:
        if envelope.get('is_error') is False and result.returncode == 0:
            return False
        if envelope.get('is_error') or result.returncode != 0:
            message = ' '.join(_text(envelope.get(k)) for k in ('result', 'error', 'errors', 'subtype')) + ' ' + stderr
        else:
            return False
    elif result.returncode != 0:
        message = stdout + ' ' + stderr
    else:
        # Claude can print a quota notice and exit zero. Only a leading notice
        # qualifies here, not a quota phrase quoted later in a valid answer.
        message = stdout.strip()
        if not _QUOTA_RE.match(message): return False
    return bool(_QUOTA_RE.search(message)) and not bool(_NONQUOTA_RE.search(message))


def _account_key(env=None):
    source = os.environ if env is None else env
    material = '\0'.join(str(source.get(k, '')) for k in
                         ('HOME', 'CLAUDE_CONFIG_DIR', 'CLAUDE_CODE_OAUTH_TOKEN', 'ANTHROPIC_API_KEY'))
    return hashlib.sha256(material.encode()).hexdigest()


def mark_quota_exhausted(env=None):
    with _quota_lock: _quota_until[_account_key(env)] = time.monotonic() + 300


def quota_circuit_open(env=None):
    with _quota_lock: return _quota_until.get(_account_key(env), 0) > time.monotonic()


def reset_quota_cache():
    with _quota_lock: _quota_until.clear()


def _environment(env):
    source = os.environ if env is None else env
    allowed = {'PATH', 'HOME', 'USER', 'LOGNAME', 'LANG', 'LC_ALL', 'TZ', 'TMPDIR',
               'TMP', 'TEMP', 'CODEX_HOME', 'XDG_CONFIG_HOME', 'XDG_CACHE_HOME',
               'XDG_DATA_HOME', 'XDG_RUNTIME_DIR', 'HTTP_PROXY', 'HTTPS_PROXY',
               'ALL_PROXY', 'NO_PROXY', 'http_proxy', 'https_proxy', 'all_proxy',
               'no_proxy', 'SSL_CERT_FILE', 'SSL_CERT_DIR', 'NODE_EXTRA_CA_CERTS'}
    clean = {k: str(v) for k, v in source.items() if k in allowed}
    clean.setdefault('PATH', os.defpath)
    clean.setdefault('HOME', str(Path.home()))
    return clean


def _strict_schema(schema):
    """Only send schemas already compatible with strict structured output.

    Optional/open schemas remain unchanged in the prompt and are validated
    against the original after completion. Never invent required/null fields.
    """
    if not isinstance(schema, dict): return False
    if schema.get('type') == 'object' or 'properties' in schema:
        props = schema.get('properties', {})
        if schema.get('additionalProperties') is not False or set(schema.get('required', [])) != set(props): return False
        if not all(_strict_schema(v) for v in props.values()): return False
    if isinstance(schema.get('items'), dict) and not _strict_schema(schema['items']): return False
    for key in ('anyOf', 'oneOf', 'allOf'):
        if key in schema and not all(_strict_schema(s) for s in schema[key]): return False
    if '$ref' in schema or '$defs' in schema or 'definitions' in schema: return False
    return True


@contextmanager
def _request(prompt, *, timeout, env=None, model=None, schema=None, images=()):
    if timeout is None or timeout <= 0: raise QuotaFallbackError('completion deadline exhausted')
    source = os.environ if env is None else env
    model = model or source.get('CLAUDE_QUOTA_CODEX_MODEL') or DEFAULT_MODEL
    binary = source.get('CODEX_BIN') or shutil.which('codex', path=source.get('PATH'))
    if not binary:
        candidate = Path(source.get('HOME', str(Path.home()))) / '.local/bin/codex'
        binary = str(candidate) if candidate.is_file() else 'codex'
    with tempfile.TemporaryDirectory(prefix='claude-quota-codex-') as directory:
        out = Path(directory) / 'answer.txt'
        argv = [binary, 'exec', '--ephemeral', '--ignore-user-config', '--ignore-rules',
                '--skip-git-repo-check', '--sandbox', 'read-only', '--cd', directory,
                '--json', '--model', model, '-c', 'model_reasoning_effort="low"',
                '-c', 'web_search="disabled"']
        # Disable capabilities, not merely their use in prose. Host skills and
        # hooks are excluded so a utility call cannot load a workflow or recurse.
        for feature in ('shell_tool', 'unified_exec', 'apps', 'browser_use',
                        'browser_use_external', 'browser_use_full_cdp_access',
                        'computer_use', 'image_generation', 'multi_agent',
                        'multi_agent_v2', 'hooks', 'code_mode', 'code_mode_host',
                        'view_image'):
            argv += ['--disable', feature]
        argv += ['--enable', 'skip_host_skill_discovery']
        for image in images:
            p = Path(image).resolve()
            if not p.is_file(): raise QuotaFallbackError('completion image unavailable')
            argv += ['--image', str(p)]
        if schema is not None:
            # Validate the schema itself before invoking a model.
            try:
                import jsonschema
                jsonschema.validators.validator_for(schema).check_schema(schema)
            except Exception as exc:
                raise QuotaFallbackError('completion schema unavailable or invalid') from exc
            if schema.get('type') == 'object' and _strict_schema(schema):
                path = Path(directory) / 'schema.json'
                path.write_text(json.dumps(schema))
                argv += ['--output-schema', str(path)]
            else:
                prompt += '\n\nReturn only JSON matching this schema:\n' + json.dumps(schema)
        argv += ['--output-last-message', str(out), '-']
        yield argv, _environment(env), prompt, out, model


def _kill_group(proc):
    try: os.killpg(proc.pid, signal.SIGKILL)
    except ProcessLookupError: pass


def _bounded_run(argv, *, input=None, timeout, env=None, cwd=None, **kwargs):
    """Spool provider diagnostics, bound returned bytes, reap process groups."""
    kwargs.pop('capture_output', None)
    kwargs.pop('text', None)
    kwargs.pop('check', None)
    if kwargs.get('stdin') is None: kwargs.pop('stdin', None)
    kwargs.pop('start_new_session', None)
    with tempfile.TemporaryFile() as stdout, tempfile.TemporaryFile() as stderr:
        proc = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=stdout, stderr=stderr,
                                text=True, env=env, cwd=cwd, start_new_session=True, **kwargs)
        try:
            proc.communicate(input=input, timeout=timeout)
        finally:
            # Kill any surviving descendants too, including after parent exit.
            _kill_group(proc)
            proc.wait()
        if stdout.tell() > MAX_OUTPUT_BYTES or stderr.tell() > MAX_OUTPUT_BYTES:
            raise QuotaFallbackError('completion output exceeded limit')
        stdout.seek(0); stderr.seek(0)
        return subprocess.CompletedProcess(argv, proc.returncode, _text(stdout.read()), _text(stderr.read()))


def _finish(result, output, model, schema, started):
    if result.returncode != 0: raise QuotaFallbackError('Codex completion failed')
    if not output.is_file() or output.stat().st_size > MAX_OUTPUT_BYTES:
        raise QuotaFallbackError('Codex final output missing or oversized')
    answer = output.read_text(encoding='utf-8').strip()
    if not answer: raise QuotaFallbackError('Codex final output empty')
    usage, session_id, completed = {}, None, False
    for line in _text(result.stdout).splitlines():
        try: event = json.loads(line)
        except ValueError: continue
        if not isinstance(event, dict): continue
        if event.get('type') in ('turn.failed', 'error'):
            raise QuotaFallbackError('Codex reported a failed completion')
        if event.get('type') == 'thread.started': session_id = event.get('thread_id')
        if event.get('type') == 'turn.completed':
            usage = event.get('usage') or {}
            completed = True
        item = event.get('item') or {}
        if isinstance(item, dict) and item.get('type') in ('command_execution', 'mcp_tool_call', 'web_search', 'file_change'):
            raise QuotaFallbackError('unexpected tool use in utility completion')
    if not completed: raise QuotaFallbackError('Codex completion event missing')
    if schema is not None:
        try:
            import jsonschema
            jsonschema.validate(json.loads(answer), schema)
        except Exception as exc:
            raise QuotaFallbackError('Codex output failed schema validation') from exc
    duration = int((time.monotonic() - started) * 1000)
    final = subprocess.CompletedProcess(result.args, 0, answer, '')
    final.provider, final.model, final.usage = 'codex', model, usage
    final.fallback_reason = 'claude_quota_exhausted'
    final.metadata = dict(provider='codex', model=model, usage=usage,
                          fallback_reason=final.fallback_reason, duration_ms=duration,
                          session_id=session_id, total_cost_usd=None)
    LOG.info('completion provider=codex model=%s reason=claude_quota_exhausted duration_ms=%d', model, duration)
    return final


def run_codex(prompt, *, timeout, env=None, model=None, schema=None, images=(), runner=None):
    """One bounded, tool-disabled Codex completion using subscription auth."""
    started = time.monotonic()
    with _request(prompt, timeout=timeout, env=env, model=model, schema=schema, images=images) as (argv, clean, text, out, chosen):
        try:
            result = (runner or _bounded_run)(argv, input=text, capture_output=True,
                                               text=True, timeout=timeout, env=clean)
            return _finish(result, out, chosen, schema, started)
        except QuotaFallbackError: raise
        except Exception as exc:
            raise QuotaFallbackError('Codex completion transport failed: ' + type(exc).__name__) from exc


async def run_codex_async(prompt, *, timeout, env=None, model=None, schema=None, images=()):
    """Async equivalent; cancellation kills and reaps the complete child group."""
    started = time.monotonic()
    with _request(prompt, timeout=timeout, env=env, model=model, schema=schema, images=images) as (argv, clean, text, out, chosen):
        with tempfile.TemporaryFile() as stdout, tempfile.TemporaryFile() as stderr:
            try:
                proc = await asyncio.create_subprocess_exec(*argv, stdin=asyncio.subprocess.PIPE,
                           stdout=stdout, stderr=stderr, env=clean, start_new_session=True)
                try:
                    await asyncio.wait_for(proc.communicate(text.encode()), timeout=timeout)
                finally:
                    _kill_group(proc)
                    await asyncio.shield(proc.wait())
                if stdout.tell() > MAX_OUTPUT_BYTES or stderr.tell() > MAX_OUTPUT_BYTES:
                    raise QuotaFallbackError('Codex output exceeded limit')
                stdout.seek(0); stderr.seek(0)
                result = subprocess.CompletedProcess(argv, proc.returncode, _text(stdout.read()), _text(stderr.read()))
                return _finish(result, out, chosen, schema, started)
            except asyncio.CancelledError: raise
            except QuotaFallbackError: raise
            except Exception as exc:
                raise QuotaFallbackError('Codex completion transport failed: ' + type(exc).__name__) from exc


def claude_envelope(result, schema=None):
    meta = result.metadata
    envelope = dict(type='result', is_error=False, result=result.stdout, **meta)
    if schema is not None: envelope['structured_output'] = json.loads(result.stdout)
    return envelope


def _prompt_from_args(args, input):
    positional, system = [], []
    takes_value = {'--model', '--effort', '--tools', '--max-turns', '--setting-sources',
                   '--output-format', '--json-schema', '--append-system-prompt', '--system-prompt',
                   '--permission-mode', '--allowedTools', '--allowed-tools', '--settings', '--mcp-config'}
    i = 1
    while i < len(args):
        arg = str(args[i])
        if arg in takes_value:
            if i + 1 >= len(args): raise QuotaFallbackError('incomplete Claude argument')
            if arg in ('--append-system-prompt', '--system-prompt'): system.append(str(args[i+1]))
            i += 2; continue
        if not arg.startswith('-'): positional.append(arg)
        i += 1
    return '\n\n'.join(system + positional + ([_text(input)] if input else []))


def _arg_value(args, name):
    try: return args[args.index(name) + 1]
    except (ValueError, IndexError): return None


def run_claude(args, *, input=None, timeout, env=None, cwd=None, capture_output=True,
               text=True, images=(), schema=None, runner=None, fallback_prompt=None,
               model=None, **kwargs):
    """subprocess.run-compatible completion boundary with quota-only fallback.

    Successful Claude calls and non-quota failures retain their exact result.
    This is only for pure completion callers. Agentic runners must establish
    their own safe retry checkpoint before calling run_codex.
    """
    if not capture_output or not text: raise ValueError('quota adapter requires captured text output')
    started = time.monotonic()
    check = kwargs.pop('check', False)
    if not quota_circuit_open(env):
        result = (runner or _bounded_run)(args, input=input, timeout=timeout, env=env,
                         cwd=cwd, capture_output=True, text=True, **kwargs)
        if not is_quota_exhausted(result):
            if check: result.check_returncode()
            return result
        mark_quota_exhausted(env)
    if _arg_value(args, '--output-format') == 'stream-json':
        raise QuotaFallbackError('agentic stream callers must manage their own checkpoint')
    remaining = timeout - (time.monotonic() - started)
    if remaining <= 0: raise QuotaFallbackError('completion deadline exhausted after Claude')
    if schema is None and _arg_value(args, '--json-schema') is not None:
        try: schema = json.loads(_arg_value(args, '--json-schema'))
        except ValueError as exc: raise QuotaFallbackError('invalid Claude schema') from exc
    prompt = fallback_prompt if fallback_prompt is not None else _prompt_from_args(args, input)
    if not prompt: raise QuotaFallbackError('completion prompt missing')
    final = run_codex(prompt, timeout=remaining, env=env, model=model,
                      schema=schema, images=images, runner=runner)
    if _arg_value(args, '--output-format') == 'json':
        final.stdout = json.dumps(claude_envelope(final, schema))
    return final
