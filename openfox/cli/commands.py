from __future__ import annotations
import secrets
import typer
import uvicorn
from openfox.schemas.config import Config
from openfox.utils.serving import run_uvicorn_with_web_banner
from openfox.tools.config import ConfigTools

app = typer.Typer(
    name="openfox",
    help="openfox - LLM Agent",
    no_args_is_help=True,
)


def init():
    config_tools = ConfigTools()
    if config_tools.exists():
        typer.secho(f"Config file already exists: {config_tools.get_path()}", fg=typer.colors.YELLOW)
        typer.secho("To re-run setup, delete that file manually, then run this command again.", fg=typer.colors.YELLOW)
        return

    typer.secho("Initializing OpenFox configuration", fg=typer.colors.GREEN, bold=True)

    # Start from built-in defaults (including db_url / db_name); you can edit the file afterward.
    config = Config()

    # Docs
    docs_enabled = typer.prompt(typer.style("Enable API docs? (docs_enabled)", fg=typer.colors.CYAN), default=config.docs_enabled)
    config.docs_enabled = docs_enabled
    typer.secho(f"docs_enabled: {docs_enabled}", fg=typer.colors.MAGENTA)

    # Authorization
    authorization_enabled = typer.prompt(typer.style("Enable authorization? (authorization_enabled)", fg=typer.colors.CYAN), default=config.authorization_enabled)
    config.authorization_enabled = authorization_enabled
    typer.secho(f"authorization_enabled: {authorization_enabled}", fg=typer.colors.MAGENTA)

    # os_security_key
    os_security_key = secrets.token_hex(16)
    config.os_security_key = os_security_key
    typer.secho(f"Generated os_security_key: {os_security_key}", fg=typer.colors.MAGENTA)

    # CORS allowed origins (comma-separated; stored as List[str])
    typer.secho(f"cors_origin_list: {config.cors_origin_list}", fg=typer.colors.MAGENTA)

    # Time zone
    time_zone = typer.prompt(typer.style("Time zone (time_zone)", fg=typer.colors.CYAN), default=config.time_zone)
    config.time_zone = time_zone

    # LLM
    typer.secho("\nLLM settings:", fg=typer.colors.GREEN, bold=True)
    config.llm.model_name = typer.prompt(typer.style("LLM model name (llm.model_name)", fg=typer.colors.CYAN), default=config.llm.model_name)
    config.llm.api_base = typer.prompt(typer.style("LLM API base URL (llm.api_base)", fg=typer.colors.CYAN), default=config.llm.api_base)
    config.llm.api_key = typer.prompt(typer.style("LLM API key (llm.api_key)", fg=typer.colors.CYAN))

    # Feishu (Lark) channel
    typer.secho("\nFeishu (Lark) channel:", fg=typer.colors.GREEN, bold=True)
    feishu = config.channels.feishu
    feishu.app_id = typer.prompt(typer.style("Feishu App ID (channels.feishu.app_id)", fg=typer.colors.CYAN))
    feishu.app_secret = typer.prompt(typer.style("Feishu App Secret (channels.feishu.app_secret)", fg=typer.colors.CYAN))
    feishu.encrypt_key = typer.prompt(typer.style("Feishu Encrypt Key (channels.feishu.encrypt_key)", fg=typer.colors.CYAN))
    feishu.verification_token = typer.prompt(typer.style("Feishu Verification Token (channels.feishu.verification_token)", fg=typer.colors.CYAN))

    config_tools.save(config)
    typer.secho(f"Configuration saved to: {config_tools.get_path()}", fg=typer.colors.GREEN)


@app.command()
def serve(host: str = "0.0.0.0", port: int = 7777) -> None:
    """
    Start the OpenFox HTTP server.
    """
    init()
    # Import after init() so configuration is loaded when the agent starts.
    from openfox.agent import OpenFoxAgent

    openfox_agent = OpenFoxAgent()
    if port != 7777:
        cfg_path = ConfigTools().get_path()
        typer.secho(
            f"Port is {port} (not 7777): add the /web origin to `cors_origin_list` in {cfg_path} "
            f"(e.g. http://127.0.0.1:{port}, http://localhost:{port}) or the embedded web UI may fail CORS.",
            fg=typer.colors.YELLOW,
        )
    uvicorn_config = uvicorn.Config(openfox_agent.app, host=host, port=port)
    run_uvicorn_with_web_banner(uvicorn_config)
