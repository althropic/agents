# Changelog

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

All notable changes to this project are documented here.

---

## [Unreleased]

### Added — REPL Slash Commands

- **`src/repl_commands.py`** — New module: REPL slash-command dispatcher. Handles `/think on|off`, `/model <name>`, `/export [label]`, `/help`. Returns `True` on every handled command so the REPL loop knows to skip the LLM call.
- **`src/agent/memory.py`** — `Memory.export_markdown()`: writes conversation history to a `.md` file with `## Role` headings.
- **`src/config.py`** — `LLMConfig.thinking_param` field (default `"reasoning_effort"`). Controls the `extra_body` key used to pass `thinking_budget` to the model server. Change to `"thinking"` for Anthropic-style endpoints.

### Changed — REPL Slash Commands

- **`src/agent/loop.py`** — `_create_kwargs()` helper centralises all API call parameters and injects `extra_body` when `thinking_budget > 0`. Both `_step()` and `stream_with_memory()` now use it. `thinking_budget` is finally wired to actual API calls.
- **`src/runner.py`** — REPL startup banner updated to mention `/help`. Slash commands are intercepted before the LLM call via `repl_commands.is_command()` / `repl_commands.handle()`.
- **`config.yaml`** — `llm.thinking_param: "reasoning_effort"` added and documented.

### Added — Streaming REPL

- **`src/agent/loop.py`** — `AgentLoop.stream_with_memory()` method: streams the final answer token-by-token using shared memory. Tool-call turns are processed silently; only the final text turn is yielded chunk-by-chunk. Handles streaming tool call fragment accumulation. `stream()` now delegates to `stream_with_memory()`. Unused `stream_final` parameter removed from `_step()`.
- **`src/runner.py`** — REPL now calls `stream_with_memory()` instead of `run_with_memory()`. Answers print incrementally as the model generates them, with a newline appended after completion.
- **`tests/test_streaming.py`** — 5 tests for streaming: single-turn chunk yielding, shared-memory chunk yielding, tool-call-then-streamed-answer, max-iterations `RuntimeError`, empty content handling.

### Added — Phase 2: Action Tools

- **`src/agent/action_schemas.py`** — New module with OpenAI function-calling schemas for five action tools: `run_command`, `git_status`, `git_diff`, `git_commit`, `run_tests`.
- **`src/agent/action_tools.py`** — New module with implementations for all five action tools. Every tool validates its command against `execution.allowed_commands` before running. `run_command` validates the working directory stays inside the workspace. All tools return formatted output (exit code + stdout + stderr).
- **`src/config.py`** — `ExecutionConfig` Pydantic model (`allowed_commands`, `timeout_seconds`). Added to `AppConfig` with a safe default (empty list, 30 s timeout).
- **`config.yaml`** — `execution` section with `allowed_commands: [pytest, python, pip, git]` and `timeout_seconds: 30`. System prompt updated to mention shell, git, and test capabilities.
- **`tests/test_action_tools.py`** — 23 tests covering all five action tools: allowed/disallowed commands, workspace cwd guards, timeout, git status/diff/commit on a fresh repo, pytest execution, `build_action_tool_map`, and `build_tool_map` integration (file + action tools combined).

### Changed — Phase 2

- **`src/agent/schemas.py`** — `ALL_TOOLS` list renamed to `FILE_TOOLS`; `ALL_TOOLS` now combines `FILE_TOOLS + ACTION_TOOLS` so the LLM sees every available tool.
- **`src/agent/tools.py`** — `build_tool_map()` accepts optional `allowed_commands`, `workspace`, and `command_timeout` params. When provided, action tools are merged into the returned map.
- **`src/agent/loop.py`** — `AgentLoop.__init__` passes `execution.allowed_commands`, `workspace`, and `execution.timeout_seconds` to `build_tool_map`. Startup log includes the new values.
- **`src/runner.py`** — Config-loaded log lines in `_build_loop` and `run_repl` extended to include `allowed_commands` and `timeout`.
- **`tests/conftest.py`** — `minimal_config_dict` includes an `execution` section with test-safe defaults.

### Added

- **`src/agent/schemas.py`** — New module containing all five OpenAI function-calling schema dicts (`ALL_TOOLS`). Extracted from `tools.py` to keep both files under the 200-line limit. `ALL_TOOLS` is re-exported from `tools.py` via a `noqa: F401` import so all existing callers are unaffected.
- **`src/io.py`** — `write_output(text)` stdout writer. All user-facing terminal output in `src/` now routes through this function instead of `print()`, satisfying the no-`print()`-in-src rule while keeping interactive output separate from the structured log.
- **`config.yaml` / `LLMConfig`** — `llm.thinking_budget` field (default `0`). Tokens budgeted for the model's internal reasoning trace; passed as `reasoning_effort` (or equivalent) to models that support it. Set to `0` to disable; ignored by models that do not expose reasoning.

### Changed

- **`config.yaml`** — `llm.model` switched from `gpt-oss:120b` to `nemotron-3-ultra`. `llm.max_tokens` raised from `4096` to `32000` to accommodate reasoning traces.
- **`src/config.py`** — `LLMConfig.max_tokens` default raised to `32000`; `LLMConfig.thinking_budget: int = 0` added.
- **`src/runner.py`** — All `print()` calls replaced with `write_output()` from `src/io.py`. Startup log lines in `_build_loop` and `run_repl` extended to include `max_tokens` and `thinking_budget`.
- **`src/agent/tools.py`** — Schema block removed (now in `schemas.py`); `ALL_TOOLS` imported and re-exported. File trimmed from ~210 lines to ~130 lines.

### Added

- **`pyproject.toml`** — Package manifest with `setuptools` build backend and `agent` console script entry point (`src.runner:main`). Run `pip install -e .` once in the conda env, then use `agent` / `agent --workspace DIR` / `agent "prompt"` directly instead of `python -m src.runner`.

### Added

- **`src/agent/loop.py`** — `AgentLoop.run_with_memory()` public method: runs a task against a caller-supplied `Memory` instance. Enables the REPL to share conversation history across prompts within a session.
- **`src/runner.py`** — `--workspace DIR` CLI flag (via `argparse`). Accepts any directory as the agent's operating root; defaults to `os.getcwd()`. Prints the active workspace on REPL startup.

### Changed

- **`src/config.py`** — `AppConfig.resolved_roots()` is now a regular method (was a `@property`). Resolves relative roots against `cfg.workspace` instead of `_CONFIG_PATH.parent`, making the sandbox portable. `load_config()` accepts an optional `workspace` parameter. New `AppConfig.resolved_memory_export_path()` method anchors the memory export directory to the same workspace.
- **`src/agent/loop.py`** — `AgentLoop.run()` delegates to `run_with_memory()` with a fresh `Memory` per call (single-shot behaviour unchanged). Memory export path now resolved via `cfg.resolved_memory_export_path()`.
- **`src/runner.py`** — REPL now creates a single `Memory` instance outside the prompt loop, giving the agent access to prior turns within the same session. Replaced raw `sys.argv` slicing with `argparse`.

### Fixed

- **`src/agent/tools.py`** — `_resolve_and_check`: replaced `str(target).startswith(str(root))` with `target.is_relative_to(root)`. The old check incorrectly allowed `/foo` to pass the guard for a root of `/foobar`.
- **`scripts/run.bat`** — Removed broken minimized-window relaunch pattern that leaked `-minimized` and `ECHO is off.` as prompts to the runner. Simplified to a direct conda activate + launch.
- **`src/logger.py`** — Removed `StreamHandler` from root logger; logs now go to `logs/agent.log` only. Eliminates INFO noise in the terminal during interactive and single-shot use.

---

## [0.1.0] — 2026-09-24

### Added

- **`src/config.py`** — Pydantic v2 `AppConfig` with typed sub-models for LLM, agent, memory, file access, and logging. Loads `config.yaml`; overlays `LLM_API_KEY` from `.env`.
- **`src/logger.py`** — `get_logger(__name__)` factory with `RotatingFileHandler` to `logs/agent.log` (100 KB default) and console output. `apply_log_level()` updates level at runtime.
- **`src/agent/tools.py`** — Five file tools (`read_file`, `write_file`, `list_dir`, `search_files`, `grep`) with OpenAI function-calling schemas and `build_tool_map()`. All tools enforce `allowed_roots` and `max_file_size_kb` guards.
- **`src/agent/memory.py`** — `Memory` class: in-memory conversation history (system prompt + message list), `export()` to JSON, `maybe_export()` gated on `config.memory.persist`.
- **`src/agent/loop.py`** — `AgentLoop` implementing the ReAct think → act → observe cycle against any OpenAI-compatible endpoint. Supports `run()` (blocking) and `stream()` (token iterator). Enforces `max_iterations` guard.
- **`src/runner.py`** — Entry point (`python -m src.runner`). Single-shot mode via CLI args; interactive REPL when run with no args.
- **`scripts/run.bat`** — Windows launcher: activates `.conda` env and delegates to `src.runner` with pass-through args.
- **`config.yaml`** — Central config: LLM endpoint (`http://localhost:8080/v1`, `gpt-oss:120b`), agent limits, memory persistence, file access roots, logging level.
- **`config.example.yaml`** — *(planned)* Verbose reference copy with all options documented.
- **`tests/conftest.py`** — Shared pytest fixtures: `minimal_config_dict`, `config_file`, `app_config`, `tmp_workspace`.
- **`tests/test_tools.py`** — 25 unit tests covering all five file tools: happy paths, permission guards, size limits, edge cases, and `build_tool_map()`.
- **`tests/test_agent.py`** — 9 integration tests with a fully mocked LLM: single-turn answer, tool-call-then-answer, unknown tool graceful handling, max-iterations `RuntimeError`, and `Memory` unit tests.
- **`README.md`** — User-friendly setup, usage, configuration reference, tool list, and project structure.
- **`requirements.txt`** — `openai`, `pydantic`, `pyyaml`, `python-dotenv`.
- **`requirements-dev.txt`** — `pytest`, `pytest-mock`.

---
