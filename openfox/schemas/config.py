from pydantic import Field
from pydantic_settings import BaseSettings
from typing import List


class FeishuConfig(BaseSettings):
    """Feishu (Lark) channel settings."""

    app_id: str = Field(default="", description="Feishu Open Platform app ID")
    app_secret: str = Field(default="", description="Feishu Open Platform app secret")
    encrypt_key: str = Field(default="", description="Event subscription encrypt key")
    verification_token: str = Field(default="", description="Event subscription verification token")


class LLMConfig(BaseSettings):
    """LLM settings."""

    model_name: str = Field(default="deepseek/deepseek-chat", description="Model name")
    api_base: str = Field(default="https://api.deepseek.com", description="API base URL")
    api_key: str = Field(default="", description="API key")


class ChannelsConfig(BaseSettings):
    """Channel integrations."""

    feishu: FeishuConfig = Field(default_factory=FeishuConfig)


class MCPServerConfig(BaseSettings):
    """MCP server connection (stdio or HTTP)."""

    name: str = Field(default="", description="Config display name")
    command: str = Field(default="", description="Command (stdio transport)")
    args: list[str] = Field(default_factory=list, description="Command arguments")
    env: dict[str, str] = Field(default_factory=dict, description="Environment variables")
    url: str = Field(default="", description="HTTP endpoint URL")
    headers: dict[str, str] = Field(default_factory=dict, description="HTTP custom headers")
    tool_timeout: int = Field(default=30, description="Tool call timeout in seconds")


class Config(BaseSettings):
    """Application configuration."""

    agent_id: str = Field(default="OpenFox", description="Agent ID")
    skills_path: str = Field(default="openfox/skills", description="Skills directory path")
    docs_enabled: bool = Field(default=True, description="Enable API docs")
    authorization_enabled: bool = Field(default=True, description="Enable authorization")
    os_security_key: str = Field(default="", description="AgentOS security key")
    cors_origin_list: List[str] = Field(default_factory=list, description="Allowed CORS origins")
    time_zone: str = Field(default="Asia/Shanghai", description="Default timezone")
    db_url: str = Field(default="mongodb://test:test@127.0.0.1:27017", description="MongoDB connection URL")
    db_name: str = Field(default="openfox", description="MongoDB database name")
    llm: LLMConfig = Field(default_factory=LLMConfig, description="LLM settings")
    channels: ChannelsConfig = Field(default_factory=ChannelsConfig, description="Channel integrations")
    mcps: List[MCPServerConfig] = Field(default_factory=list, description="MCP server connections")
