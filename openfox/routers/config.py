"""HTTP API for OpenFox ``~/.openfox/config.json`` (extension to Agno, not core OS)."""

from __future__ import annotations

from agno.os.settings import AgnoAPISettings
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse

from openfox.schemas.config import Config
from openfox.tools.config import ConfigTools


def _load_config(tools: ConfigTools) -> Config:
    """Load and validate config from disk; raise HTTP 500 on parse/load failure."""
    try:
        return tools.load()
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


def _save_config(tools: ConfigTools, config: Config) -> None:
    """Write config to disk; raise HTTP 500 on I/O failure."""
    try:
        tools.save(config)
    except OSError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


def get_router(
    tools: ConfigTools,
    settings: AgnoAPISettings,
) -> APIRouter:
    from agno.os.auth import get_authentication_dependency

    router = APIRouter(tags=["OpenFox"])
    auth_dep = get_authentication_dependency(settings)

    @router.get("/expand/config")
    async def get_config(_auth: bool = Depends(auth_dep)) -> JSONResponse:
        """Return the current OpenFox configuration JSON."""
        model = _load_config(tools)
        return JSONResponse(status_code=200, content=model.model_dump())

    @router.put("/expand/config")
    async def put_config(
        body: Config,
        _auth: bool = Depends(auth_dep),
    ) -> JSONResponse:
        """Replace the on-disk configuration with the request body."""
        _save_config(tools, body)
        return JSONResponse(
            status_code=200,
            content={"path": tools.get_path()},
        )

    return router
