from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from werkzeug.utils import secure_filename


_URL_RE = re.compile(r"^(https?://|file://).+", re.IGNORECASE)


def is_valid_feed_url(url: str) -> bool:
    return bool(url and _URL_RE.match(url.strip()))


def project_root() -> Path:
    # web_ui/ -> project root
    return Path(__file__).parent.parent.resolve()


def digest_instructions_dir() -> Path:
    return project_root() / "digest_instructions"


def save_instruction_upload(file_storage) -> Optional[str]:
    """Save an uploaded instruction file into digest_instructions/.

    Returns the saved filename (not full path), or None if no file provided.
    """
    if not file_storage or not getattr(file_storage, 'filename', ''):
        return None
    filename = secure_filename(file_storage.filename)
    if not filename:
        raise ValueError("Invalid filename")
    # Simple validation: only allow .md or .txt
    if not (filename.lower().endswith(".md") or filename.lower().endswith(".txt")):
        raise ValueError("Instruction file must be .md or .txt")
    target_dir = digest_instructions_dir()
    target_dir.mkdir(parents=True, exist_ok=True)
    dest = target_dir / filename
    file_storage.save(str(dest))
    return filename

