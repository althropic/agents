# File Assistant Agent

An AI assistant that works with your codebase in plain English. Ask it to read files, run tests, commit changes, explain code, or search across your project — it figures out what to do and shows its work.

```
>>> summarize src/config.py
>>> run the tests and tell me what failed
>>> what changed since the last commit?
>>> find all Python files under tests/
>>> /goal refactor src/config.py to add named profiles
>>> /orchestrate add pagination to the /users endpoint
```

Runs entirely on your machine using a local AI model. No internet connection, no data leaving your computer.

---

## Before you start

You'll need:

- [Miniconda](https://docs.conda.io/en/latest/miniconda.html) — manages the Python environment
- [Ollama](https://ollama.com) — runs the AI model locally (vLLM or llama.cpp also work)
- Python 3.11

**Start Ollama and pull a model (one time):**

```bash
ollama serve
ollama pull nemotron-mini
```

Then update `config.yaml` to point at Ollama's port:

```yaml
llm:
  base_url: "http://localhost:11434/v1"
  model: "nemotron-mini"
```

> The default config points at port `8080`. Ollama runs on `11434` unless you've configured it otherwise.

---

## Setup

Run these commands once from the project folder:

```bash
conda create --prefix ./.conda python=3.11 -y
conda activate ./.conda
pip install -r requirements.txt
pip install -r requirements-dev.txt
pip install -e .
```

This registers the `agent` command in the active environment. Editable installs pick up code changes automatically — no reinstall needed.

---

## Running the assistant

**Start an interactive session:**

```bash
conda activate ./.conda
agent
```

By default the assistant operates on the current directory. Each prompt you send in the same session shares conversation history — you can refer back to results from earlier turns.

```
File Assistant Agent — workspace: C:\your\project
Type your request, or 'exit' to quit. Type /help for commands.

>>> list the files in src/
>>> what does the first one contain?
>>> /think off
>>> /reason on
>>> find all .py files under tests/
>>> /goal refactor src/config.py to support named profiles
>>> /export my-session
>>> exit
```

**Slash commands** (handled instantly, no model call):

| Command | What it does |
|---------|-------------|
| `/think on\|off` | Enable or disable the model's reasoning step |
| `/reason on\|off` | Show or hide the model's chain-of-thought trace (dimmed, inline) |
| `/model <name>` | Switch the active model for this session |
| `/export [label]` | Save the conversation to a markdown file |
| `/goal <description>` | Break a goal into subtasks and execute them in sequence |
| `/orchestrate <description>` | Route subtasks to specialist sub-agents (researcher, coder, reviewer, tester). Requires `orchestrator.enabled: true` in config |
| `/index` | Build (or rebuild) the vector memory index from the workspace. Requires `vector_memory.enabled: true` in config |
| `/help` | List all available commands |

**Point the assistant at a different directory:**

```bash
agent --workspace /path/to/other/project
```

The `--workspace` flag sets the root directory the assistant is allowed to read and write. It also becomes the base for resolving any relative paths in `config.yaml`.

**Run a single task and exit:**

```bash
agent "summarize src/config.py"
agent --workspace /path/to/project "summarize src/config.py"
```

**On Windows, you can also use the legacy launch script (no install required):**

```bat
scripts\run.bat
scripts\run.bat "summarize src/config.py"
```

---

## What it can do

| Action | Example request |
|--------|----------------|
| Read a file | "show me what's in config.yaml" |
| Write a file | "create a file called notes.txt with..." |
| List a folder | "what files are in the src/ folder?" |
| Search for files | "find all markdown files in this project" |
| Search inside a file | "find every line in tools.py that mentions 'error'" |
| Fetch a web page | "fetch the httpx docs and show me how to set a timeout" |
| Run a shell command | "run pytest and show me the results" |
| Check git status | "what changed since the last commit?" |
| Show a git diff | "show me the unstaged diff" |
| Commit changes | "stage everything and commit with message 'fix bug'" |
| Run tests | "run the test suite" |
| Search the memory index | "find the file that handles rate limiting" |
| Plan a goal | `/goal refactor config.py to support named profiles` |
| Orchestrate a task | `/orchestrate add pagination to the /users endpoint` |

The assistant can only access folders listed under `file_access.allowed_roots` in `config.yaml`. Shell, git, and test tools only run commands listed under `execution.allowed_commands`. Anything outside either guard is blocked.

---

## Settings

All settings are in `config.yaml`. Open it to change how the assistant behaves.

| Setting | Default | What it does |
|---------|---------|-------------|
| `llm.base_url` | `http://localhost:8080/v1` | Where your AI model server is running |
| `llm.model` | `nemotron-3-ultra` | Which model to use |
| `llm.max_tokens` | `32000` | Maximum tokens the model may generate |
| `llm.thinking_effort` | `high` | Reasoning depth: `none`/`low`/`medium`/`high`/`max` |
| `llm.thinking_budget` | `0` | Integer token budget for Anthropic-style endpoints; `0` to disable |
| `llm.thinking_param` | `reasoning_effort` | `extra_body` key for thinking config (`reasoning_effort` or `thinking`) |
| `llm.show_reasoning` | `false` | Print chain-of-thought inline (dimmed). Toggle with `/reason on\|off` |
| `agent.max_iterations` | `20` | Steps before giving up on a task |
| `agent.max_file_size_kb` | `100` | Files larger than this won't be read |
| `agent.planner_prompt` | *(built-in)* | System prompt for the `/goal` planning step |
| `file_access.allowed_roots` | `["."]` | Folders the assistant can access, relative to `--workspace` |
| `memory.persist` | `false` | Save the conversation to disk after each session |
| `memory.export_path` | `.agent_memory` | Where to write saved sessions |
| `logging.level` | `INFO` | Log verbosity |
| `execution.allowed_commands` | `["pytest","python","pip","git"]` | Commands the agent may run |
| `execution.timeout_seconds` | `30` | Max seconds a shell command may run |
| `web_fetch.enabled` | `false` | Allow the agent to fetch public URLs |
| `web_fetch.max_response_kb` | `100` | Max response size for web fetches |
| `web_fetch.timeout_seconds` | `15` | Request timeout for web fetches |
| `orchestrator.enabled` | `false` | Enable the `/orchestrate` multi-agent command |
| `orchestrator.router_prompt` | `""` | Override the built-in role-routing system prompt |
| `orchestrator.role_overrides` | `{}` | Per-role system prompt overrides (researcher/coder/reviewer/tester) |
| `vector_memory.enabled` | `false` | Enable the `memory_search` tool and `/index` command |
| `vector_memory.index_path` | `.agent_memory/index.json` | Where to store the TF-IDF index |
| `vector_memory.embedding_model` | `tfidf` | Reserved for a future sentence-transformers backend |
| `vector_memory.max_file_size_kb` | `100` | Files larger than this are skipped during indexing |

To use a different API key, create a `.env` file in the project folder:

```
LLM_API_KEY=your-key-here
```

---

## Logs

The assistant keeps a log of everything it does in `logs/agent.log`. If something goes wrong, that's the first place to look. The file resets automatically when it gets too large.

---

## Running the tests

```bash
conda activate ./.conda
pytest
```

The tests don't need a live AI model — they run entirely with a fake one. All 205 should pass in under 20 seconds.

---

## Project layout

```
src/
  config.py              loads and validates settings from config.yaml
  io.py                  write_output() — all terminal output routes here
  logger.py              rotating file logger factory
  repl_commands.py       slash-command dispatcher (/think, /reason, /model, etc.)
  repl_ext.py            heavy slash-command handlers (/goal, /orchestrate, /index)
  runner.py              CLI entry point (interactive REPL or single-shot)
  task_queue.py          TaskQueue — breaks a /goal into subtasks
  orchestrator.py        Orchestrator — routes subtasks to specialist sub-agents
  orchestrator_helpers.py  task router and scoped loop factory
  memory_store.py        VectorMemory — TF-IDF index with JSON persistence
  memory_tfidf.py        TF-IDF math helpers and memory_search_tool formatter
  agent/
    schemas.py           FILE_TOOLS + ACTION_TOOLS + WEB_TOOLS + MEMORY_TOOLS → ALL_TOOLS
    action_schemas.py    action tool schemas (shell, git, tests)
    mem_schemas.py       memory_search tool schema
    web_schemas.py       web_fetch tool schema
    tools.py             file tool implementations + build_tool_map()
    action_tools.py      shell, git, and test tool implementations
    web_tools.py         web_fetch tool implementation
    profiles.py          specialist agent profiles (researcher/coder/reviewer/tester)
    loop.py              ReAct think→act→observe loop
    memory.py            conversation history, export to JSON/markdown
    reasoning.py         extracts chain-of-thought from streaming deltas
tests/                   automated checks (205 tests, no live model required)
logs/                    log files (created automatically)
config.yaml              all runtime settings
pyproject.toml           package manifest — defines the `agent` CLI command
```
