"""
Load and validate config.yaml using Pydantic.
Secrets (API keys) are overlaid from .env via python-dotenv.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import List, Optional

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, Field, field_validator

# Load .env early so os.getenv picks up secrets
load_dotenv()

_CONFIG_PATH = Path(__file__).parent.parent / "config.yaml"


class LLMConfig(BaseModel):
    base_url: str
    api_key: str = Field(default="local-env")
    model: str
    temperature: float = 0.2
    max_tokens: int = 4096

    @field_validator("api_key", mode="before")
    @classmethod
    def overlay_env_key(cls, v: str) -> str:
        """Allow LLM_API_KEY in .env to override config.yaml value."""
        return os.getenv("LLM_API_KEY", v)


class AgentConfig(BaseModel):
    system_prompt: str
    max_iterations: int = 20
    max_file_size_kb: int = 100


class MemoryConfig(BaseModel):
    persist: bool = False
    export_path: str = ".agent_memory"


class FileAccessConfig(BaseModel):
    allowed_roots: List[str] = Field(default_factory=lambda: ["."])


class LoggingConfig(BaseModel):
    level: str = "INFO"
    log_dir: str = "logs"
    max_size_kb: int = 100


class AppConfig(BaseModel):
    llm: LLMConfig
    agent: AgentConfig
    memory: MemoryConfig
    file_access: FileAccessConfig
    logging: LoggingConfig
    # Resolved at load time from the --workspace flag (or cwd fallback).
    # Not read from config.yaml — set by load_config().
    workspace: Path = Field(default_factory=Path.cwd, exclude=True)

    model_config = {"arbitrary_types_allowed": True}

    def resolved_roots(self) -> List[Path]:
        """Return allowed_roots as absolute Paths anchored to workspace."""
        return [
            Path(r).resolve() if Path(r).is_absolute() else (self.workspace / r).resolve()
            for r in self.file_access.allowed_roots
        ]

    def resolved_memory_export_path(self) -> Path:
        """Return the memory export path anchored to workspace."""
        p = Path(self.memory.export_path)
        return p.resolve() if p.is_absolute() else (self.workspace / p).resolve()


def load_config(
    path: Optional[Path] = None,
    workspace: Optional[Path] = None,
) -> AppConfig:
    """Load and validate config.yaml, returning a typed AppConfig.

    Args:
        path: Override path to config.yaml. Defaults to the repo-root config.
        workspace: The working directory the agent should operate on.
                   Defaults to os.getcwd() at call time.
    """
    config_path = path or _CONFIG_PATH
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with config_path.open("r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)

    cfg = AppConfig.model_validate(raw)
    cfg.workspace = (workspace or Path.cwd()).resolve()
    return cfg
