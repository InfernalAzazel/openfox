"""API models for installed skills (content 校验以 Agno ``validate_skill_directory`` 为准)."""

from __future__ import annotations

from pydantic import BaseModel


class SkillInfo(BaseModel):
    """One installed skill as exposed by the HTTP API."""

    name: str
    description: str
    license: str | None = None
    path: str
