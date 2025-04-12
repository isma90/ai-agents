# src/core/config.py

from dataclasses import dataclass

@dataclass
class AgentConfig:
    name: str
    provider: str  # Ej: "openai", "anthropic", etc.
    api_key: str
    model: str     # Ej: "gpt-4o-mini", "claude-3-sonnet"
    prompt_path: str
    verbose: bool = True
    output_dir: str = "outputs"
