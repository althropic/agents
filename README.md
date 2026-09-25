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

---

## Running the assistant

**Start an interactive session:**

```bash
conda activate ./.conda
python -m src.runner
```

By default the assistant operates on the current directory. Each prompt you send in the same session shares conversation history — you can refer back to results from earlier turns.

```
File Assistant Agent — workspace: C:\your\project
Type your request, or 'exit' to quit.

>>> list the files in src/
>>> what does the first one contain?
>>> find all .py files under tests/
>>> exit
```

**Point the assistant at a different directory:**

```bash
python -m src.runner --workspace /path/to/other/project
```

The `--workspace` flag sets the root directory the assistant is allowed to read and write. It also becomes the base for resolving any relative paths in `config.yaml` (like `allowed_roots` and `memory.export_path`).

**Run a single task and exit:**

```bash
python -m src.runner "summarize src/config.py"
python -m src.runner --workspace /path/to/project "summarize src/config.py"
```

**On Windows, you can also use the launch script:**

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

The assistant can only access folders listed under `file_access.allowed_roots` in `config.yaml`, resolved relative to the active workspace. Anything outside is blocked.

---

## Settings

All settings are in `config.yaml`. Open it to change how the assistant behaves.

| Setting | Default | What it does |
|---------|---------|-------------|
| `llm.base_url` | `http://localhost:8080/v1` | Where your AI model server is running |
| `llm.model` | `gpt-oss:120b` | Which model to use |
| `agent.max_iterations` | `20` | How many steps the assistant takes before giving up |
| `agent.max_file_size_kb` | `100` | Files bigger than this (in KB) won't be read |
| `file_access.allowed_roots` | `["."]` | Folders the assistant can access, relative to `--workspace` |
| `memory.persist` | `false` | Save the conversation to disk after each session |
| `memory.export_path` | `.agent_memory` | Where to write saved sessions, relative to `--workspace` |
| `logging.level` | `INFO` | How much detail to write to the log file |

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

The tests don't need a live AI model — they run entirely with a fake one. All 34 should pass in under a second.

---

## Project layout

```
src/
  config.py        loads and checks settings from config.yaml
  logger.py        handles writing to the log file
  runner.py        starts the assistant (interactive or single task)
  agent/
    tools.py       the file actions (read, write, list, search)
    loop.py        the main thinking loop
    memory.py      keeps track of the conversation
tests/             automated checks
logs/              log files (created automatically)
config.yaml        all your settings
```
