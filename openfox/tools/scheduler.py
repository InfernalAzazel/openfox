from agno.scheduler import ScheduleManager
from agno.tools import Toolkit
from agno.utils.log import logger


class CronTools(Toolkit):
    def __init__(self, endpoint: str, schedule_mgr: ScheduleManager, **kwargs):
        self.endpoint = endpoint
        self.schedule_mgr = schedule_mgr
        tools = [
            self.create,
            self.list,
            self.delete,
            self.disable,
        ]
        super().__init__(name="cron_tools", tools=tools, **kwargs)

    async def create(
        self,
        name: str,
        cron_expr: str,
        message: str,
        channel: dict = {},
        timezone: str = "Asia/Shanghai",
    ) -> str:
        """
        创建定时任务。

        当用户说「每X帮我做Y」时：X 是周期（如每分钟、每天9点）→ 转为 cron_expr；Y 是到点要执行的动作 → 作为 message。
        message 是到点时发给本 Agent 的完整指令，Agent 会按这条消息执行（可触发技能）。message 里不要包含「每X」等时间描述。

        参数:
            name: 任务名称，唯一标识（可由 agent 推断）
            cron_expr: cron 五段式（分 时 日 月 周），如 "* * * * *" 每分钟，"0 9 * * *" 每天 9:00（需用户确认）
            message: 到点发送给 agent 的消息（需用户确认），例如 "帮我总结 https://example.com"
            channel: 到点发送给 agent 的频道，例如 {"type": "feishu", "open_id": "open_id", "chat_id": "chat_id"}
            timezone: 时区，默认 Asia/Shanghai
        """
        logger.info(f"create_schedule: name={name}, cron_expr={cron_expr}, message={message}, timezone={timezone}")
        await self.schedule_mgr.acreate(
                name=name,
                cron=cron_expr,
                endpoint=self.endpoint,
                method="POST",
                payload={"message": message, "channel": channel},
                timezone=timezone,
                if_exists="update",
            )
        return f"定时任务创建成功"

    async def list(self) -> str:
        """
        获取定时任务列表。
        """
        schedules = await self.schedule_mgr.alist(enabled=True)
        return f"定时任务列表: {schedules}"

    async def delete(self, schedule_id: str) -> str:
        """
        删除定时任务
        - 需要先调用 list 方法获取 schedule_id
        """
        await self.schedule_mgr.adelete(schedule_id)
        return f"定时任务删除成功"

    async def disable(self, schedule_id: str) -> str:
        """
        禁用定时任务
        - 需要先调用 list 方法获取 schedule_id
        """
        await self.schedule_mgr.adisable(schedule_id)
        return f"定时任务禁用成功"
