"""Serve the Vite-built UI from ``openfox/static/web`` at ``/web``."""

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

# ``__file__`` is ``.../openfox/utils/web_static.py``; static bundle lives in ``openfox/static/web``.
WEB_STATIC_ROOT = Path(__file__).resolve().parent.parent / "static" / "web"


def install_web_routes(app: FastAPI) -> None:
    """Serve built Vue assets under /web without StaticFiles.

    Agno's TrailingSlashMiddleware strips ``/web/`` to ``/web``. That interacts badly
    with Starlette's ``redirect_slashes`` and StaticFiles' directory-index redirect,
    causing an infinite 307 loop. Explicit routes avoid trailing-slash redirects.
    """

    root = WEB_STATIC_ROOT.resolve()

    @app.get("/web", include_in_schema=False)
    @app.get("/web/", include_in_schema=False)
    async def _web_index():
        index = root / "index.html"
        if not index.is_file():
            raise HTTPException(status_code=404)
        return FileResponse(index)

    @app.get("/web/{resource_path:path}", include_in_schema=False)
    async def _web_asset(resource_path: str):
        if resource_path == "" or ".." in resource_path.split("/"):
            raise HTTPException(status_code=404)
        target = (root / resource_path).resolve()
        try:
            target.relative_to(root)
        except ValueError:
            raise HTTPException(status_code=404)
        if target.is_file():
            return FileResponse(target)
        index = root / "index.html"
        if index.is_file():
            return FileResponse(index)
        raise HTTPException(status_code=404)
