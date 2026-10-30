"""
Load and validate config.yaml using Pydantic.
Secrets (API keys) are overlaid from .env via python-dotenv.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import List, Literal, Optional

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
    max_tokens: int = 32000
    # Reasoning depth for Ollama/OpenAI-compatible servers. Sent as the
    # `reasoning_effort` extra_body key — a string enum, NOT a token count.
    # "none" disables thinking; "low"/"medium"/"high"/"max" scale it.
    thinking_effort: Literal["none", "low", "medium", "high", "max"] = "high"
    # Integer token budget, used only when thinking_param points at an
    # Anthropic-style key (e.g. "thinking"). 0 disables it. Ignored by the
    # reasoning_effort path above.
    thinking_budget: int = 0
    thinking_param: str = "reasoning_effort"
    # When true, the REPL prints the model's reasoning trace inline (dimmed)
    # as it streams. Off by default — traces are verbose.
    show_reasoning: bool = False

    @field_validator("api_key", mode="before")
    @classmethod
    def overlay_env_key(cls, v: str) -> str:
        """Allow LLM_API_KEY in .env to override config.yaml value."""
        return os.getenv("LLM_API_KEY", v)

    def thinking_extra_body(self) -> Optional[dict]:
        """Build the extra_body dict that carries thinking config to the server.

        - reasoning_effort servers (Ollama/OpenAI): always send a string enum
          (including "none", which explicitly disables thinking).
        - Anthropic-style servers (thinking_param != "reasoning_effort"):
          send the integer token budget only when it is > 0.
        Returns None when nothing should be sent.
        """
        if self.thinking_param == "reasoning_effort":
            return {"reasoning_effort": self.thinking_effort}
        if self.thinking_budget > 0:
            return {self.thinking_param: self.thinking_budget}
        return None


class AgentConfig(BaseModel):
    system_prompt: str
    planner_prompt: str = (
        "You are a planning assistant. When given a goal, respond with ONLY a "
        "JSON array of short task descriptions (strings) in the order they should "
        "be executed. No markdown fences, no explanation — just the JSON array."
    )
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


class ExecutionConfig(BaseModel):
    allowed_commands: List[str] = Field(default_factory=list)
    timeout_seconds: int = 30


class WebFetchConfig(BaseModel):
    enabled: bool = False
    max_response_kb: int = 100
    timeout_seconds: int = 15


class OrchestratorConfig(BaseModel):
    # Set to true to enable the /orchestrate REPL command.
    enabled: bool = False
    # System prompt injected into the routing LLM call that assigns roles.
    # Leave empty to use the built-in router prompt.
    router_prompt: str = ""
    # Override system prompts for individual roles.  Keys must match a known
    # profile name: researcher | coder | reviewer | tester.  Missing keys
    # keep the built-in default.
    role_overrides: dict = Field(default_factory=dict)


class AppConfig(BaseModel):
    llm: LLMConfig
    agent: AgentConfig
    memory: MemoryConfig
    file_access: FileAccessConfig
    logging: LoggingConfig
    execution: ExecutionConfig = Field(default_factory=ExecutionConfig)
    web_fetch: WebFetchConfig = Field(default_factory=WebFetchConfig)
    # Resolved at load time from the --workspace flag (or cwd fallback).
    # Not read from config.yaml — set by load_config().
    workspace: Path = Field(default_factory=Path.cwd, exclude=True)

    model_config = {"arbitrary_types_allowed": True}

    def resolved_roots(self, workspace: Optional[Path] = None) -> List[Path]:
        """Return allowed_roots as absolute Paths anchored to *workspace*.

        When *workspace* is omitted, uses ``self.workspace`` (set at load time).
        Pass an explicit workspace to resolve roots for a different project
        without mutating the config object.
        """
        anchor = workspace or self.workspace
        return [
            Path(r).resolve() if Path(r).is_absolute() else (anchor / r).resolve()
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
