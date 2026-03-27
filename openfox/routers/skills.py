"""HTTP API for Agno LocalSkills: install/replace/delete via ZIP, list installed."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import NoReturn

from agno.os.settings import AgnoAPISettings
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from openfox.services.skills import (
    MAX_SKILL_ZIP_BYTES,
    SkillExistsError,
    SkillNotFoundError,
    SkillPackageError,
    delete_skill,
    install_skill_from_zip,
    list_installed_skills,
    replace_skill_from_zip,
)
from openfox.tools.config import ConfigTools


def _ensure_zip_upload(file: UploadFile) -> None:
    """Reject non-ZIP uploads (415)."""
    name = (file.filename or "").lower()
    ctype = (file.content_type or "").lower()
    if not name.endswith(".zip") and "zip" not in ctype:
        raise HTTPException(
            status_code=415,
            detail="Only ZIP archives are accepted (.zip)",
        )


async def _persist_uploaded_zip(file: UploadFile) -> Path:
    """Stream upload to a temp file; caller must unlink. Raises HTTPException on limits."""
    _ensure_zip_upload(file)
    data = await file.read()
    if len(data) > MAX_SKILL_ZIP_BYTES:
        max_mib = MAX_SKILL_ZIP_BYTES // (1024 * 1024)
        raise HTTPException(
            status_code=413,
            detail=f"ZIP too large (max {max_mib} MiB)",
        )
    fd, path_str = tempfile.mkstemp(prefix="openfox-skill-", suffix=".zip")
    os.close(fd)
    path = Path(path_str)
    try:
        path.write_bytes(data)
    except OSError:
        path.unlink(missing_ok=True)
        raise
    return path


def _raise_http_for_skill_error(exc: SkillPackageError) -> NoReturn:
    """Map service-layer skill errors to HTTP status codes."""
    if isinstance(exc, SkillExistsError):
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if isinstance(exc, SkillNotFoundError):
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    raise HTTPException(status_code=400, detail=str(exc)) from exc


def get_router(
    tools: ConfigTools,
    settings: AgnoAPISettings,
) -> APIRouter:
    from agno.os.auth import get_authentication_dependency

    router = APIRouter(tags=["OpenFox Skills"])
    auth_dep = get_authentication_dependency(settings)

    @router.get("/expand/skills")
    async def list_skills(_auth: bool = Depends(auth_dep)) -> JSONResponse:
        """Return installed skills under the configured skills path."""
        config = tools.load()
        items = list_installed_skills(config)
        return JSONResponse(
            status_code=200,
            content=[item.model_dump() for item in items],
        )

    @router.post("/expand/skills")
    async def upload_skill(
        file: UploadFile = File(...),
        _auth: bool = Depends(auth_dep),
    ) -> JSONResponse:
        """Install a new skill from ZIP. Returns 409 if the skill folder already exists."""
        tmp = await _persist_uploaded_zip(file)
        try:
            try:
                info = install_skill_from_zip(tmp, tools.load())
            except SkillPackageError as e:
                _raise_http_for_skill_error(e)
        finally:
            tmp.unlink(missing_ok=True)
        return JSONResponse(status_code=201, content=info.model_dump())

    @router.put("/expand/skills/{name}")
    async def replace_skill(
        name: str,
        file: UploadFile = File(...),
        _auth: bool = Depends(auth_dep),
    ) -> JSONResponse:
        """Replace an existing skill; ZIP top-level folder name must match ``name``."""
        tmp = await _persist_uploaded_zip(file)
        try:
            try:
                info = replace_skill_from_zip(tmp, name, tools.load())
            except SkillPackageError as e:
                _raise_http_for_skill_error(e)
        finally:
            tmp.unlink(missing_ok=True)
        return JSONResponse(status_code=200, content=info.model_dump())

    @router.delete("/expand/skills/{name}")
    async def remove_skill(
        name: str,
        _auth: bool = Depends(auth_dep),
    ) -> JSONResponse:
        """Remove an installed skill directory by name."""
        try:
            delete_skill(name, tools.load())
        except SkillPackageError as e:
            _raise_http_for_skill_error(e)
        return JSONResponse(status_code=200, content={"ok": True, "name": name})

    return router
