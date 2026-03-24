from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo
from agno.scheduler import ScheduleManager
from agno.tools import Toolkit
from agno.utils.log import logger
from sqlalchemy import Engine


class CronTools(Toolkit):
    def __init__(self, endpoint: str, schedule_mgr: ScheduleManager, **kwargs: Any):
        self.endpoint = endpoint
        self.schedule_mgr = schedule_mgr
        tools = [self.create, self.list, self.get, self.delete, self.disable]
        super().__init__(name="cron_tools", tools=tools, **kwargs)

    async def create(
        self,
        name: str,
        cron_expr: str,
        message: str,
        channel: dict,
        timezone: str = "Asia/Shanghai",
    ) -> str:
        """
        Create a scheduled (cron) task.

        When the user says something like "every X do Y for me": X is the schedule (e.g. every minute, 9:00 daily)
        → map it to cron_expr; Y is what to run at that time → use as message.
        message is the full instruction sent to this Agent when the job fires; the Agent runs from that message
        (skills may be triggered). Do not put schedule wording like "every X" inside message.

        Args:
            name: Task name, unique identifier (may be inferred by the agent).
            cron_expr: Standard five-field cron (minute hour day month weekday), e.g. "* * * * *" every minute,
                "0 9 * * *" daily at 9:00 (confirm with the user).
            message: Message sent to the agent at run time (confirm with the user), e.g. "Summarize https://example.com".
            channel: Channel for the agent at run time, e.g. {"type": "feishu", "open_id": "open_id", "chat_id": "chat_id"}.
            timezone: Time zone; default Asia/Shanghai.
        """
        logger.info(
            "create_schedule: name=%s cron_expr=%s message=%s timezone=%s"
            % (name, cron_expr, message, timezone)
        )
        if not channel:
            return "channel is required"
        payload = {"message": message, "channel": channel}

        try:
            schedule = await self.schedule_mgr.acreate(
                name=name,
                cron=cron_expr,
                endpoint=self.endpoint,
                method="POST",
                payload=payload,
                timezone=timezone,
                if_exists="update",
            )
        except (ValueError, RuntimeError) as e:
            logger.warning(f"create_schedule failed: {e}")
            return f"Failed to create schedule: {e}"

        if schedule is None:
            logger.error("create_schedule returned no schedule")
            return "Failed to create schedule: no schedule returned"

        tz_name = schedule.timezone or timezone
        next_ts = schedule.next_run_at
        if next_ts is None:
            when = "next run unknown"
        else:
            try:
                dt = datetime.fromtimestamp(int(next_ts), tz=ZoneInfo(tz_name))
                when = f"{dt.strftime('%Y-%m-%d %H:%M:%S %Z')} (epoch {next_ts})"
            except Exception:
                when = f"epoch {next_ts} (timezone {tz_name})"

        return (
            f"Schedule created successfully. schedule_id={schedule.id} name={schedule.name!r} "
            f"next_run={when}"
        )

    async def list(self) -> str:
        """List scheduled tasks."""
        schedules = await self.schedule_mgr.alist(enabled=True)
        logger.info("list_schedule: schedules=%s" % (schedules,))
        return f"Scheduled tasks: {schedules}"

    async def get(self, schedule_id: str) -> str:
        """Get a scheduled task."""
        schedule = await self.schedule_mgr.aget(schedule_id)
        logger.info("get_schedule: schedule_id=%s" % (schedule_id,))
        return f"Scheduled task: {schedule}"

    async def delete(self, schedule_id: str) -> str:
        """
        Delete a scheduled task.

        Call list first to obtain schedule_id.
        """
        await self.schedule_mgr.adelete(schedule_id)
        logger.info("delete_schedule: schedule_id=%s" % (schedule_id,))
        return f"delete_schedule: schedule_id={schedule_id}"

    async def disable(self, schedule_id: str) -> str:
        """
        Disable a scheduled task.

        Call list first to obtain schedule_id.
        """
        await self.schedule_mgr.adisable(schedule_id)
        logger.info("disable_schedule: schedule_id=%s" % (schedule_id,))
        return f"disable_schedule: schedule_id={schedule_id}"
