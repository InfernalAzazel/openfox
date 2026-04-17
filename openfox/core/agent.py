from agno.agent import Agent
from agno.db.sqlite import AsyncSqliteDb
from agno.models.litellm import LiteLLM
from agno.os import AgentOS
from agno.os.settings import AgnoAPISettings
from agno.skills import Skills
from openfox.core.knowledge import build_knowledge
from openfox.core.lifespan import app_lifespan
from openfox.core.skills import ensure_skills_from_bundle
from openfox.core.tools import build_openfox_toolkits
from openfox.routers import config
from openfox.routers import skills
from openfox.routers import version
from openfox.tools.config import ConfigTools
from openfox.utils.const import DB_PATH, SKILLS_PATH
from openfox.utils.notify import send_notification
from openfox.utils.skills import LocalSkills
from openfox.utils.web_static import install_web_routes
from agno.tracing import setup_tracing

class OpenFoxAgent:
    """Wires OpenFox config, storage, tools, and AgentOS runtime."""
    
    def __init__(self):

        self.config_tools = ConfigTools()
        self.config = self.config_tools.load()
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        ensure_skills_from_bundle()
        self.db = AsyncSqliteDb(db_file=str(DB_PATH))
        setup_tracing(self.db)
        self.knowledge = build_knowledge(self.config, self.db)

        self.instructions = [
            # default timezone is set in config.json
            f"The default timezone is {self.config.time_zone}.",
            # When the user wants to create a scheduled/periodic task (create_schedule, etc.) and a channel appears in the context：
            (
                'When the user EXPLICITLY requests to create a recurring or scheduled task'
               '(e.g. using clear intent like "schedule", "remind", "repeat", "every day", etc.),'
                'and a `channel` object appears in the context:',
                '- You MUST include a `channel` field in the schedule payload JSON.',
                '- The value of `channel` MUST match the provided context object exactly (copy it verbatim).',
                'If the user does NOT explicitly request scheduling or recurring behavior:',
                '- DO NOT create any schedule.',
                '- DO NOT infer or assume scheduling intent.',
                '- DO NOT generate any schedule-related payload.',
            ),
            # mcp config tool
            "When the user wants to configure MCP through chat, use the mcp_config tool.",
        ]

        tools_list = build_openfox_toolkits(
            self.db,
            self.config_tools,
        )

        self.agent = Agent(
            id=self.config.agent_id,
            model=LiteLLM(
                id=self.config.llm.model_name,
                api_key=self.config.llm.api_key,
                api_base=self.config.llm.api_base,
            ),
            instructions=self.instructions,
            tools=tools_list,
            skills=Skills(loaders=[LocalSkills(str(SKILLS_PATH))]),
            db=self.db,
            markdown=True,
            add_history_to_context=True,
            num_history_runs=3,
            update_memory_on_run=True,
            knowledge=self.knowledge if self.config.search_knowledge else None,
            search_knowledge=self.config.search_knowledge,
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
            db=self.db,
            scheduler=True,
            scheduler_poll_interval=15,
            settings=settings,
            lifespan=app_lifespan,
        )
        self.app = self.os.get_app()
        self.app.state.openfox_agent = self
        self.app.include_router(config.get_router(self.config_tools, settings))
        self.app.include_router(skills.get_router(self.agent, settings))
        self.app.include_router(version.get_router(settings))
        install_web_routes(self.app)