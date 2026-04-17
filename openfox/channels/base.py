from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Union

from agno.agent import Agent, RunOutput
from agno.agent.remote import RemoteAgent
from agno.team.remote import RemoteTeam
from agno.team.team import Team
from agno.workflow import RemoteWorkflow, Workflow

class BaseChannel(ABC):
    """Base class for all message channels."""

    @abstractmethod
    def __init__(
        self,
        agent: Optional[Union[Agent, RemoteAgent]] = None,
        team: Optional[Union[Team, RemoteTeam]] = None,
        workflow: Optional[Union[Workflow, RemoteWorkflow]] = None,
    ):
        self.type: str = None
        raise NotImplementedError

    @abstractmethod
    def start(self):
        raise NotImplementedError

    @abstractmethod
    async def on_notify_scheduled(run_output: RunOutput, channel: Dict[str, Any]) -> None:
        raise NotImplementedError