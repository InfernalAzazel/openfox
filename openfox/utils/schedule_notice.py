
from __future__ import annotations
import asyncio
from typing import Any, Awaitable, Callable, Dict, Optional
from agno.utils.log import log_error, log_info, log_warning
from pymongo import ReturnDocument
from openfox.db.agno_mongo import AsyncMongoDb

OnChangeCallback = Callable[[Dict[str, Any], Dict[str, Any]], Awaitable[None]]

class ScheduleNotice:
    """
    轮询 `schedule_runs` 集合，根据执行状态触发通知回调。

    - 每次从 `schedule_runs` 中原子地取出一条尚未通知且状态为 "success"/"failed" 的记录；
    - 将该记录的 `is_notify` 字段置为 True，避免并发重复通知；
    - 查出对应的 `schedule` 文档，一并传入回调；
    - 回调签名：handler(run_doc: dict, schedule_doc: dict | None) -> Awaitable[None]。
    """

    POLL_INTERVAL_SECONDS = 10  # 轮询间隔秒数

    def __init__(self, db: AsyncMongoDb) -> None:
        """初始化通知器。

        Args:
            db: 使用的 AsyncMongoDb 实例。
        """
        self._db = db
        # 支持多个回调，便于适配多种通道/侧向逻辑
        self._handlers: list[OnChangeCallback] = []
        self._task: Optional[asyncio.Task[Any]] = None
        self._stop_event = asyncio.Event()

    def add_handler(self, handler: OnChangeCallback) -> None:
        """注册调度结果回调（例如不同 IM 通道的通知逻辑）。"""
        self._handlers.append(handler)

    async def start(self) -> None:
        """启动轮询任务（幂等，多次调用只会启动一个后台任务）。"""
        if self._task is not None and not self._task.done():
            return
        self._stop_event.clear()
        self._task = asyncio.create_task(self._watch_loop())
        log_info("计划通知监视器已启动")

    async def stop(self) -> None:
        """停止轮询任务并等待退出。"""
        self._stop_event.set()
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        log_info("ScheduleNotice 观察者已停止")

    async def _watch_loop(self) -> None:
        """通过轮询 `schedule_runs` 实现成功/失败通知。"""
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
                        log_error(f"ScheduleNotice 回调异常: {e}")

            except asyncio.CancelledError:
                return
            except Exception as e:
                log_warning(f"ScheduleNotice 轮询异常，将在 {self.POLL_INTERVAL_SECONDS} 秒后重试: {e}")

            # 间隔轮询
            await asyncio.sleep(self.POLL_INTERVAL_SECONDS)

    async def _default_on_change(
        self,
        schedule_doc: [Dict[str, Any]],
        run_doc: Dict[str, Any],
        
    ) -> None:
        """
        默认通知实现：仅打日志。

        上层通常会在构造时传入自己的 on_change 回调（如发送飞书通知）。
        """
        run_id = run_doc.get("id")
        schedule_id = run_doc.get("schedule_id")
        status = run_doc.get("status")
        if status == "success":
            log_info(
                f"ScheduleNotice 捕获到成功调度: "
                f"schedule_id={schedule_id}, run_id={run_id}, schedule={schedule_doc}"
            )
        elif status == "failed":
            error = run_doc.get("error")
            log_warning(
                f"ScheduleNotice 捕获到失败调度: "
                f"schedule_id={schedule_id}, run_id={run_id}, error={error}, schedule={schedule_doc}"
            )
        else:
            log_info(
                f"ScheduleNotice 捕获到调度变更: "
                f"schedule_id={schedule_id}, run_id={run_id}, status={status}, schedule={schedule_doc}"
            )


