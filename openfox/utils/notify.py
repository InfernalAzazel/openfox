"""Scheduled-run notifications: in-memory registry and auto-discovery of channels/*.py handlers."""

from __future__ import annotations

import json
import inspect
from importlib import import_module
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, Optional

from agno.agent import RunOutput
from agno.hooks.decorator import hook
from agno.utils.log import logger

ScheduledNotifierFn = Callable[[RunOutput, Dict[str, Any]], Awaitable[None]]

# Maps channel["type"] (e.g. "feishu") to async notifier handlers discovered in channels modules.
_notifiers: Dict[str, ScheduledNotifierFn] = {}
_CHANNELS_DIR = Path(__file__).resolve().parent.parent / "channels"


def _build_class_notifier(cls: type) -> ScheduledNotifierFn:
    """
    Build a notifier wrapper around `Class.on_notify_scheduled`.

    The channel instance is created lazily at first notification dispatch.
    """
    instance: Any = None

    async def _wrapped(run_output: RunOutput, channel: Dict[str, Any]) -> None:
        nonlocal instance
        if instance is None:
            try:
                instance = cls()
            except Exception as e:
                raise RuntimeError(
                    f"scheduled_notify: cannot init {cls.__module__}.{cls.__name__}: {e}"
                ) from e
        await instance.on_notify_scheduled(run_output, channel)

    return _wrapped


def _load_channel_notifiers() -> None:
    """
    Import every openfox/channels/*.py module and discover class notifier handlers.
    """
    if not _CHANNELS_DIR.is_dir():
        return
    for path in sorted(_CHANNELS_DIR.glob("*.py")):
        stem = path.stem
        # Skip package init, base abstractions, and private/helper modules.
        if stem in {"__init__", "base"} or stem.startswith("_"):
            continue
        modname = f"openfox.channels.{stem}"
        try:
            mod = import_module(modname)
        except Exception as e:
            logger.warning(f"scheduled_notify: skip channel module {modname}: {e}")
            continue

        # Only detect class method on_notify_scheduled(...)
        found = False
        for _, obj in inspect.getmembers(mod, inspect.isclass):
            if obj.__module__ != mod.__name__:
                continue
            method = getattr(obj, "on_notify_scheduled", None)
            if callable(method):
                _notifiers[stem] = _build_class_notifier(obj)
                found = True
                break
        if not found:
            logger.warning(f"scheduled_notify: no on_notify_scheduled found in {modname}")


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
_load_channel_notifiers()
