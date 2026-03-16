from __future__ import annotations
import secrets
import typer
import uvicorn
from pymongo import MongoClient
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
    
    # 是否启用文档
    docs_enabled = typer.prompt(typer.style("是否启用文档 (docs_enabled)", fg=typer.colors.CYAN), default=config.docs_enabled)
    config.docs_enabled = docs_enabled
    typer.secho(f"是否启用文档: {docs_enabled}", fg=typer.colors.MAGENTA)

    # 是否启用授权
    authorization_enabled = typer.prompt(typer.style("是否启用授权 (authorization_enabled)", fg=typer.colors.CYAN), default=config.authorization_enabled)
    config.authorization_enabled = authorization_enabled
    typer.secho(f"是否启用授权: {authorization_enabled}", fg=typer.colors.MAGENTA)

    # 生成 os_security_key
    os_security_key = secrets.token_hex(16)
    config.os_security_key = os_security_key
    typer.secho(f"生成 os_security_key: {os_security_key}", fg=typer.colors.MAGENTA)

    # CORS 允许的源列表（逗号分隔，内部仍然存 List[str]）
    cors_origin_input = typer.prompt(
        typer.style("CORS 允许的源列表 (cors_origin_list, 用逗号分隔, 默认 * 表示所有源)", fg=typer.colors.CYAN),
        default=["*"],
    )
    config.cors_origin_list = [origin.strip() for origin in cors_origin_input.split(",") if origin.strip()]
  
    # 时区
    time_zone = typer.prompt(typer.style("时区 (time_zone)", fg=typer.colors.CYAN), default=config.time_zone)
    config.time_zone = time_zone

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
    # 必须在 init() 之后导入 OpenMeshAgent，否则会读取不到配置
    from openfox.utils.agent import OpenMeshAgent
    openfox_agent = OpenMeshAgent()
    uvicorn.run(openfox_agent.app, host=host, port=port)