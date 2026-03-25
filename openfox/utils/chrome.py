"""Launch a local Chromium-based browser with Chrome DevTools Protocol (CDP).

Use HTTP (e.g. ``http://127.0.0.1:9222/json/version``) and WebSockets for automation.
Behaviour mirrors OpenClaw's ``chrome.ts``: resolve executable, build flags, optional
profile bootstrap, poll until CDP is up, stop the process.

Notes:
    - Default ``user-data-dir`` is ``~/.openfox/browser/<profile>/user-data``, isolated
      from the user's normal Chrome profile.
    - No SSRF checks; intended only for loopback debugging.
"""

from __future__ import annotations

import asyncio
import json
import os
import signal
import shutil
import socket
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx
import websockets

# --- Timeouts and diagnostics (same unit: seconds, except CHROME_STDERR_HINT_MAX in bytes) ---
# Magnitudes follow OpenClaw cdp-timeouts.

CHROME_REACHABILITY_TIMEOUT_S = 5.0  # HTTP /json/version fetch or raw WS probe
CHROME_LAUNCH_READY_POLL_S = 0.1  # Sleep between polls while waiting for CDP after spawn
CHROME_LAUNCH_READY_WINDOW_S = 30.0  # Total budget for post-spawn CDP to become reachable
CHROME_WS_READY_TIMEOUT_S = 5.0  # DevTools WS connect + Browser.getVersion round trip
CHROME_BOOTSTRAP_PREFS_TIMEOUT_S = 15.0  # New profile: wait for Local State + Default/Preferences
CHROME_BOOTSTRAP_EXIT_TIMEOUT_S = 5.0  # After bootstrap SIGTERM, wait for process exit
CHROME_STOP_TIMEOUT_S = 10.0  # After stop SIGTERM, wait before SIGKILL
CHROME_STDERR_HINT_MAX = 4000  # Launch failure: append at most this many stderr chars

DEFAULT_OPENFOX_BROWSER_PROFILE_NAME = "default"

# Relative path segments / static tuples (used with os.path / profile cleanup)

_WIN_SUFFIX = os.path.join("Google", "Chrome", "Application", "chrome.exe")

_CHROME_SINGLETON_FILES = ("SingletonLock", "SingletonSocket", "SingletonCookie")

# --- Per-platform resolution: each tuple is (kind, absolute path or PATH executable name) ---

_MAC_CANDIDATES: list[tuple[str, str]] = [
    ("chrome", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
    ("chromium", "/Applications/Chromium.app/Contents/MacOS/Chromium"),
    ("edge", "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"),
    ("brave", "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser"),
]

_LINUX_WHICH: list[tuple[str, str]] = [
    ("chrome", "google-chrome-stable"),
    ("chrome", "google-chrome"),
    ("chromium", "chromium"),
    ("chromium", "chromium-browser"),
    ("brave", "brave-browser"),
    ("edge", "microsoft-edge"),
    ("edge", "microsoft-edge-stable"),
]


@dataclass(frozen=True)
class BrowserExecutable:
    """Resolved Chromium-family browser binary.

    Attributes:
        kind: Short label (e.g. ``chrome``, ``chromium``, ``edge``, ``brave``).
        path: Absolute path to the executable on disk.
    """

    kind: str
    path: str


@dataclass
class RunningChrome:
    """Handle for a successfully started browser process.

    Pass to ``stop_openfox_chrome`` for graceful shutdown.

    Attributes:
        pid: Operating-system process ID (``-1`` if unknown).
        exe: Which browser binary was launched.
        user_data_dir: Chrome ``--user-data-dir`` path in use.
        cdp_port: ``--remote-debugging-port`` value.
        started_at: ``time.time()`` when the main process was spawned.
        proc: Subprocess handle; stderr may still be open until the process exits.
    """

    pid: int
    exe: BrowserExecutable
    user_data_dir: str
    cdp_port: int
    started_at: float
    proc: subprocess.Popen[bytes]


# Launches from this module are registered for graceful stop (SIGTERM + CDP-unreachable probe).
_RUNNING: dict[int, RunningChrome] = {}


def resolve_openfox_user_data_dir(profile_name: str = DEFAULT_OPENFOX_BROWSER_PROFILE_NAME) -> Path:
    """Return the Chrome ``user-data-dir`` for a logical OpenFox profile.

    Args:
        profile_name: Subdirectory name under ``~/.openfox/browser/``; defaults to
            ``DEFAULT_OPENFOX_BROWSER_PROFILE_NAME``.

    Returns:
        Path to ``~/.openfox/browser/<profile_name>/user-data`` (not guaranteed to exist).
    """
    return Path.home() / ".openfox" / "browser" / profile_name / "user-data"


def clear_profile_process_singleton(user_data_dir: str | Path) -> list[str]:
    """Remove Chrome process-singleton files under ``user-data-dir``.

    Call only when no window is using this profile. Stale locks after a crash cause
    ``SingletonLock: File exists`` on the next launch.

    Args:
        user_data_dir: Chrome profile root (the directory passed as ``--user-data-dir``).

    Returns:
        Names of lock files successfully removed (e.g. ``\"SingletonLock\"``); empty if none.
    """
    root = Path(user_data_dir)
    removed: list[str] = []
    for name in _CHROME_SINGLETON_FILES:
        path = root / name
        try:
            if path.exists() or path.is_symlink():
                path.unlink(missing_ok=True)
                removed.append(name)
        except OSError:
            pass
    return removed


def _exists(path: str | Path) -> bool:
    """Return True if ``path`` is an existing regular file.

    Args:
        path: Filesystem path (used to detect ``Local State``, ``Preferences``, etc.).

    Returns:
        True if the path exists and is a file; False on missing path or OS errors.
    """
    try:
        return Path(path).is_file()
    except OSError:
        return False


def cdp_url_for_port(cdp_port: int) -> str:
    """Build the HTTP base URL for a local CDP endpoint.

    Args:
        cdp_port: TCP port where ``--remote-debugging-port`` listens (loopback).

    Returns:
        String ``http://127.0.0.1:<cdp_port>`` (no trailing path).
    """
    return f"http://127.0.0.1:{cdp_port}"


def ensure_port_available(port: int, host: str = "127.0.0.1") -> None:
    """Verify that ``host:port`` can be bound (port is free for Chrome to use).

    Args:
        port: TCP port number to check.
        host: Address to bind for the probe; default loopback ``127.0.0.1``.

    Raises:
        RuntimeError: If the port is already in use or cannot be bound.
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((host, port))
    except OSError as e:
        raise RuntimeError(f"Port {port} on {host} is not available: {e}") from e
    finally:
        s.close()


def find_browser_executable() -> BrowserExecutable | None:
    """Locate a supported Chromium-based browser on the current OS.

    Returns:
        ``BrowserExecutable`` for the first match in predefined paths / ``PATH``;
        ``None`` if nothing was found.
    """
    plat = sys.platform
    if plat == "darwin":
        for kind, p in _MAC_CANDIDATES:
            if Path(p).is_file():
                return BrowserExecutable(kind=kind, path=p)
        return None
    if plat.startswith("linux"):
        for kind, name in _LINUX_WHICH:
            resolved = shutil.which(name)
            if resolved:
                return BrowserExecutable(kind=kind, path=resolved)
        return None
    if plat == "win32":
        pf = os.environ.get("PROGRAMFILES", r"C:\Program Files")
        pf_x86 = os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)")
        for base in {pf, pf_x86}:
            candidate = os.path.join(base, _WIN_SUFFIX)
            if os.path.isfile(candidate):
                return BrowserExecutable(kind="chrome", path=candidate)
        edge = os.path.join(pf_x86, "Microsoft", "Edge", "Application", "msedge.exe")
        if os.path.isfile(edge):
            return BrowserExecutable(kind="edge", path=edge)
        return None
    return None


def build_chrome_launch_args(
    *,
    cdp_port: int,
    user_data_dir: str | Path,
    headless: bool = False,
    no_sandbox: bool = False,
    extra_args: list[str] | None = None,
) -> list[str]:
    """Build argv flags for launching the browser (CDP, profile isolation, noise reduction).

    Args:
        cdp_port: Value for ``--remote-debugging-port``.
        user_data_dir: Value for ``--user-data-dir`` (string or path-like).
        headless: When True, append ``--headless=new`` and ``--disable-gpu``.
        no_sandbox: When True, append ``--no-sandbox`` and ``--disable-setuid-sandbox``.
        extra_args: Optional extra Chromium arguments appended as-is.

    Returns:
        List of command-line strings starting with debug/profile flags, then optional extras.
    """
    args: list[str] = [
        f"--remote-debugging-port={cdp_port}",
        f"--user-data-dir={user_data_dir}",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-sync",
        "--disable-background-networking",
        "--disable-component-update",
        "--disable-features=Translate,MediaRouter",
        "--disable-session-crashed-bubble",
        "--hide-crash-restore-bubble",
        "--password-store=basic",
    ]
    if headless:
        args.append("--headless=new")
        args.append("--disable-gpu")
    if no_sandbox:
        args.append("--no-sandbox")
        args.append("--disable-setuid-sandbox")
    if sys.platform.startswith("linux"):
        args.append("--disable-dev-shm-usage")
    if extra_args:
        args.extend(extra_args)
    return args


def _append_cdp_path(cdp_url: str, path: str) -> str:
    """Resolve ``path`` against the CDP HTTP base URL.

    Args:
        cdp_url: Base such as ``http://127.0.0.1:9222`` (with or without trailing slash).
        path: Relative segment, e.g. ``json/version``.

    Returns:
        Absolute URL string suitable for HTTP GET.
    """
    base = cdp_url if cdp_url.endswith("/") else cdp_url + "/"
    return urljoin(base, path.lstrip("/"))


def _normalize_ws_url(ws_url: str, cdp_http_url: str) -> str:
    """Normalize WebSocket URL host/port to match the HTTP endpoint used for probing.

    Args:
        ws_url: Value of ``webSocketDebuggerUrl`` from ``/json/version``.
        cdp_http_url: Base HTTP URL that was used to fetch the version document.

    Returns:
        Possibly rewritten ``ws://...`` string; unchanged if host is not loopback.
    """
    ws_url = ws_url.strip()
    if not ws_url:
        return ws_url
    p_ws = urlparse(ws_url)
    p_http = urlparse(cdp_http_url)
    if p_ws.hostname in ("localhost", "127.0.0.1") and p_http.hostname:
        host = p_http.hostname or "127.0.0.1"
        port = p_ws.port or p_http.port or 9222
        path = p_ws.path or ""
        query = f"?{p_ws.query}" if p_ws.query else ""
        return f"ws://{host}:{port}{path}{query}"
    return ws_url


def fetch_chrome_version_json(cdp_url: str, timeout_s: float = CHROME_REACHABILITY_TIMEOUT_S) -> dict[str, Any] | None:
    """GET ``/json/version`` from a CDP HTTP endpoint.

    Args:
        cdp_url: CDP base URL (http) or any prefix ``_append_cdp_path`` accepts.
        timeout_s: HTTP client timeout in seconds.

    Returns:
        Parsed JSON object on success; ``None`` on network/HTTP errors or non-object JSON.
    """
    version_url = _append_cdp_path(cdp_url, "json/version")
    try:
        with httpx.Client(timeout=timeout_s) as client:
            r = client.get(version_url)
            r.raise_for_status()
            data = r.json()
            if not isinstance(data, dict):
                return None
            return data
    except Exception:
        return None


def is_chrome_reachable(cdp_url: str, timeout_s: float = CHROME_REACHABILITY_TIMEOUT_S) -> bool:
    """Cheap health check: HTTP version endpoint or raw WebSocket URL.

    Args:
        cdp_url: If it starts with ``ws``, only a WebSocket connect is attempted; otherwise
            ``fetch_chrome_version_json`` must succeed.
        timeout_s: Per-attempt timeout (HTTP or WebSocket handshake).

    Returns:
        True if the endpoint responds as expected; False otherwise.
    """
    if cdp_url.strip().lower().startswith("ws"):
        return asyncio.run(_can_open_websocket(cdp_url.strip(), timeout_s))
    return fetch_chrome_version_json(cdp_url, timeout_s) is not None


async def _can_open_websocket(url: str, timeout_s: float) -> bool:
    """Try to open and close a WebSocket (no CDP commands).

    Args:
        url: Full ``ws://`` or ``wss://`` URL.
        timeout_s: Connect / handshake timeout in seconds.

    Returns:
        True if the connection succeeded; False on any error.
    """
    try:
        async with asyncio.timeout(max(timeout_s, 0.5)):
            async with websockets.connect(url, open_timeout=timeout_s) as ws:
                await ws.close()
    except Exception:
        return False
    return True


def get_chrome_websocket_url(cdp_url: str, timeout_s: float = CHROME_REACHABILITY_TIMEOUT_S) -> str | None:
    """Resolve the DevTools WebSocket URL for automation.

    Args:
        cdp_url: HTTP CDP base or already a ``ws://`` URL (returned unchanged after strip).
        timeout_s: Timeout for fetching ``/json/version`` when using HTTP.

    Returns:
        Normalized ``ws://...`` string, or ``None`` if missing or unreachable.
    """
    u = cdp_url.strip()
    if u.lower().startswith("ws"):
        return u
    version = fetch_chrome_version_json(u, timeout_s)
    if not version:
        return None
    raw = str(version.get("webSocketDebuggerUrl") or "").strip()
    if not raw:
        return None
    return _normalize_ws_url(raw, u)


async def _cdp_browser_get_version_ok(ws_url: str, handshake_timeout_s: float) -> bool:
    """Run CDP ``Browser.getVersion`` over an existing DevTools WebSocket.

    Args:
        ws_url: Browser-level WebSocket endpoint from ``webSocketDebuggerUrl``.
        handshake_timeout_s: Timeout for connect, send, and waiting for message id ``1``.

    Returns:
        True if a response with ``id == 1`` and dict ``result`` is received.
    """
    try:
        async with asyncio.timeout(max(handshake_timeout_s, 0.2) + 1.0):
            async with websockets.connect(ws_url, open_timeout=handshake_timeout_s) as ws:
                await ws.send(json.dumps({"id": 1, "method": "Browser.getVersion"}))
                while True:
                    raw = await asyncio.wait_for(ws.recv(), timeout=handshake_timeout_s)
                    try:
                        msg = json.loads(raw)
                    except json.JSONDecodeError:
                        continue
                    if msg.get("id") == 1:
                        res = msg.get("result")
                        return isinstance(res, dict)
    except Exception:
        return False


def is_chrome_cdp_ready(
    cdp_url: str,
    reach_timeout_s: float = CHROME_REACHABILITY_TIMEOUT_S,
    ws_timeout_s: float = CHROME_WS_READY_TIMEOUT_S,
) -> bool:
    """Stricter than ``is_chrome_reachable``: HTTP up plus one successful CDP command over WS.

    Args:
        cdp_url: HTTP CDP base (e.g. ``http://127.0.0.1:9222``).
        reach_timeout_s: Timeout for ``get_chrome_websocket_url`` (HTTP phase).
        ws_timeout_s: Timeout for the WebSocket ``Browser.getVersion`` round trip.

    Returns:
        True if both HTTP and CDP-over-WS checks succeed.
    """
    ws_url = get_chrome_websocket_url(cdp_url, reach_timeout_s)
    if not ws_url:
        return False
    return asyncio.run(_cdp_browser_get_version_ok(ws_url, ws_timeout_s))


def _spawn_chrome(exe: BrowserExecutable, args: list[str]) -> subprocess.Popen[bytes]:
    """Start ``exe.path`` with ``args``; stdin/stdout discarded, stderr captured.

    Args:
        exe: Browser binary to execute.
        args: Chromium flags (excluding argv0; caller builds full flag list).

    Returns:
        ``Popen`` instance with ``stderr=PIPE`` for diagnostic reads on failure.
    """
    return subprocess.Popen(
        [exe.path, *args],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        env={**os.environ, "HOME": str(Path.home())},
    )


def _wait_prefs_bootstrap(proc: subprocess.Popen[bytes], user_data_dir: Path) -> None:
    """Wait for default profile files, then terminate the bootstrap Chrome process.

    Args:
        proc: Bootstrap ``Popen`` from ``_spawn_chrome``.
        user_data_dir: Profile root where ``Local State`` and ``Default/Preferences`` should appear.
    """
    local_state = user_data_dir / "Local State"
    preferences = user_data_dir / "Default" / "Preferences"
    deadline = time.monotonic() + CHROME_BOOTSTRAP_PREFS_TIMEOUT_S
    while time.monotonic() < deadline:
        if _exists(local_state) and _exists(preferences):
            break
        time.sleep(0.1)
    try:
        proc.terminate()
    except ProcessLookupError:
        pass
    exit_deadline = time.monotonic() + CHROME_BOOTSTRAP_EXIT_TIMEOUT_S
    while time.monotonic() < exit_deadline:
        if proc.poll() is not None:
            break
        time.sleep(0.05)


def launch_openfox_chrome(
    *,
    cdp_port: int,
    profile_name: str = DEFAULT_OPENFOX_BROWSER_PROFILE_NAME,
    headless: bool = False,
    no_sandbox: bool = False,
    extra_args: list[str] | None = None,
    clear_singleton_lock: bool = False,
) -> RunningChrome:
    """Start browser on a free port and wait until CDP responds; register in ``_RUNNING``.

    Args:
        cdp_port: Remote debugging port (must be unused).
        profile_name: Logical name; resolves to ``~/.openfox/browser/<name>/user-data``.
        headless: Use Chromium ``headless=new``.
        no_sandbox: Often required in containers / root on Linux.
        extra_args: Additional Chromium flags.
        clear_singleton_lock: If True, delete singleton lock files first (only when no instance
            uses this profile).

    Returns:
        ``RunningChrome`` registered in ``_RUNNING``; use ``stop_openfox_chrome`` to stop.

    Raises:
        RuntimeError: If no browser binary is found, the port is unavailable, or CDP never becomes ready.
    """
    ensure_port_available(cdp_port)
    exe = find_browser_executable()
    if not exe:
        raise RuntimeError(
            "No supported browser found (Chrome/Brave/Edge/Chromium on macOS, Linux, or Windows)."
        )

    user_data_dir = resolve_openfox_user_data_dir(profile_name)
    user_data_dir.mkdir(parents=True, exist_ok=True)
    if clear_singleton_lock:
        clear_profile_process_singleton(user_data_dir)
    uds = str(user_data_dir)

    local_state = user_data_dir / "Local State"
    preferences = user_data_dir / "Default" / "Preferences"
    needs_bootstrap = not _exists(local_state) or not _exists(preferences)

    # First use of this dir: Chrome may not create Default prefs immediately; one short run stabilizes.
    if needs_bootstrap:
        boot_args = build_chrome_launch_args(
            cdp_port=cdp_port,
            user_data_dir=uds,
            headless=headless,
            no_sandbox=no_sandbox,
            extra_args=extra_args,
        )
        bootstrap = _spawn_chrome(exe, boot_args)
        _wait_prefs_bootstrap(bootstrap, user_data_dir)

    started_at = time.time()
    args = build_chrome_launch_args(
        cdp_port=cdp_port,
        user_data_dir=uds,
        headless=headless,
        no_sandbox=no_sandbox,
        extra_args=extra_args,
    )
    proc = _spawn_chrome(exe, args)

    stderr_chunks: list[bytes] = []

    # Drain stderr in a thread so the pipe cannot fill and block the child; use tail on errors only.
    def pump_stderr() -> None:
        if not proc.stderr:
            return
        try:
            while True:
                chunk = proc.stderr.read(4096)
                if not chunk:
                    break
                stderr_chunks.append(chunk)
        except Exception:
            pass

    threading.Thread(target=pump_stderr, daemon=True).start()

    cdp_http = cdp_url_for_port(cdp_port)
    ready_deadline = time.monotonic() + CHROME_LAUNCH_READY_WINDOW_S
    while time.monotonic() < ready_deadline:
        if is_chrome_reachable(cdp_http):
            break
        time.sleep(CHROME_LAUNCH_READY_POLL_S)

    if not is_chrome_reachable(cdp_http):
        err = b"".join(stderr_chunks).decode("utf-8", errors="replace").strip()
        hint = f"\nChrome stderr:\n{err[:CHROME_STDERR_HINT_MAX]}" if err else ""
        sandbox_hint = ""
        if sys.platform.startswith("linux") and not no_sandbox:
            sandbox_hint = (
                "\nHint: If running in a container or as root, try launch with no_sandbox=True."
            )
        try:
            proc.kill()
        except ProcessLookupError:
            pass
        raise RuntimeError(
            f"Failed to start Chrome CDP on port {cdp_port} for profile {profile_name!r}.{sandbox_hint}{hint}"
        )

    pid = proc.pid or -1
    running = RunningChrome(
        pid=pid,
        exe=exe,
        user_data_dir=uds,
        cdp_port=cdp_port,
        started_at=started_at,
        proc=proc,
    )
    _RUNNING[pid] = running
    return running


def stop_openfox_chrome(
    running: RunningChrome,
    timeout_s: float = CHROME_STOP_TIMEOUT_S,
    probe_timeout_s: float = CHROME_REACHABILITY_TIMEOUT_S,
) -> None:
    """Stop a browser started via this module: SIGTERM, then optional SIGKILL.

    Args:
        running: Handle returned by ``launch_openfox_chrome``.
        timeout_s: Max seconds after SIGTERM before SIGKILL.
        probe_timeout_s: HTTP timeout for each ``is_chrome_reachable`` check while waiting
            for CDP to go away (confirms the browser actually exited).
    """
    proc = running.proc
    if proc.poll() is not None:
        _RUNNING.pop(running.pid, None)
        return
    try:
        proc.terminate()
    except ProcessLookupError:
        pass

    start = time.monotonic()
    cdp_http = cdp_url_for_port(running.cdp_port)
    while time.monotonic() - start < timeout_s:
        if proc.poll() is not None:
            _RUNNING.pop(running.pid, None)
            return
        if not is_chrome_reachable(cdp_http, probe_timeout_s):
            _RUNNING.pop(running.pid, None)
            return
        time.sleep(0.1)

    try:
        proc.kill()
    except ProcessLookupError:
        pass
    _RUNNING.pop(running.pid, None)


def stop_chrome_by_pid(pid: int, timeout_s: float = CHROME_STOP_TIMEOUT_S) -> None:
    """Stop Chrome by PID: prefer tracked ``RunningChrome``, else bare ``os.kill``.

    Args:
        pid: Process ID to stop.
        timeout_s: Same meaning as in ``stop_openfox_chrome`` / wait before SIGKILL for untracked PIDs.
    """
    running = _RUNNING.get(pid)
    if running is not None:
        stop_openfox_chrome(running, timeout_s=timeout_s)
        return
    try:
        os.kill(pid, getattr(signal, "SIGTERM", 15))
    except ProcessLookupError:
        return
    except OSError:
        return
    t0 = time.monotonic()
    probe = 0.3
    while time.monotonic() - t0 < timeout_s:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return
        time.sleep(probe)
    try:
        os.kill(pid, getattr(signal, "SIGKILL", 9))
    except ProcessLookupError:
        pass
    except OSError:
        pass
