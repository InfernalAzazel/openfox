from __future__ import annotations
import secrets
import typer
import uvicorn
from pymongo import MongoClient
from openfox.utils.agent import OpenMeshAgent
from openfox.tools.config import ConfigTools
from openfox.modes.config import Config


app = typer.Typer(
    name="openfox",
    help="openfox - LLM Agent",
    no_args_is_help=True,
)


def init():
    config_tools = ConfigTools()
    if config_tools.exists():
        typer.secho(f"配置文件已存在：{config_tools.get_path()}", fg=typer.colors.YELLOW)
        typer.secho("如需重新初始化，请手动删除该文件后再运行。", fg=typer.colors.YELLOW)
        return

    typer.secho("🦊 初始化 OpenFox 配置", fg=typer.colors.GREEN, bold=True)

    # 使用内置默认值初始化配置
    config = Config()

    # MongoDB 配置
    config.db_url = typer.prompt(typer.style("MongoDB 连接字符串 (db_url)", fg=typer.colors.CYAN), default=config.db_url)
    config.db_name = typer.prompt(typer.style("MongoDB 数据库名称 (db_name)", fg=typer.colors.CYAN), default=config.db_name)

    # 检测 MongoDB 是否可用
    typer.secho("检测 MongoDB 连接中...", fg=typer.colors.BLUE)
    try:
        client = MongoClient(config.db_url, serverSelectionTimeoutMS=3000)
        client.admin.command("ping")
        typer.secho("✅ MongoDB 连接成功。", fg=typer.colors.GREEN)
    except Exception as e:  # noqa: BLE001
        typer.secho("⚠️ MongoDB 连接失败，请检查连接字符串。", fg=typer.colors.RED)
        typer.secho(
            "你可以参考 MongoDB 官方连接字符串文档："
            "https://www.mongodb.com/docs/manual/reference/connection-string/",
            fg=typer.colors.YELLOW,
        )
        return
    
    # 生成token
    token = secrets.token_hex(16)
    config.token = token
    typer.secho(f"生成 token: {token}", fg=typer.colors.MAGENTA)

    # LLM 配置
    typer.secho("\n配置 LLM：", fg=typer.colors.GREEN, bold=True)
    config.llm.model_name = typer.prompt(typer.style("LLM 模型名称 (llm.model_name)", fg=typer.colors.CYAN),default=config.llm.model_name)
    config.llm.api_base = typer.prompt(typer.style("LLM API Base URL (llm.api_base)", fg=typer.colors.CYAN),default=config.llm.api_base)
    config.llm.api_key = typer.prompt(typer.style("LLM API Key (llm.api_key)", fg=typer.colors.CYAN))

    # 飞书配置
    typer.secho("\n配置飞书通道：", fg=typer.colors.GREEN, bold=True)
    feishu = config.channels.feishu
    feishu.app_id = typer.prompt(typer.style("飞书 App ID (channels.feishu.app_id)", fg=typer.colors.CYAN))
    feishu.app_secret = typer.prompt(typer.style("飞书 App Secret (channels.feishu.app_secret)", fg=typer.colors.CYAN))
    feishu.encrypt_key = typer.prompt(typer.style("飞书 Encrypt Key (channels.feishu.encrypt_key)", fg=typer.colors.CYAN))
    feishu.verification_token = typer.prompt(typer.style("飞书 Verification Token (channels.feishu.verification_token)", fg=typer.colors.CYAN))

    # 保存最终配置
    config_tools.save(config)
    typer.secho(f"配置文件已保存到：{config_tools.get_path()}", fg=typer.colors.GREEN)
    

@app.command()
def serve(host: str = "0.0.0.0", port: int = 7777) -> None:
    """
    启动 OpenFox HTTP 服务。
    """
    init()
    openfox_agent = OpenMeshAgent()
    uvicorn.run(openfox_agent.app, host=host, port=port)





