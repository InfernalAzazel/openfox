"""Scheduled-run notifications: in-memory registry and auto-discovery of notifys/*.py plugins."""

from __future__ import annotations

import json
from importlib import import_module
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, Optional

from agno.agent import Agent, RunOutput
from agno.hooks.decorator import hook
from agno.utils.log import logger

ScheduledNotifierFn = Callable[[RunOutput, Dict[str, Any]], Awaitable[None]]

# Maps channel["type"] (e.g. "feishu") to the async handler from each plugin's register tuple.
_notifiers: Dict[str, ScheduledNotifierFn] = {}
_NOTIFYS_DIR = Path(__file__).resolve().parent.parent / "notifys"


def _load_notifys_plugins() -> None:
    """Import every openfox/notifys/*.py module and read register = (type_name, handler)."""
    if not _NOTIFYS_DIR.is_dir():
        return
    for path in sorted(_NOTIFYS_DIR.glob("*.py")):
        stem = path.stem
        # Skip package init and private/helper modules (e.g. _utils.py).
        if stem == "__init__" or stem.startswith("_"):
            continue
        modname = f"openfox.notifys.{stem}"
        try:
            mod = import_module(modname)
        except Exception as e:
            logger.warning(f"scheduled_notify: skip plugin {modname}: {e}")
            continue
        # Plugins expose register = ("channel_type", async_callable).
        reg = getattr(mod, "register", None)
        if reg is None:
            continue
        if (
            isinstance(reg, tuple)
            and len(reg) == 2
            and isinstance(reg[0], str)
            and reg[0]
            and callable(reg[1])
        ):
            _notifiers[reg[0]] = reg[1]
        else:
            logger.warning(f"scheduled_notify: invalid register= in {modname}")


def _coerce_channel_dict(raw: Any) -> Optional[Dict[str, Any]]:
    """Normalize channel from Agent run kwargs: dict as-is, or JSON string from scheduler form POST."""
    if isinstance(raw, dict):
        return raw
    if not isinstance(raw, str) or not (s := raw.strip()):
        return None
    try:
        parsed = json.loads(s)
    except json.JSONDecodeError:
        logger.warning("scheduled_notify: channel string is not valid JSON")
        return None
    return parsed if isinstance(parsed, dict) else None


async def _dispatch_scheduled_notify(run_output: RunOutput, channel: Dict[str, Any]) -> None:
    """Look up handler by channel['type'] and invoke it with the completed run output."""
    ctype = channel.get("type")
    if not isinstance(ctype, str) or not ctype:
        logger.warning("scheduled_notify: channel missing or invalid type")
        return
    fn = _notifiers.get(ctype)
    if fn is None:
        logger.warning(f"scheduled_notify: unsupported channel type={ctype!r}")
        return
    await fn(run_output, channel)


@hook(run_in_background=True)
async def send_notification(run_output: RunOutput, channel: Any = None) -> None:
    """Agent post-hook: notify external channel when a scheduled run includes channel in the request."""
    # Interactive runs (e.g. Feishu webhook) omit channel; scheduled HTTP runs pass channel in the form body.
  
    if not (cd := _coerce_channel_dict(channel)):
        return
    ch_type = cd.get("type")
    try:
        await _dispatch_scheduled_notify(run_output, cd)
        logger.info(f"post_hook: scheduled notify dispatched type={ch_type!r}")
    except Exception as e:
        logger.error(f"post_hook: scheduled notify failed type={ch_type}: {e}")


# Populate _notifiers at import time so handlers exist before any run completes.
_load_notifys_plugins()
