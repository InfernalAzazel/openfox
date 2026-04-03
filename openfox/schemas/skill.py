"""API models for installed skills"""

from __future__ import annotations

from pydantic import BaseModel, Field


class SkillInfo(BaseModel):
    """One installed skill as exposed by the HTTP API."""

    activate: bool = Field(
        description=(
            "Whether the skill is active for the agent. "
            "False when the install directory name ends with ``-`` (listed only, not loaded)."
        ),
    )
    name: str
    description: str
    license: str | None = None
    path: str


class SkillActivate(BaseModel):
    """Body for ``PATCH /expand/skills/activate/{name}`` (path = install folder name)."""

    activate: bool = Field(
        description=(
            "``true``: load into the agent; ``false``: disable by appending ``-`` to the folder name (list-only)."
        ),
    )
