from pydantic import Field
from pydantic_settings import BaseSettings
from typing import List

class FeishuConfig(BaseSettings):
    """飞书通道配置。"""
    app_id: str = Field(default="", description="飞书开放平台 App ID")
    app_secret: str = Field(default="", description="飞书开放平台 App Secret")
    encrypt_key: str = Field(default="", description="事件订阅加密密钥")
    verification_token: str = Field(default="", description="事件订阅校验 Token")

class LLMConfig(BaseSettings):
    """LLM 配置。"""
    model_name: str = Field(default="deepseek/deepseek-chat", description="模型名称")
    api_base: str = Field(default="https://api.deepseek.com", description="API 基础 URL")
    api_key: str = Field(default="", description="API 密钥")

class ChannelsConfig(BaseSettings):
    """通道配置。"""
    feishu: FeishuConfig = Field(default_factory=FeishuConfig)

class MCPServerConfig(BaseSettings):
    """MCP server 连接配置（stdio 或 HTTP）"""
    name: str = Field(default="", description="配置名称")
    command: str = Field(default="", description="命令")
    args: list[str] = Field(default_factory=list, description="命令参数")
    env: dict[str, str] = Field(default_factory=dict, description="环境变量")
    url: str = Field(default="", description="HTTP 端点 URL")
    headers: dict[str, str] = Field(default_factory=dict, description="HTTP 自定义头部")
    tool_timeout: int = Field(default=30, description="工具调用超时时间")

class Config(BaseSettings):
    """配置。"""
    agent_id: str = Field(default="OpenFox", description="Agent ID")
    skills_path: str = Field(default="openfox/skills", description="技能路径")
    time_zone: str = Field(default="Asia/Shanghai", description="时区")
    token: str = Field(default="", description="OpenFox HTTP 服务访问令牌")
    db_url: str = Field(default="mongodb://test:test@127.0.0.1:27017", description="MongoDB 连接 URL")
    db_name: str = Field(default="openfox", description="MongoDB 数据库名称")
    llm: LLMConfig = Field(default_factory=LLMConfig, description="LLM 配置")
    channels: ChannelsConfig = Field(default_factory=ChannelsConfig, description="通道配置")
    mcps: List[MCPServerConfig] = Field(default_factory=list, description="MCP server 连接配置")
