"""Skills install path helpers for the core agent runtime."""

from __future__ import annotations

import shutil
from pathlib import Path

from openfox.utils.const import OPENFOX_HOME_PATH, SKILLS_PATH

# Packaged defaults: ``openfox/skills`` next to ``openfox.core``.
_BUNDLED_SKILLS = Path(__file__).resolve().parent.parent / "skills"


def ensure_skills_from_bundle() -> None:
    """If ``SKILLS_PATH`` does not exist, copy packaged ``openfox/skills`` into it.

    If the bundle directory is missing, creates an empty ``SKILLS_PATH`` so loaders
    still see a valid directory.
    """
    if SKILLS_PATH.exists():
        return
    OPENFOX_HOME_PATH.mkdir(parents=True, exist_ok=True)
    if _BUNDLED_SKILLS.is_dir():
        shutil.copytree(
            _BUNDLED_SKILLS,
            SKILLS_PATH,
            ignore=shutil.ignore_patterns(".DS_Store", "__pycache__"),
        )
    else:
        SKILLS_PATH.mkdir(parents=True, exist_ok=True)
