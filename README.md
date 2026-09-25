# File Assistant Agent

An AI assistant that works with files on your computer. Ask it in plain English — it figures out what to do.

```
>>> summarize src/config.py
>>> find all Python files under tests/
>>> read src/agent/loop.py and explain what it does
```

No internet connection needed. It runs entirely on your machine using a local AI model.

---

## Before you start

You'll need:

- [Miniconda](https://docs.conda.io/en/latest/miniconda.html) — manages the Python environment
- A local AI model server running at `http://localhost:8080/v1` (e.g. [Ollama](https://ollama.com), vLLM, or llama.cpp)
- Python 3.11

---

## Installation

Run these commands once from the project folder:

```bash
conda create --prefix ./.conda python=3.11 -y
conda activate ./.conda
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

**Optional — override the API key or endpoint via `.env`:**

```
LLM_API_KEY=your-key-here
```

## Usage

**Interactive REPL:**

```bash
conda activate ./.conda
python -m src.runner
```

```
File Assistant Agent — type your request, or 'exit' to quit.

>>> list the files in src/
>>> read src/agent/loop.py and explain the main loop
>>> find all Python files under tests/
>>> exit
```

**Single-shot (pipe-friendly):**

```bash
python -m src.runner "grep for TODO in src/agent/tools.py"
```

**Via the launch script (Windows):**

```bat
scripts\run.bat "summarize src/config.py"
scripts\run.bat
```

## Configuration

All settings live in `config.yaml`. Nothing is hardcoded.

| Key | Default | What it controls |
|-----|---------|-----------------|
| `llm.base_url` | `http://localhost:8080/v1` | LLM server endpoint |
| `llm.model` | `gpt-oss:120b` | Model name to request |
| `agent.max_iterations` | `20` | Max tool-call rounds before giving up |
| `agent.max_file_size_kb` | `100` | Files larger than this are refused |
| `file_access.allowed_roots` | `["."]` | Directories the agent is allowed to touch |
| `memory.persist` | `false` | Save conversation history to `.agent_memory/` |
| `logging.level` | `INFO` | Log verbosity (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |

## Available tools

| Tool | What it does |
|------|-------------|
| `read_file` | Read the full text of a file |
| `write_file` | Write or overwrite a file |
| `list_dir` | List files and folders in a directory |
| `search_files` | Find files by glob pattern (e.g. `**/*.py`) |
| `grep` | Search inside a file with a regex |

The agent can only access paths inside `file_access.allowed_roots`. Anything outside is blocked.

## Running tests

```bash
conda activate ./.conda
pytest
```

All 34 tests run in under a second with no LLM connection needed — the test suite mocks the API entirely.

## Project structure

```
src/
  config.py          Config loading and validation (Pydantic)
  logger.py          Logging factory → logs/agent.log
  runner.py          Entry point: REPL + single-shot mode
  agent/
    tools.py         File tool implementations + OpenAI schemas
    loop.py          ReAct agent loop
    memory.py        Conversation history + optional export
tests/
  conftest.py        Shared fixtures
  test_tools.py      Unit tests for all file tools
  test_agent.py      Integration tests with mock LLM
logs/                Runtime logs (auto-created)
config.yaml          All configurable settings
```

## Logs

The agent writes structured logs to `logs/agent.log` (rotates at 100 KB). To see debug-level output, set `logging.level: DEBUG` in `config.yaml`.
