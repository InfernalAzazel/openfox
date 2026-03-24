import json
from pathlib import Path
from agno.tools import Toolkit
from json_repair import load as json_repair_load
from openfox.schemas.config import Config


class ConfigTools(Toolkit):
    """Config helpers: path, existence check, load, and save."""

    def __init__(self) -> None:
        self.config_path = Path.home() / ".openfox" / "config.json"
        tools = [
            self.get_path,
            self.exists,
            self.load,
            self.save,
        ]
        super().__init__(name="config", tools=tools)

    def get_path(self) -> str:
        """Return the config file path."""
        return str(self.config_path.resolve())

    def exists(self) -> bool:
        """Return whether the config file exists."""
        return self.config_path.exists()

    def load(self) -> Config:
        """Load config from disk. If missing, returns defaults (no file written)."""

        if self.exists():
            try:
                with open(self.config_path, encoding="utf-8") as f:
                    data = json_repair_load(f)
                return Config.model_validate(data)
            except Exception as e:
                raise ValueError(f"Failed to load config: {e}") from e

        return Config()

    def save(self, config: Config) -> str:
        """Persist config to the config file.

        Args:
            config: Config model instance.

        Returns:
            Human-readable result; on success includes the saved path.
        """
        self.config_path.parent.mkdir(parents=True, exist_ok=True)

        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(config.model_dump(by_alias=False), f, indent=2, ensure_ascii=False)
        return f"Config saved to {self.config_path}"
