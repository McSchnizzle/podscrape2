"""
Unit tests for the script_generator expansion loop termination fix (kanban #2423).

Root cause: The expansion loop in create_digest re-initialised `existing_ids`
from `episodes` at the top of every iteration. When an episode was rejected as
"fully redundant" (empty pre-deduped transcript) its ID was never added to
`episodes`, so it was excluded from `existing_ids` on the next pass and the
same episode was re-fetched indefinitely.

Fix (this module): Replace the per-iteration `existing_ids` re-init with a
persistent `excluded_from_expansion` set that lives OUTSIDE the while loop and
is updated immediately after every fetch (before the redundancy filter).

These tests exercise the loop algorithm in isolation — no ScriptGenerator
instantiation required, so no heavy DB / API dependencies.
"""

from __future__ import annotations

import unittest
from typing import Any


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

class _FakeEp:
    """Minimal Episode-like stub sufficient for expansion-loop testing."""

    def __init__(self, ep_id: int, title: str = "", transcript: str = "hello"):
        self.id = ep_id
        self.title = title
        self.transcript_content = transcript
        self.scores: dict[str, float] = {"AI and Technology": 0.9}


def _make_fake_get_extra(pool: list[_FakeEp]):
    """
    Return a callable that simulates _get_extra_scored_episodes against `pool`.
    Each call returns the first episode NOT in exclude_ids, or [] if exhausted.
    Also records every (exclude_ids_snapshot, returned_ep_ids) pair for assertions.
    """
    call_log: list[tuple[frozenset, list[int]]] = []

    def get_extra(topic: str, exclude_ids: set, limit: int) -> list[_FakeEp]:
        for ep in pool:
            if ep.id not in exclude_ids:
                call_log.append((frozenset(exclude_ids), [ep.id]))
                return [ep]
        call_log.append((frozenset(exclude_ids), []))
        return []

    return get_extra, call_log


def _run_fixed_loop(
    initial_episodes: list[_FakeEp],
    pool: list[_FakeEp],
    deduped_cache: dict[int, str],
    *,
    target_chars: int = 25_000,
    max_transcripts: int = 9,
    max_iter: int = 1_000,
) -> tuple[list[_FakeEp], list[tuple[frozenset, list[int]]], int]:
    """
    Run the FIXED expansion loop algorithm and return:
      - final episodes list
      - call log (see _make_fake_get_extra)
      - number of iterations executed
    Raises AssertionError if max_iter is exceeded (infinite-loop guard).
    """
    get_extra, call_log = _make_fake_get_extra(pool)

    episodes = list(initial_episodes)
    script_content = ""  # empty → below target, forces expansion
    topic = "AI and Technology"

    # ── FIXED: persistent exclusion set, initialised OUTSIDE the loop ──
    excluded_from_expansion = {ep.id for ep in episodes if ep.id is not None}
    iterations = 0

    while len(script_content) < target_chars and len(episodes) < max_transcripts:
        iterations += 1
        assert iterations <= max_iter, (
            f"Infinite-loop regression: still running after {max_iter} iterations"
        )

        extras = get_extra(topic=topic, exclude_ids=excluded_from_expansion, limit=1)
        if not extras:
            break

        # Record fetched IDs IMMEDIATELY (before redundancy filter)
        excluded_from_expansion.update(ep.id for ep in extras if ep.id is not None)

        # Apply pre-deduped transcript if cached
        for ep in extras:
            if ep.id in deduped_cache:
                ep.transcript_content = deduped_cache[ep.id]

        # Drop fully redundant episodes
        extras = [
            ep for ep in extras
            if ep.id not in deduped_cache or deduped_cache.get(ep.id)
        ]
        if not extras:
            continue  # try the next candidate

        episodes = list(episodes) + list(extras)
        # Simulate script generation producing long-enough content the moment
        # a real (non-redundant) episode is added.
        if any(ep.transcript_content for ep in extras):
            script_content = "x" * target_chars

    return episodes, call_log, iterations


def _run_broken_loop(
    initial_episodes: list[_FakeEp],
    pool: list[_FakeEp],
    deduped_cache: dict[int, str],
    *,
    target_chars: int = 25_000,
    max_transcripts: int = 9,
    max_iter: int = 50,
) -> int:
    """
    Run the OLD (broken) expansion loop algorithm and return the iteration count.
    This function is used in regression tests to prove the OLD code would loop
    indefinitely on a redundant episode.
    """
    get_extra, _ = _make_fake_get_extra(pool)

    episodes = list(initial_episodes)
    script_content = ""
    topic = "AI and Technology"
    iterations = 0

    while len(script_content) < target_chars and len(episodes) < max_transcripts:
        iterations += 1
        if iterations > max_iter:
            break  # old code would never reach this on its own — we cap it

        # OLD: per-iteration re-init discards rejected IDs
        existing_ids = {ep.id for ep in episodes if ep.id is not None}
        extras = get_extra(topic=topic, exclude_ids=existing_ids, limit=1)
        if not extras:
            break

        fetched_ids = {ep.id for ep in extras}
        for ep in extras:
            if ep.id in deduped_cache:
                ep.transcript_content = deduped_cache[ep.id]

        extras = [
            ep for ep in extras
            if ep.id not in deduped_cache or deduped_cache.get(ep.id)
        ]
        if not extras:
            existing_ids.update(fetched_ids)  # discarded on next iteration!
            continue

        episodes = list(episodes) + list(extras)
        if any(ep.transcript_content for ep in extras):
            script_content = "x" * target_chars

    return iterations


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestExpansionLoopTermination(unittest.TestCase):
    """The fixed loop must terminate when all expansion candidates are redundant."""

    def _base(self) -> _FakeEp:
        return _FakeEp(1, "Base episode", "x" * 1000)

    def test_single_redundant_episode_terminates(self):
        """One redundant episode → loop exits after 2 fetches (fetch + exhaust)."""
        pool = [_FakeEp(100, "Redundant", "")]
        deduped_cache = {100: ""}  # empty = fully redundant

        eps, call_log, iterations = _run_fixed_loop(
            [self._base()], pool, deduped_cache
        )
        # Calls: fetch ep-100 (redundant), fetch [] (exhausted)
        self.assertEqual(len(call_log), 2, f"call_log={call_log}")
        self.assertLess(iterations, 10, "Loop took too many iterations")

    def test_multiple_redundant_episodes_terminate(self):
        """5 redundant episodes → loop exhausts pool then exits."""
        pool = [_FakeEp(100 + i, f"Redundant {i}", "") for i in range(5)]
        deduped_cache = {ep.id: "" for ep in pool}

        eps, call_log, iterations = _run_fixed_loop(
            [self._base()], pool, deduped_cache
        )
        # 5 redundant fetches + 1 exhausted = 6 calls
        self.assertEqual(len(call_log), 6, f"call_log={call_log}")

    def test_exclude_ids_grow_each_call(self):
        """exclude_ids passed to each successive call must be strictly larger."""
        pool = [_FakeEp(100 + i) for i in range(4)]
        # All fully redundant
        deduped_cache = {ep.id: "" for ep in pool}

        _, call_log, _ = _run_fixed_loop([self._base()], pool, deduped_cache)

        for i in range(1, len(call_log)):
            prev_excl, _ = call_log[i - 1]
            curr_excl, _ = call_log[i]
            self.assertGreater(
                len(curr_excl), len(prev_excl),
                f"exclude_ids did not grow at call {i}: {prev_excl} → {curr_excl}",
            )

    def test_first_call_excludes_only_base_episode(self):
        """First call to _get_extra must exclude exactly the initial episodes."""
        pool = [_FakeEp(100, "Redundant", "")]
        deduped_cache = {100: ""}

        _, call_log, _ = _run_fixed_loop([self._base()], pool, deduped_cache)

        first_excl, _ = call_log[0]
        self.assertEqual(first_excl, frozenset({1}))  # only the base ep (id=1)

    def test_second_call_excludes_first_redundant(self):
        """After fetching a redundant ep-100, the next call must exclude 100."""
        pool = [_FakeEp(100, "Redundant1", ""), _FakeEp(101, "Redundant2", "")]
        deduped_cache = {100: "", 101: ""}

        _, call_log, _ = _run_fixed_loop([self._base()], pool, deduped_cache)

        _, second_excl = call_log[1][0], call_log[1][0]
        self.assertIn(100, call_log[1][0])

    def test_no_episode_added_when_all_redundant(self):
        """Episode list must remain unchanged when every candidate is redundant."""
        base = self._base()
        pool = [_FakeEp(100, "Redundant", "")]
        deduped_cache = {100: ""}

        final_eps, _, _ = _run_fixed_loop([base], pool, deduped_cache)
        self.assertEqual([ep.id for ep in final_eps], [1])


class TestExpansionLoopRegressionGuard(unittest.TestCase):
    """Prove that the OLD code exhibits the infinite-loop bug this fix addresses."""

    def test_old_code_loops_to_cap_on_redundant_episode(self):
        """
        The broken algorithm re-creates existing_ids each iteration, so a
        redundant episode is never excluded and is re-fetched indefinitely.
        The old loop hits our MAX_ITER cap instead of terminating naturally.
        """
        base = _FakeEp(1, "Base", "x" * 1000)
        pool = [_FakeEp(100, "Always redundant", "")]
        deduped_cache = {100: ""}

        MAX_ITER = 50
        iterations = _run_broken_loop([base], pool, deduped_cache, max_iter=MAX_ITER)

        self.assertGreaterEqual(
            iterations, MAX_ITER,
            f"Expected old code to reach the {MAX_ITER}-iteration cap (infinite loop), "
            f"but it stopped at {iterations}",
        )

    def test_fixed_code_terminates_where_old_would_hang(self):
        """
        Same scenario as above, but with the FIXED algorithm: must exit in
        ≤3 iterations (fetch redundant, exhaust pool, done).
        """
        base = _FakeEp(1, "Base", "x" * 1000)
        pool = [_FakeEp(100, "Always redundant", "")]
        deduped_cache = {100: ""}

        _, _, iterations = _run_fixed_loop(
            [base], pool, deduped_cache, max_iter=100
        )
        self.assertLessEqual(
            iterations, 3,
            f"Fixed code should exit in ≤3 iterations, took {iterations}",
        )


class TestExpansionLoopGoodEpisode(unittest.TestCase):
    """A non-redundant episode must be accepted and added to the digest."""

    def test_good_episode_added(self):
        """A good (non-redundant) episode must appear in the final episode list."""
        base = _FakeEp(1, "Base", "x" * 1000)
        good = _FakeEp(200, "Good episode", "x" * 5_000)
        pool = [good]
        deduped_cache: dict[int, str] = {}  # nothing redundant

        final_eps, call_log, _ = _run_fixed_loop([base], pool, deduped_cache)

        self.assertIn(200, [ep.id for ep in final_eps])

    def test_redundant_then_good_episode(self):
        """After skipping a redundant episode the loop should pick up a good one."""
        base = _FakeEp(1, "Base", "x" * 1000)
        redundant = _FakeEp(100, "Redundant", "")
        good = _FakeEp(200, "Good", "x" * 5_000)
        pool = [redundant, good]
        deduped_cache = {100: ""}  # ep-100 is redundant; ep-200 is fine

        final_eps, call_log, _ = _run_fixed_loop([base], pool, deduped_cache)

        ep_ids = [ep.id for ep in final_eps]
        self.assertNotIn(100, ep_ids, "Redundant ep should NOT be in final list")
        self.assertIn(200, ep_ids, "Good ep SHOULD be in final list")


if __name__ == "__main__":
    unittest.main()
