"""
ReAct agent loop.

Drives the think → act → observe cycle against an OpenAI-compatible endpoint.
The loop calls the LLM, dispatches tool calls, feeds observations back, and
repeats until the model returns a final answer or max_iterations is hit.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any, Dict, Iterator, Optional

from openai import OpenAI

from src.agent.memory import Memory
from src.agent.tools import ALL_TOOLS, build_tool_map
from src.config import AppConfig
from src.logger import get_logger

logger = get_logger(__name__)


class AgentLoop:
    """Stateless executor — create once, call run() per task."""

    def __init__(self, config: AppConfig) -> None:
        self._cfg = config
        self._client = OpenAI(
            base_url=config.llm.base_url,
            api_key=config.llm.api_key,
        )
        self._tool_map = build_tool_map(
            allowed_roots=config.resolved_roots(),
            max_size_kb=config.agent.max_file_size_kb,
            allowed_commands=config.execution.allowed_commands,
            workspace=config.workspace,
            command_timeout=config.execution.timeout_seconds,
        )
        logger.info(
            "AgentLoop ready: model=%s base_url=%s max_iter=%d workspace=%s roots=%s "
            "allowed_commands=%s timeout=%ds",
            config.llm.model,
            config.llm.base_url,
            config.agent.max_iterations,
            config.workspace,
            config.resolved_roots(),
            config.execution.allowed_commands,
            config.execution.timeout_seconds,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self, user_prompt: str) -> str:
        """
        Run a single task to completion and return the final answer string.
        Creates a fresh Memory per call (stateless across calls).
        Raises RuntimeError if max_iterations is exceeded without a final answer.
        """
        memory = Memory(
            system_prompt=self._cfg.agent.system_prompt,
            persist=self._cfg.memory.persist,
            export_path=str(self._cfg.resolved_memory_export_path()),
        )
        return self.run_with_memory(user_prompt, memory)

    def run_with_memory(self, user_prompt: str, memory: Memory) -> str:
        """
        Run a single task using the provided *memory* instance.
        Use this from the REPL to share history across prompts.
        Raises RuntimeError if max_iterations is exceeded without a final answer.
        """
        memory.add({"role": "user", "content": user_prompt})
        logger.info("AgentLoop.run: user_prompt=%r", user_prompt[:120])

        max_iter = self._cfg.agent.max_iterations
        for iteration in range(1, max_iter + 1):
            logger.debug("--- iteration %d/%d ---", iteration, max_iter)
            answer = self._step(memory)
            if answer is not None:
                memory.maybe_export()
                logger.info("AgentLoop.run: finished in %d iterations", iteration)
                return answer

        memory.maybe_export()
        raise RuntimeError(
            f"Agent did not produce a final answer within {max_iter} iterations."
        )

    def stream(self, user_prompt: str) -> Iterator[str]:
        """Yield the final answer token-by-token (non-tool turns only)."""
        memory = Memory(
            system_prompt=self._cfg.agent.system_prompt,
            persist=self._cfg.memory.persist,
            export_path=str(self._cfg.resolved_memory_export_path()),
        )
        yield from self.stream_with_memory(user_prompt, memory)

    def stream_with_memory(
        self, user_prompt: str, memory: Memory
    ) -> Iterator[str]:
        """
        Stream the final answer token-by-token using shared *memory*.
        Tool-call turns are processed silently; only the final text
        answer is yielded chunk-by-chunk.
        Raises RuntimeError if max_iterations is exceeded.
        """
        memory.add({"role": "user", "content": user_prompt})
        max_iter = self._cfg.agent.max_iterations
        for iteration in range(1, max_iter + 1):
            stream = self._client.chat.completions.create(
                **self._create_kwargs(memory.all(), stream=True)
            )
            parts: list[str] = []
            tc: dict[int, dict] = {}
            is_tool = False
            for chunk in stream:
                d = chunk.choices[0].delta
                if d.tool_calls:
                    is_tool = True
                    for c in d.tool_calls:
                        if c.index not in tc:
                            tc[c.index] = {"id": "", "function": {"name": "", "arguments": ""}}
                        if c.id:
                            tc[c.index]["id"] = c.id
                        if c.function and c.function.name:
                            tc[c.index]["function"]["name"] += c.function.name
                        if c.function and c.function.arguments:
                            tc[c.index]["function"]["arguments"] += c.function.arguments
                if d.content and not is_tool:
                    parts.append(d.content)
                    yield d.content
            if is_tool:
                calls = [SimpleNamespace(id=tc[i]["id"], function=SimpleNamespace(
                    name=tc[i]["function"]["name"], arguments=tc[i]["function"]["arguments"]))
                    for i in sorted(tc)]
                memory.add({"role": "assistant", "content": None, "tool_calls": [
                    {"id": c.id, "type": "function",
                     "function": {"name": c.function.name, "arguments": c.function.arguments}}
                    for c in calls]})
                self._dispatch_tools(calls, memory)
                continue
            answer = "".join(parts)
            memory.add({"role": "assistant", "content": answer})
            memory.maybe_export()
            return
        memory.maybe_export()
        raise RuntimeError(
            f"Agent did not produce a final answer within {max_iter} iterations."
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _create_kwargs(self, messages, stream=False):
        """Build kwargs for a chat.completions.create call."""
        kw = dict(model=self._cfg.llm.model, messages=messages, tools=ALL_TOOLS,
                  tool_choice="auto", temperature=self._cfg.llm.temperature,
                  max_tokens=self._cfg.llm.max_tokens, stream=stream)
        if self._cfg.llm.thinking_budget > 0:
            kw["extra_body"] = {self._cfg.llm.thinking_param: self._cfg.llm.thinking_budget}
        return kw

    def _step(self, memory: Memory) -> Optional[str]:
        """
        One LLM call.
        - If the response contains tool calls → execute them, append results, return None.
        - If the response is a plain text message → return it as the final answer.
        """
        response = self._client.chat.completions.create(
            **self._create_kwargs(memory.all())
        )

        msg = response.choices[0].message

        if msg.tool_calls:
            # Append the assistant's tool-call message
            memory.add(msg.model_dump(exclude_unset=True))
            self._dispatch_tools(msg.tool_calls, memory)
            return None  # signal: keep looping

        # Final answer
        answer = msg.content or ""
        memory.add({"role": "assistant", "content": answer})
        return answer

    def _dispatch_tools(self, tool_calls: Any, memory: Memory) -> None:
        """Execute each tool call and append the results to memory."""
        for call in tool_calls:
            name = call.function.name
            try:
                args: Dict[str, Any] = json.loads(call.function.arguments)
            except json.JSONDecodeError as exc:
                logger.warning("Failed to parse tool args for %s: %s", name, exc)
                args = {}

            logger.info("Tool call: %s args=%s", name, args)

            if name not in self._tool_map:
                result = f"ERROR: unknown tool '{name}'"
                logger.warning(result)
            else:
                try:
                    result = self._tool_map[name](**args)
                except Exception as exc:  # noqa: BLE001
                    result = f"ERROR: {exc}"
                    logger.error("Tool '%s' raised: %s", name, exc, exc_info=True)

            logger.debug("Tool result: %s → %r", name, str(result)[:200])
            memory.add(
                {
                    "role": "tool",
                    "tool_call_id": call.id,
                    "name": name,
                    "content": str(result),
                }
            )
