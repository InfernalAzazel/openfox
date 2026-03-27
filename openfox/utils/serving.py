"""HTTP serving helpers.

Agno AgentOS registers a custom FastAPI ``lifespan``; in that mode FastAPI does not run
``@app.on_event("startup")`` handlers. To print the bundled ``/web`` URL next to Uvicorn’s
bind line, we append it from :meth:`uvicorn.server.Server._log_started_message`.
"""

from __future__ import annotations

import logging
import sys
from collections.abc import Sequence
import socket
from uvicorn.config import Config
from uvicorn.main import STARTUP_FAILURE
from uvicorn.server import Server

_log = logging.getLogger("uvicorn.error")


class UvicornServerWithWebBanner(Server):
    """Uvicorn server that logs one extra INFO line for ``/web`` after the default bind banner."""

    def __init__(self, config: Config, *, web_banner_host: str, web_banner_port: int) -> None:
        super().__init__(config)
        self._web_banner_host = web_banner_host
        self._web_banner_port = web_banner_port

    def _log_started_message(self, listeners: Sequence[socket.SocketType]) -> None:
        super()._log_started_message(listeners)
        _log.info(
            "OpenFox web UI: http://%s:%s/web",
            self._web_banner_host,
            self._web_banner_port,
        )

def run_uvicorn_with_web_banner(config: Config) -> None:
    """Run Uvicorn with the bundled ``/web`` banner (uses ``config.host`` / ``config.port``)."""

    banner_host = config.host if config.host is not None else "0.0.0.0"
    server = UvicornServerWithWebBanner(
        config, web_banner_host=banner_host, web_banner_port=config.port
    )
    try:
        server.run()
    except KeyboardInterrupt:
        pass
    if not server.started:
        sys.exit(STARTUP_FAILURE)
