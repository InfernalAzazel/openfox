
from __future__ import annotations
import asyncio
from typing import Any, Awaitable, Callable, Dict, Optional
from agno.utils.log import log_error, log_info, log_warning
from pymongo import ReturnDocument
from openfox.db.agno_mongo import AsyncMongoDb

OnChangeCallback = Callable[[Dict[str, Any], Dict[str, Any]], Awaitable[None]]


class ScheduleNotice:
    """
    Polls the ``schedule_runs`` collection and invokes notification callbacks by run status.

    - Atomically picks one run whose status is ``success`` or ``failed`` and that is not yet notified;
    - Sets ``is_notify`` on that document to avoid duplicate concurrent notifications;
    - Loads the matching ``schedule`` document and passes both into the callback;
    - Callback signature: ``handler(schedule_doc: dict | None, run_doc: dict) -> Awaitable[None]``.
    """

    POLL_INTERVAL_SECONDS = 10

    def __init__(self, db: AsyncMongoDb) -> None:
        """
        Args:
            db: ``AsyncMongoDb`` instance to use.
        """
        self._db = db
        self._handlers: list[OnChangeCallback] = []
        self._task: Optional[asyncio.Task[Any]] = None
        self._stop_event = asyncio.Event()

    def add_handler(self, handler: OnChangeCallback) -> None:
        """Register a handler for schedule run outcomes (e.g. per-channel notification logic)."""
        self._handlers.append(handler)

    async def start(self) -> None:
        """Start the polling loop (idempotent; only one background task is started)."""
        if self._task is not None and not self._task.done():
            return
        self._stop_event.clear()
        self._task = asyncio.create_task(self._watch_loop())
        log_info("ScheduleNotice watcher started")

    async def stop(self) -> None:
        """Stop the polling task and wait for it to exit."""
        self._stop_event.set()
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        log_info("ScheduleNotice watcher stopped")

    async def _watch_loop(self) -> None:
        """Poll ``schedule_runs`` and dispatch success/failure notifications."""
        while not self._stop_event.is_set():
            try:
                schedule_runs_col = await self._db._get_collection(  # type: ignore[attr-defined]
                    table_type="schedule_runs",
                    create_collection_if_not_found=True,
                )

                query = {
                    "status": {"$in": ["success", "failed"]},
                    "is_notify": {"$ne": True},
                }

                run_doc = await schedule_runs_col.find_one_and_update(
                    query,
                    {"$set": {"is_notify": True}},
                    return_document=ReturnDocument.BEFORE,
                )

                if not run_doc:
                    await asyncio.sleep(self.POLL_INTERVAL_SECONDS)
                    continue

                schedule_id = run_doc.get("schedule_id")
                if not schedule_id:
                    continue

                schedule_doc = await self._db.get_schedule(schedule_id)
                handlers = self._handlers if self._handlers else [self._default_on_change]

                for handler in handlers:
                    try:
                        await handler(schedule_doc, run_doc)
                    except Exception as e:
                        log_error(f"ScheduleNotice handler error: {e}")

            except asyncio.CancelledError:
                return
            except Exception as e:
                log_warning(
                    f"ScheduleNotice poll error, retrying in {self.POLL_INTERVAL_SECONDS}s: {e}"
                )

            await asyncio.sleep(self.POLL_INTERVAL_SECONDS)

    async def _default_on_change(
        self,
        schedule_doc: Optional[Dict[str, Any]],
        run_doc: Dict[str, Any],
    ) -> None:
        """Default handler: log only. Callers usually register their own handler (e.g. Feishu)."""
        run_id = run_doc.get("id")
        schedule_id = run_doc.get("schedule_id")
        status = run_doc.get("status")
        if status == "success":
            log_info(
                f"ScheduleNotice successful run: "
                f"schedule_id={schedule_id}, run_id={run_id}, schedule={schedule_doc}"
            )
        elif status == "failed":
            error = run_doc.get("error")
            log_warning(
                f"ScheduleNotice failed run: "
                f"schedule_id={schedule_id}, run_id={run_id}, error={error}, schedule={schedule_doc}"
            )
        else:
            log_info(
                f"ScheduleNotice run update: "
                f"schedule_id={schedule_id}, run_id={run_id}, status={status}, schedule={schedule_doc}"
            )
