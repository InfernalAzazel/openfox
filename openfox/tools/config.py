import json
from pathlib import Path
from agno.tools import Toolkit
from json_repair import load as json_repair_load
from openfox.modes.config import Config


class ConfigTools(Toolkit):
    """配置工具：获取配置路径、加载配置、保存配置。"""

    def __init__(self) -> None:
        self.config_path = Path.home() / ".openfox" / "config.json"
        tools = [
            self.get_path,
            self.exists,
            self.exists,
            self.load,
            self.save,
        ]
        super().__init__(name="config", tools=tools)

    def get_path(self) -> str:
        """获取配置文件路径。"""
        return str(self.config_path.resolve())

    def exists(self) -> bool:
        """判断配置文件是否已存在。"""
        return self.config_path.exists()

    def load(self) -> Config:
        """加载配置。从文件读取，若不存在则自动创建默认配置文件并返回。"""

        if self.exists():
            try:
                with open(self.config_path, encoding="utf-8") as f:
                    data = json_repair_load(f)
                return Config.model_validate(data)
            except Exception as e:
                raise ValueError(f"加载配置失败: {e}") from e
                
        return  Config()

    def save(self, config: Config) -> str:
        """保存配置到文件。

        Args:
            config: 配置对象。

        Returns:
            保存结果描述，成功时返回保存路径。
        """
        self.config_path.parent.mkdir(parents=True, exist_ok=True)

        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(config.model_dump(by_alias=False), f, indent=2, ensure_ascii=False)
        return f"配置已保存到 {self.config_path}"
