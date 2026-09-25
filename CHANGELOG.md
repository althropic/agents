# Changelog

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

All notable changes to this project are documented here.

---

## [Unreleased]

### Fixed

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
