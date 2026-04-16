"""HTTP API for OpenFox package version."""

from __future__ import annotations

from agno.os.settings import AgnoAPISettings
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from openfox import __version__


def get_router(settings: AgnoAPISettings) -> APIRouter:
    from agno.os.auth import get_authentication_dependency

    router = APIRouter(tags=["OpenFox"])
    auth_dep = get_authentication_dependency(settings)

    @router.get("/expand/version")
    async def get_version(_auth: bool = Depends(auth_dep)) -> JSONResponse:
        """Return current OpenFox package version."""
        return JSONResponse(status_code=200, content={"version": __version__})

    return router
