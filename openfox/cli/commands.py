
from __future__ import annotations
import typer
import uvicorn
from openfox.utils.agent import OpenMeshAgent


app = typer.Typer(
    name="openfox",
    help="openfox - 简单的终端 LLM Agent",
    no_args_is_help=True,
)


@app.command()
def agent() -> None:
    """
    与 LLM Agent 交互（交互式 REPL）。
    """
    pass


@app.command()
def serve() -> None:
    """
    启动 HTTP 服务（FastAPI + uvicorn）。
    """
    openfox_agent = OpenMeshAgent()
    uvicorn.run(openfox_agent.app, host="0.0.0.0", port=7777)





