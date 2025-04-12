# src/core/agent.py (actualizado)
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
import os
from core.config import AgentConfig
from openai import OpenAI

class Agent(ABC):
    def __init__(self, config: AgentConfig):
        self.config = config
        self.prompt_template = self._load_prompt(self.config.prompt_path)
        self.client = None
        if config.provider == "openai":
            self.client = OpenAI(api_key=config.api_key)
        
    def _load_prompt(self, path: str) -> str:
        if not Path(path).exists():
            raise FileNotFoundError(f"Prompt file not found: {path}")
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
            
    def _save_output(self, content: str, iteration_id: str) -> str:
        Path(self.config.output_dir).mkdir(parents=True, exist_ok=True)
        filename = f"{self.config.name.lower()}-{iteration_id}.txt"
        full_path = os.path.join(self.config.output_dir, filename)
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(content)
        if self.config.verbose:
            print(f"[{self.config.name}] Resultado guardado en: {full_path}")
        return full_path
        
    def _generate_iteration_id(self) -> str:
        return datetime.now().strftime("id-%d%m%Y-%H%M%S")
        
    def _format_prompt(self, **kwargs) -> str:
        return self.prompt_template.format(**kwargs)
        
    @abstractmethod
    def run(self, **kwargs) -> str:
        pass