"""
Shared pytest fixtures for the File Assistant Agent test suite.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest
import yaml

from src.config import AppConfig, load_config


# ---------------------------------------------------------------------------
# Config fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def minimal_config_dict() -> dict:
    """Minimal raw dict that satisfies AppConfig validation."""
    return {
        "llm": {
            "base_url": "http://localhost:8080/v1",
            "api_key": "test-key",
            "model": "test-model",
        },
        "agent": {
            "system_prompt": "You are a test agent.",
            "max_iterations": 5,
            "max_file_size_kb": 10,
        },
        "memory": {
            "persist": False,
            "export_path": ".agent_memory",
        },
        "file_access": {
            "allowed_roots": ["."],
        },
        "logging": {
            "level": "DEBUG",
            "log_dir": "logs",
            "max_size_kb": 100,
        },
        "execution": {
            "allowed_commands": ["pytest", "python", "git", "echo"],
            "timeout_seconds": 10,
        },
    }


@pytest.fixture()
def config_file(tmp_path: Path, minimal_config_dict: dict) -> Path:
    """Write a minimal config.yaml into tmp_path and return its path."""
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(yaml.dump(minimal_config_dict), encoding="utf-8")
    return cfg_path


@pytest.fixture()
def app_config(config_file: Path) -> AppConfig:
    """Return a validated AppConfig loaded from the temp config file."""
    return load_config(config_file)


# ---------------------------------------------------------------------------
# Filesystem fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def tmp_workspace(tmp_path: Path) -> Path:
    """
    A temporary directory pre-populated with a small file tree for tool tests.

    Layout:
        tmp_workspace/
            hello.txt          — "Hello, world!"
            subdir/
                nested.txt     — "Nested content."
    """
    (tmp_path / "hello.txt").write_text("Hello, world!", encoding="utf-8")
    subdir = tmp_path / "subdir"
    subdir.mkdir()
    (subdir / "nested.txt").write_text("Nested content.", encoding="utf-8")
    return tmp_path
