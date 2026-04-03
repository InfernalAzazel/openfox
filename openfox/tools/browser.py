"""Agent-facing browser tools: CDP launch, health checks, WebSocket URL, and stop.

These wrap :mod:`openfox.utils.chrome` for Agno ``Toolkit`` registration. Return values are
JSON strings so LLM tool calls get structured, parseable text.
"""

from __future__ import annotations
import json
from typing import Any
from agno.tools import Toolkit
from openfox.utils.chrome import (
    DEFAULT_OPENFOX_BROWSER_PROFILE_NAME,
    cdp_url_for_port,
    get_chrome_websocket_url,
    is_chrome_cdp_ready,
    is_chrome_reachable,
    launch_openfox_chrome,
    resolve_openfox_user_data_dir,
    stop_chrome_by_pid,
)


class BrowserTools(Toolkit):
    """Toolkit for local Chromium remote debugging (CDP).

    Exposes launch/reuse flow, HTTP reachability, DevTools WebSocket URL resolution,
    and process shutdown. All tool methods return UTF-8 JSON strings.
    """

    def __init__(self, **kwargs: Any) -> None:
        tools = [
            self.launch_chrome_cdp,
            self.check_chrome_cdp,
            self.get_cdp_websocket_url,
            self.stop_chrome_cdp,
        ]
        super().__init__(name="browser", tools=tools, **kwargs)

    def launch_chrome_cdp(
        self,
        cdp_port: int = 9222,
        headless: bool = False,
        no_sandbox: bool = False,
        profile_name: str = DEFAULT_OPENFOX_BROWSER_PROFILE_NAME,
        extra_args: str | None = None,
        reuse_existing_cdp: bool = True,
        clear_singleton_lock: bool = False,
    ) -> str:
        """Start Chromium with ``--remote-debugging-port``, or reuse CDP already on that port.

        When ``reuse_existing_cdp`` is True and ``http://127.0.0.1:<cdp_port>`` already
        answers ``/json/version``, no new process is started and ``reused_existing`` is True.

        Args:
            cdp_port: TCP port for CDP on loopback. Must be free unless reusing an existing CDP.
            headless: If True, pass Chromium ``--headless=new`` (and ``--disable-gpu``).
            no_sandbox: If True, pass ``--no-sandbox`` / ``--disable-setuid-sandbox`` (common in containers).
            profile_name: Logical profile; data under ``~/.openfox/browser/<name>/user-data``.
            extra_args: Optional single string of extra flags, split on whitespace (e.g. ``"--disable-gpu --blink-settings=..."``).
            reuse_existing_cdp: If True, skip launch when CDP is already reachable on this port.
            clear_singleton_lock: If True, remove Chrome singleton lock files under the profile before launch.
                Safe only when no Chrome instance uses that profile directory.

        Returns:
            JSON object (string) including:

            - ``ok`` (bool)
            - ``reused_existing`` (bool): True when an existing CDP was used
            - ``pid`` (int | null): OS pid of the new browser, or null when reused
            - ``cdp_http_url``: e.g. ``http://127.0.0.1:9222``
            - ``cdp_websocket_url``: DevTools WS URL when available, else null
            - ``deep_ready`` (bool): CDP command over WS succeeded (see ``is_chrome_cdp_ready``)
            - ``user_data_dir``: Absolute ``--user-data-dir`` path
            - ``browser_kind`` (str | null): e.g. ``chrome``, or null when reused
            - ``hint`` (str, optional): Present when ``reused_existing`` is True

        Raises:
            RuntimeError: Propagated from :func:`~openfox.utils.chrome.launch_openfox_chrome` when
                the port is unavailable, no browser binary is found, or CDP never becomes ready.
        """
        cdp_http_url = cdp_url_for_port(cdp_port)
        uds = str(resolve_openfox_user_data_dir(profile_name))
        if reuse_existing_cdp and is_chrome_reachable(cdp_http_url):
            ws_url = get_chrome_websocket_url(cdp_http_url)
            deep = is_chrome_cdp_ready(cdp_http_url) if ws_url else False
            payload: dict[str, Any] = {
                "ok": True,
                "reused_existing": True,
                "pid": None,
                "cdp_http_url": cdp_http_url,
                "cdp_websocket_url": ws_url,
                "deep_ready": deep,
                "user_data_dir": uds,
                "browser_kind": None,
                "hint": "CDP already serves this port; no new browser started. For a fresh instance set reuse_existing_cdp=False, use another port, or stop the process holding the port.",
            }
            return json.dumps(payload, ensure_ascii=False)

        extras: list[str] | None = None
        if extra_args and extra_args.strip():
            extras = extra_args.strip().split()
        running = launch_openfox_chrome(
            cdp_port=cdp_port,
            profile_name=profile_name,
            headless=headless,
            no_sandbox=no_sandbox,
            extra_args=extras,
            clear_singleton_lock=clear_singleton_lock,
        )
        ws_url = get_chrome_websocket_url(cdp_http_url)
        deep = is_chrome_cdp_ready(cdp_http_url) if ws_url else False
        payload = {
            "ok": True,
            "reused_existing": False,
            "pid": running.pid,
            "cdp_http_url": cdp_http_url,
            "cdp_websocket_url": ws_url,
            "deep_ready": deep,
            "user_data_dir": running.user_data_dir,
            "browser_kind": running.exe.kind,
        }
        return json.dumps(payload, ensure_ascii=False)

    def check_chrome_cdp(self, cdp_http_url: str, deep: bool = False) -> str:
        """Probe whether a CDP HTTP endpoint is up; optionally verify a CDP command over WebSocket.

        Args:
            cdp_http_url: Base URL, e.g. ``http://127.0.0.1:9222`` (no path required).
            deep: If True and the endpoint is reachable, also run ``Browser.getVersion`` over WS.

        Returns:
            JSON object (string) with keys:

            - ``reachable`` (bool): ``/json/version`` (or equivalent) succeeded
            - ``cdp_http_url``: Echo of the input URL
            - ``deep_ready`` (bool, optional): Present when ``deep`` is True; WS-level health
        """
        reachable = is_chrome_reachable(cdp_http_url)
        out: dict[str, Any] = {"reachable": reachable, "cdp_http_url": cdp_http_url}
        if deep and reachable:
            out["deep_ready"] = is_chrome_cdp_ready(cdp_http_url)
        return json.dumps(out, ensure_ascii=False)

    def get_cdp_websocket_url(self, cdp_http_url: str) -> str:
        """Fetch ``webSocketDebuggerUrl`` from ``GET /json/version``.

        Args:
            cdp_http_url: CDP HTTP base, e.g. ``http://127.0.0.1:9222``.

        Returns:
            JSON object (string). On success: ``{"ok": true, "cdp_websocket_url": "ws://..."}``.
            On failure: ``{"ok": false, "error": "no webSocketDebuggerUrl", "cdp_http_url": "..."}``.
        """
        ws = get_chrome_websocket_url(cdp_http_url)
        if not ws:
            return json.dumps(
                {"ok": False, "error": "no webSocketDebuggerUrl", "cdp_http_url": cdp_http_url},
                ensure_ascii=False,
            )
        return json.dumps({"ok": True, "cdp_websocket_url": ws}, ensure_ascii=False)

    def stop_chrome_cdp(self, pid: int) -> str:
        """Stop a browser process by pid (tracked launch preferred, else raw ``os.kill``).

        Args:
            pid: Process ID returned by ``launch_chrome_cdp`` in the ``pid`` field (when not reused).

        Returns:
            JSON object (string): ``{"ok": true, "pid": <int>, "message": "stop requested"}``.

        Note:
            If ``pid`` was from a reused CDP session (``reused_existing`` true), stopping it may
            terminate an unrelated browser that happens to own that pid; prefer a dedicated port/profile.
        """
        stop_chrome_by_pid(pid)
        return json.dumps({"ok": True, "pid": pid, "message": "stop requested"}, ensure_ascii=False)