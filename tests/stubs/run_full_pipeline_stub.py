"""Lightweight test stub for the legacy ``run_full_pipeline`` module.

The production repository no longer ships the original CLI runner, but the
pytest suite still references it for regression coverage.  This stub provides a
minimal implementation so that CLI and discovery tests can execute without
requiring the full operational dependencies (database, TTS providers, etc.).
"""

from __future__ import annotations

import argparse
import logging
from calendar import timegm
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Optional

import requests


class _FeedparserModule:
    """Tiny feedparser replacement used solely for testing."""

    class _Result:
        entries: List[Any]

        def __init__(self) -> None:
            self.entries = []

    def parse(self, _url: str) -> "_FeedparserModule._Result":
        return _FeedparserModule._Result()


feedparser = _FeedparserModule()


@dataclass
class _EpisodeRecord:
    """In-memory episode placeholder used by the stub repository."""

    episode_guid: str
    title: str = ""


class EpisodeRepositoryStub:
    """Simple repository that mimics the project interface for tests."""

    def __init__(self) -> None:
        self._episodes: Dict[str, _EpisodeRecord] = {}

    def get_by_episode_guid(self, guid: str) -> Optional[_EpisodeRecord]:
        return self._episodes.get(guid)

    def create(self, episode: _EpisodeRecord) -> str:
        self._episodes[episode.episode_guid] = episode
        return episode.episode_guid


def get_episode_repo(_manager: Any = None) -> EpisodeRepositoryStub:
    """Return a stub repository (patched in tests when real one is required)."""

    return EpisodeRepositoryStub()


def get_digest_repo(_manager: Any = None) -> None:
    return None


def get_feed_repo(_manager: Any = None) -> None:
    return None


class FeedParser:
    """Drop-in replacement with the same interface as the real parser."""

    def parse_feed(self, feed_url: str) -> _FeedparserModule._Result:
        return feedparser.parse(feed_url)


class FullPipelineRunner:
    """Test-friendly implementation of the legacy CLI runner."""

    def __init__(
        self,
        log_file: Optional[str] = None,
        phase_stop: Optional[str] = None,
        dry_run: bool = False,
        limit: Optional[int] = None,
        days_back: int = 7,
        episode_guid: Optional[str] = None,
        verbose: bool = False,
    ) -> None:
        self.log_file = log_file
        self.phase_stop = phase_stop
        self.dry_run = dry_run
        self.limit = limit
        self.days_back = days_back
        self.episode_guid = episode_guid
        self.verbose = verbose
        self.max_episodes_per_run = 3
        self.rss_feeds: List[Dict[str, Any]] = []
        self.feed_parser = FeedParser()
        self.episode_repo = get_episode_repo()
        self.logger = logging.getLogger(__name__)

        if verbose:
            logging.getLogger(__name__).setLevel(logging.DEBUG)

        if dry_run:
            print("DRY RUN MODE: Pipeline will not modify data")
        if limit is not None:
            print(f"LIMIT: Processing max {limit} episodes")
        if days_back is not None:
            print(f"TIMEFRAME: Processing episodes from last {days_back} days")

    # ------------------------------------------------------------------
    # CLI helper behaviour
    # ------------------------------------------------------------------
    def run_pipeline(self) -> List[Dict[str, Any]]:
        return self.discover_new_episodes()

    # ------------------------------------------------------------------
    # Discovery utilities
    # ------------------------------------------------------------------
    def discover_new_episodes(self) -> List[Dict[str, Any]]:
        """Return candidate episodes based on the configured state."""

        if self.episode_guid:
            episode = self.episode_repo.get_by_episode_guid(self.episode_guid)
            if episode:
                if self.dry_run:
                    title = getattr(episode, "title", self.episode_guid)
                    print(f"DRY RUN: Would process episode '{title}' ({self.episode_guid})")
                    return []
                return [episode]
            return []

        results: List[Dict[str, Any]] = []
        max_results = self.limit or self.max_episodes_per_run
        cutoff = None
        if self.days_back is not None:
            cutoff = datetime.now(timezone.utc) - timedelta(days=self.days_back)

        for feed in self.rss_feeds:
            feed_url = feed.get("url", "")
            try:
                requests.get(feed_url, timeout=5)
            except Exception:
                # Network errors are ignored in the stub – the caller can inspect
                # returned results to determine success.
                pass

            parsed = feedparser.parse(feed_url)
            entries = getattr(parsed, "entries", [])
            for entry in entries:
                candidate = self._normalise_entry(entry, feed)
                guid = candidate.get("guid")
                if not guid:
                    continue

                if cutoff and candidate["published"] and candidate["published"] < cutoff:
                    continue

                if self.episode_repo.get_by_episode_guid(guid):
                    continue

                results.append(candidate)
                if len(results) >= max_results:
                    break

            if len(results) >= max_results:
                break

        return results

    # ------------------------------------------------------------------
    @staticmethod
    def _normalise_entry(entry: Any, feed: Dict[str, Any]) -> Dict[str, Any]:
        """Convert a feedparser entry or mock into a predictable dictionary."""

        def _get(obj: Any, key: str, default: Any = None) -> Any:
            if hasattr(obj, "get"):
                try:
                    return obj.get(key, default)
                except Exception:
                    return default
            return getattr(obj, key, default)

        title = _get(entry, "title", "")
        summary = _get(entry, "summary", "")
        guid = _get(entry, "id") or _get(entry, "guid") or _get(entry, "link")

        published_dt: Optional[datetime] = None
        published_parsed = getattr(entry, "published_parsed", None)
        if published_parsed:
            try:
                published_dt = datetime.fromtimestamp(timegm(published_parsed), tz=timezone.utc)
            except Exception:
                published_dt = None

        audio_url = FullPipelineRunner._extract_audio_url(entry)

        return {
            "title": title,
            "summary": summary,
            "guid": guid,
            "published": published_dt,
            "audio_url": audio_url,
            "feed": feed,
        }

    @staticmethod
    def _extract_audio_url(entry: Any) -> Optional[str]:
        links: Iterable[Any] = getattr(entry, "links", []) or getattr(entry, "enclosures", [])
        for link in links:
            href = getattr(link, "href", None)
            link_type = getattr(link, "type", None)
            if isinstance(link, dict):
                href = link.get("href")
                link_type = link.get("type")
            if href and (not link_type or "audio" in link_type):
                return href
        return None


def main(argv: Optional[List[str]] = None) -> None:
    """Entry point mirroring the historical CLI interface."""

    parser = argparse.ArgumentParser(description="Run the podcast pipeline")
    parser.add_argument("--dry-run", action="store_true", help="Run without side effects")
    parser.add_argument("--limit", type=int, default=None, help="Maximum episodes to process")
    parser.add_argument("--days-back", type=int, default=7, help="Only consider episodes within X days")
    parser.add_argument("--episode-guid", default=None, help="Process a specific episode by GUID")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    parser.add_argument("--phase", dest="phase", default=None, help="Stop after a specific phase")
    parser.add_argument("--log", dest="log", default=None, help="Log file path")

    args = parser.parse_args(argv)

    runner = FullPipelineRunner(
        log_file=args.log,
        phase_stop=args.phase,
        dry_run=args.dry_run,
        limit=args.limit,
        days_back=args.days_back,
        episode_guid=args.episode_guid,
        verbose=args.verbose,
    )

    runner.run_pipeline()


__all__ = [
    "FeedParser",
    "FullPipelineRunner",
    "EpisodeRepositoryStub",
    "feedparser",
    "get_episode_repo",
    "main",
]
