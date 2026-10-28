# File Assistant Agent

An AI assistant that works with your codebase in plain English. Ask it to read files, run tests, commit changes, explain code, or search across your project — it figures out what to do and shows its work.

```
>>> summarize src/config.py
>>> run the tests and tell me what failed
>>> what changed since the last commit?
>>> find all Python files under tests/
```

Runs entirely on your machine using a local AI model. No internet connection, no data leaving your computer.

---

## Before you start

You'll need:

- [Miniconda](https://docs.conda.io/en/latest/miniconda.html) — manages the Python environment
- [Ollama](https://ollama.com) — runs the AI model locally (vLLM or llama.cpp also work)
- Python 3.11

**Start Ollama and pull the model (one time):**

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
| `/help` | List all available commands |

**Point the assistant at a different directory:**

```bash
agent --workspace /path/to/other/project
```

The `--workspace` flag sets the root directory the assistant is allowed to read and write. It also becomes the base for resolving any relative paths in `config.yaml` (like `allowed_roots` and `memory.export_path`).

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
| Run a shell command | "run pytest and show me the results" |
| Check git status | "what changed since the last commit?" |
| Show a git diff | "show me the unstaged diff" |
| Commit changes | "stage everything and commit with message 'fix bug'" |
| Run tests | "run the test suite" |

The assistant can only access folders listed under `file_access.allowed_roots` in `config.yaml`, resolved relative to the active workspace. Shell, git, and test tools only run commands listed under `execution.allowed_commands`. Anything outside either guard is blocked.

---

## Settings

All settings are in `config.yaml`. Open it to change how the assistant behaves.

| Setting | Default | What it does |
|---------|---------|-------------|
| `llm.base_url` | `http://localhost:8080/v1` | Where your AI model server is running |
| `llm.model` | `nemotron-3-ultra` | Which model to use |
| `llm.max_tokens` | `32000` | Maximum tokens the model may generate (include reasoning traces) |
| `llm.thinking_effort` | `high` | Reasoning depth for Ollama/OpenAI servers, sent as `reasoning_effort`: `none`/`low`/`medium`/`high`/`max` |
| `llm.thinking_budget` | `0` | Integer token budget, used only when `thinking_param` is an Anthropic-style key (e.g. `thinking`); `0` to disable |
| `llm.thinking_param` | `reasoning_effort` | Which `extra_body` key carries thinking config — `reasoning_effort` (Ollama/OpenAI, uses `thinking_effort`) or `thinking` (Anthropic, uses `thinking_budget`) |
| `llm.show_reasoning` | `false` | Print the model's chain-of-thought inline (dimmed) as it streams. Toggle live with `/reason on\|off` |
| `agent.max_iterations` | `20` | How many steps the assistant takes before giving up |
| `agent.max_file_size_kb` | `100` | Files bigger than this (in KB) won't be read |
| `file_access.allowed_roots` | `["."]` | Folders the assistant can access, relative to `--workspace` |
| `memory.persist` | `false` | Save the conversation to disk after each session |
| `memory.export_path` | `.agent_memory` | Where to write saved sessions, relative to `--workspace` |
| `logging.level` | `INFO` | How much detail to write to the log file |
| `execution.allowed_commands` | `["pytest", "python", "pip", "git"]` | Commands the agent may run via shell/git/test tools |
| `execution.timeout_seconds` | `30` | Maximum seconds a shell command may run before being killed |

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

The tests don't need a live AI model — they run entirely with a fake one. All 104 should pass in under 15 seconds.

---

## Project layout

```
src/
  config.py        loads and checks settings from config.yaml
  io.py            write_output() — routes all terminal output to stdout
  logger.py        handles writing to the log file
  repl_commands.py slash-command dispatcher (/think, /reason, /model, /export, /help)
  runner.py        starts the assistant (interactive or single task)
  agent/
    schemas.py     file tool schemas (FILE_TOOLS) + combined ALL_TOOLS
    action_schemas.py   action tool schemas (shell, git, tests)
    tools.py       the file actions (read, write, list, search)
    action_tools.py     the action tools (run_command, git, tests)
    loop.py        the main thinking loop
    memory.py      keeps track of the conversation
    reasoning.py   extracts chain-of-thought from streaming deltas
tests/             automated checks
logs/              log files (created automatically)
config.yaml        all your settings
pyproject.toml     package manifest — defines the `agent` CLI command
```
