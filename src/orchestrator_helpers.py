"""
Internal helpers for the orchestrator.

Separated from orchestrator.py to keep both files under the 200-line limit.

Exports:
    _route_task(task_description, client, model) -> role name
    _build_scoped_loop(cfg, profile)             -> AgentLoop
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from openai import OpenAI

from src.agent.loop import AgentLoop
from src.agent.profiles import PROFILES, AgentProfile
from src.agent.schemas import ALL_TOOLS
from src.logger import get_logger

if TYPE_CHECKING:
    from src.config import AppConfig

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Role router
# ---------------------------------------------------------------------------

_ROUTER_SYSTEM = (
    "You are a task router. Given a subtask description, respond with ONLY "
    "the name of the most appropriate specialist role from this list: "
    "researcher, coder, reviewer, tester. "
    "No explanation — just the single role name in lowercase."
)

_ROLE_HINTS = {
    "researcher": ("read", "find", "search", "fetch", "look", "check", "list",
                   "inspect", "summarise", "summarize", "explore", "what", "how"),
    "coder":      ("write", "add", "implement", "create", "edit", "refactor",
                   "fix", "update", "modify", "change", "delete"),
    "reviewer":   ("review", "audit", "lint", "analyse", "analyze", "verify",
                   "validate", "assess", "quality"),
    "tester":     ("test", "run test", "run tests", "pytest", "assert",
                   "coverage", "failing", "pass", "fail"),
}


def _route_task(task_description: str, client: OpenAI, model: str) -> str:
    """Ask the LLM which specialist role should handle *task_description*.

    Falls back to keyword matching if the LLM returns an unexpected value,
    and to "researcher" when no keyword matches.
    """
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": _ROUTER_SYSTEM},
                {"role": "user", "content": task_description},
            ],
            temperature=0.0,
            max_tokens=16,
        )
        role = (response.choices[0].message.content or "").strip().lower()
        if role in PROFILES:
            logger.debug("Router: '%s' → %s (LLM)", task_description[:60], role)
            return role
        logger.warning("Router: LLM returned unknown role %r — falling back", role)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Router: LLM call failed (%s) — falling back to keywords", exc)

    desc = task_description.lower()
    for role, hints in _ROLE_HINTS.items():
        if any(h in desc for h in hints):
            logger.debug("Router: '%s' → %s (keyword)", task_description[:60], role)
            return role
    logger.debug("Router: no match — defaulting to researcher")
    return "researcher"


# ---------------------------------------------------------------------------
# Scoped AgentLoop factory
# ---------------------------------------------------------------------------

def _build_scoped_loop(cfg: "AppConfig", profile: AgentProfile) -> AgentLoop:
    """Return an AgentLoop with the profile's restricted system prompt and tools.

    A shallow Pydantic model_copy swaps the system prompt without mutating the
    original config.  The tool map and schema list are filtered to
    profile.allowed_tools after loop construction.
    """
    scoped_cfg = cfg.model_copy(deep=False)
    scoped_cfg.agent = cfg.agent.model_copy(
        update={"system_prompt": profile.system_prompt}
    )

    loop = AgentLoop(scoped_cfg)

    if profile.allowed_tools:
        loop._tool_map = {  # noqa: SLF001
            k: v for k, v in loop._tool_map.items()  # noqa: SLF001
            if k in profile.allowed_tools
        }
        loop._allowed_tools_schema = [  # noqa: SLF001
            t for t in ALL_TOOLS if t["function"]["name"] in profile.allowed_tools
        ]
    else:
        loop._allowed_tools_schema = ALL_TOOLS  # noqa: SLF001

    # Patch _create_kwargs to use the filtered schema list
    original_create_kwargs = loop._create_kwargs  # noqa: SLF001

    def _scoped_create_kwargs(messages, stream=False):
        kw = original_create_kwargs(messages, stream=stream)
        kw["tools"] = loop._allowed_tools_schema  # noqa: SLF001
        return kw

    loop._create_kwargs = _scoped_create_kwargs  # noqa: SLF001
    logger.info(
        "Scoped loop: role=%s tools=%s",
        profile.name,
        list(loop._tool_map),  # noqa: SLF001
    )
    return loop
