from agno.agent import Agent
from agno.db.sqlite import AsyncSqliteDb
from agno.models.litellm import LiteLLM
from agno.os import AgentOS
from agno.os.settings import AgnoAPISettings
from agno.scheduler import ScheduleManager
from agno.skills import Skills

from openfox.core.skills import ensure_skills_from_bundle
from openfox.core.tools import build_openfox_toolkits
from openfox.interfaces.feishu import Feishu
from openfox.schemas.config import toolkit_filter_kwargs
from openfox.routers import config
from openfox.routers import skills
from openfox.tools.config import ConfigTools
from openfox.tools.feishu import FeishuTools
from openfox.tools.mcp_config import MCPConfigTools
from openfox.utils.const import DB_PATH, SKILLS_PATH
from openfox.utils.notify import send_notification
from openfox.utils.skills import LocalSkills
from openfox.utils.web_static import install_web_routes

# Work around agno ScheduleManager: on interpreter exit, __del__ may run without `_pool` set.
ScheduleManager.close = lambda self: (getattr(self, "_pool", None) and (self._pool.shutdown(wait=False), setattr(self, "_pool", None)))


class OpenFoxAgent:
    """Wires OpenFox config, storage, tools, and AgentOS runtime."""
    
    def __init__(self):
        self.config_tools = ConfigTools()
        self.config = self.config_tools.load()
        self.feishu_tools = FeishuTools()
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        ensure_skills_from_bundle()
        self.db = AsyncSqliteDb(db_file=str(DB_PATH))
        self.schedule_mgr = ScheduleManager(self.db)

        self.instructions = [
            "当用户要求定时或周期执行任务时使用 CronTools.create。",
            "用户说「每X帮我做Y」时：将「每X」映射为 cron_expr（例如每分钟→* * * * *）。",
            "将「帮我做Y」整句作为 message：message 是到点时 Agent 要执行的任务正文（可含工具调用），不要包含时间或周期描述。",
            "从用户文本中自动提取创建定时任务所需的参数（cron_expr、message、channel、timezone）。",
            "当用户询问有哪些定时任务时使用 CronTools.list。",
            "若技能文档给出 CLI 示例，必须使用 run_shell 执行。",
            "当用户希望通过聊天配置 MCP 时，使用 mcp_config 工具。",
            f"默认时区为 {self.config.time_zone}。",
        ]

        tools_list = build_openfox_toolkits(
            self.config_tools,
            self.schedule_mgr,
            self.feishu_tools,
        )

        self.agent = Agent(
            id=self.config.agent_id,
            model=LiteLLM(
                id=self.config.llm.model_name,
                api_key=self.config.llm.api_key,
                api_base=self.config.llm.api_base,
            ),
            tools=tools_list,
            skills=Skills(loaders=[LocalSkills(str(SKILLS_PATH))]),
            db=self.db,
            markdown=True,
            post_hooks=[send_notification],
        )

        settings = AgnoAPISettings(
            os_security_key=self.config.os_security_key,
            docs_enabled=self.config.docs_enabled,
            cors_origin_list=self.config.cors_origin_list,
        )

        self.os = AgentOS(
            name=self.config.agent_id,
            agents=[self.agent],
            interfaces=[Feishu(agent=self.agent)],
            db=self.db,
            scheduler=True,
            scheduler_poll_interval=15,
            settings=settings,
        )
        self.app = self.os.get_app()
        self.app.include_router(config.get_router(self.config_tools, settings))
        self.app.include_router(skills.get_router(self.agent, settings))
        install_web_routes(self.app)