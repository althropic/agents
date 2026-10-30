"""
Specialist agent profiles for the orchestrator.

Each profile defines the system prompt and the subset of tools a role is
allowed to use.  The tool-set restriction is a list of tool names drawn from
the full set in schemas.py / action_schemas.py.  An empty list means the role
gets all available tools.

The profiles here are defaults — they can be overridden via OrchestratorConfig
in config.yaml.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from src.logger import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Profile definition
# ---------------------------------------------------------------------------

@dataclass
class AgentProfile:
    name: str
    system_prompt: str
    # Tool names this role may use.  Empty = unrestricted.
    allowed_tools: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Built-in profiles
# ---------------------------------------------------------------------------

RESEARCHER = AgentProfile(
    name="researcher",
    system_prompt=(
        "You are a Research Agent. Your job is to read and summarise existing "
        "code, documentation, and web resources so that other agents can act on "
        "accurate information. Use file and web tools to gather context. "
        "Always cite the exact file path or URL you read."
    ),
    allowed_tools=["read_file", "list_dir", "search_files", "grep", "web_fetch"],
)

CODER = AgentProfile(
    name="coder",
    system_prompt=(
        "You are a Coder Agent. Your job is to write, edit, and refactor code "
        "files. Use the file tools to read existing code before making changes. "
        "Apply the minimal diff needed — do not rewrite unrelated code. "
        "After writing, briefly describe what changed and why."
    ),
    allowed_tools=["read_file", "write_file", "list_dir", "search_files",
                   "grep", "run_command"],
)

REVIEWER = AgentProfile(
    name="reviewer",
    system_prompt=(
        "You are a Code Reviewer Agent. Your job is to inspect code for bugs, "
        "style issues, security problems, and adherence to project conventions. "
        "Read files and grep for patterns. Report findings clearly, grouped by "
        "severity (critical / warning / suggestion). Do not modify any files."
    ),
    allowed_tools=["read_file", "list_dir", "search_files", "grep"],
)

TESTER = AgentProfile(
    name="tester",
    system_prompt=(
        "You are a Tester Agent. Your job is to run the test suite, interpret "
        "failures, and report results in a structured format. Use run_tests to "
        "execute pytest and read_file / grep to inspect failing test code. "
        "Summarise: total tests, passed, failed, and a brief root-cause for "
        "each failure."
    ),
    allowed_tools=["read_file", "list_dir", "grep", "run_tests", "run_command"],
)

# Registry — keyed by role name for fast lookup
PROFILES: dict[str, AgentProfile] = {
    p.name: p for p in (RESEARCHER, CODER, REVIEWER, TESTER)
}


def get_profile(name: str) -> AgentProfile:
    """Return the profile for *name*, raising ValueError if unknown."""
    try:
        return PROFILES[name.lower()]
    except KeyError:
        known = ", ".join(PROFILES)
        raise ValueError(f"Unknown role '{name}'. Known roles: {known}") from None
