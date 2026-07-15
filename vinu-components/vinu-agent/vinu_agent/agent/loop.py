import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError, as_completed
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from .tools import ToolRegistry


@dataclass
class TokenUsage:
    total: int = 0
    prompt: int = 0
    completion: int = 0


@dataclass
class AgentResult:
    status: str = "completed"
    content: str = ""
    iterations: int = 0
    token_usage: TokenUsage = field(default_factory=TokenUsage)
    trace: List[Dict[str, Any]] = field(default_factory=list)


_ESTIMATED_CHARS_PER_TOKEN = 4.0


def _estimate_tokens(text: str) -> int:
    return int(len(text) / _ESTIMATED_CHARS_PER_TOKEN) + 1


class AgentLoop:
    def __init__(
        self,
        registry: ToolRegistry,
        llm: Any,
        memory: Any = None,
        event_callback: Optional[Callable[[str, Dict[str, Any]], None]] = None,
        max_iterations: int = 50,
        persistent_memory: Any = None,
    ) -> None:
        self.registry = registry
        self.llm = llm
        self.memory = memory
        self.event_callback = event_callback
        self.max_iterations = max_iterations
        self.persistent_memory = persistent_memory
        self._cancel_event = threading.Event()
        self._previous_summary: str = ""
        self._nudge_sent: bool = False
        self._compact_requested: bool = False
        self.tool_timeout: int = 60

    def run(self, messages: List[Dict], session_id: str = "") -> Dict:
        self._cancel_event.clear()
        iteration = 0
        full_history = list(messages)
        token_usage = TokenUsage()

        self._emit("loop.start", {
            "session_id": session_id,
            "message_count": len(messages),
        })

        while iteration < self.max_iterations:
            if self._cancel_event.is_set():
                result = self._build_result(
                    "cancelled",
                    "Agent execution cancelled.",
                    iteration,
                    token_usage,
                    full_history,
                )
                self._emit("loop.cancelled", {"session_id": session_id})
                return result

            # 0. Wrap-up nudge at 80% iterations
            remaining = self.max_iterations - iteration
            if not self._nudge_sent and remaining <= int(self.max_iterations * 0.2) and remaining > 0:
                self._nudge_sent = True
                full_history.append({
                    "role": "system",
                    "content": (
                        f"You have {remaining} iteration(s) remaining. "
                        "Wrap up your analysis and provide your final answer. "
                        "Do NOT start new tool calls."
                    ),
                })

            # 1. Apply context management
            compressed = self._apply_context_layers(full_history)

            # 2. Call LLM
            self._emit("llm.call", {
                "iteration": iteration,
                "message_count": len(compressed),
            })

            try:
                response = self._call_llm(compressed)
                token_usage.prompt += _estimate_tokens(
                    str([m["content"] for m in compressed])
                )
                token_usage.completion += _estimate_tokens(
                    response.get("content", "")
                )
                token_usage.total = token_usage.prompt + token_usage.completion
            except Exception as exc:
                error_msg = f"LLM call failed at iteration {iteration}: {exc}"
                self._emit("llm.error", {"error": str(exc)})
                return self._build_result(
                    "error", error_msg, iteration, token_usage, full_history
                )

            # 3. Parse response
            content = response.get("content", "").strip()
            tool_calls = response.get("tool_calls", [])

            if content:
                assistant_msg = {"role": "assistant", "content": content}
                full_history.append(assistant_msg)
                self._emit("llm.response", {
                    "iteration": iteration,
                    "content_preview": content[:200],
                })

            # 4. Process tool calls
            if tool_calls:
                assistant_msg = {
                    "role": "assistant",
                    "content": content or "",
                    "tool_calls": [
                        {
                            "id": tc.get("id", f"call_{iteration}_{i}"),
                            "type": "function",
                            "function": {
                                "name": tc["function"]["name"],
                                "arguments": tc["function"].get("arguments", "{}"),
                            },
                        }
                        for i, tc in enumerate(tool_calls)
                    ],
                }
                full_history.append(assistant_msg)

                # Batch readonly tools, serialize write tools
                tool_results = self._process_tool_calls(tool_calls)
                for tr in tool_results:
                    full_history.append(tr)
                    # Detect compact sentinel from compact_tool
                    try:
                        payload = json.loads(tr.get("content", "{}"))
                        if payload.get("__compact"):
                            self._compact_requested = True
                    except (json.JSONDecodeError, AttributeError):
                        pass

                self._emit("tools.executed", {
                    "iteration": iteration,
                    "tool_count": len(tool_calls),
                })
                iteration += 1
                continue

            # 5. No tool calls — final answer
            if content:
                self._emit("loop.completed", {
                    "session_id": session_id,
                    "iterations": iteration + 1,
                })
                return self._build_result(
                    "completed", content, iteration + 1, token_usage, full_history
                )

            iteration += 1

        # Max iterations reached — force summary output
        force_msg = {
            "role": "assistant",
            "content": (
                "I've reached the maximum number of iterations. "
                "Here's a summary of what I found so far..."
            ),
        }
        full_history.append(force_msg)
        return self._build_result(
            "max_iterations", force_msg["content"], iteration, token_usage, full_history
        )

    def cancel(self) -> None:
        self._cancel_event.set()

    def _process_tool_calls(self, tool_calls: List[Dict]) -> List[Dict]:
        readonly_calls = []
        write_calls = []
        for tc in tool_calls:
            name = tc["function"]["name"]
            tool = self.registry.get(name)
            if tool and tool.is_readonly:
                readonly_calls.append(tc)
            else:
                write_calls.append(tc)

        results = []

        if readonly_calls:
            with ThreadPoolExecutor(max_workers=4) as pool:
                fut_to_call = {}
                for tc in readonly_calls:
                    name = tc["function"]["name"]
                    params = self._parse_params(tc)
                    fut = pool.submit(self.registry.execute, name, params)
                    fut_to_call[fut] = tc

                for fut in as_completed(fut_to_call):
                    tc = fut_to_call[fut]
                    name = tc["function"]["name"]
                    call_id = tc.get("id", "")
                    try:
                        result = fut.result(timeout=self.tool_timeout)
                    except TimeoutError:
                        result = json.dumps({
                            "status": "error", "tool": name,
                            "error": f"timeout after {self.tool_timeout}s",
                        })
                    except Exception as exc:
                        result = json.dumps({
                            "status": "error", "tool": name, "error": str(exc),
                        })
                    results.append({
                        "role": "tool",
                        "tool_call_id": call_id,
                        "name": name,
                        "content": result,
                    })

        for tc in write_calls:
            name = tc["function"]["name"]
            params = self._parse_params(tc)
            call_id = tc.get("id", "")
            try:
                with ThreadPoolExecutor(max_workers=1) as pool:
                    fut = pool.submit(self.registry.execute, name, params)
                    result = fut.result(timeout=self.tool_timeout)
            except TimeoutError:
                result = json.dumps({
                    "status": "error", "tool": name,
                    "error": f"timeout after {self.tool_timeout}s",
                })
            except Exception as exc:
                result = json.dumps({
                    "status": "error", "tool": name, "error": str(exc),
                })
            results.append({
                "role": "tool",
                "tool_call_id": call_id,
                "name": name,
                "content": result,
            })

        return results

    def _parse_params(self, tc: Dict) -> Dict[str, Any]:
        raw = tc["function"].get("arguments", "{}")
        if isinstance(raw, str):
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                return {}
        return raw if isinstance(raw, dict) else {}

    def _call_llm(self, messages: List[Dict]) -> Dict:
        tools_def = self.registry.get_definitions()
        return self.llm.chat(messages, tools=tools_def)

    def _apply_context_layers(self, messages: List[Dict]) -> List[Dict]:
        # Layer 0: honor explicit compact tool request (agent-triggered L3)
        if self._compact_requested:
            self._compact_requested = False
            self._emit("context.compact", {"reason": "compact_tool"})
            result = self._auto_compact(messages)
            return self._fix_tool_pairs(result)

        total_text = str([m.get("content", "") for m in messages])
        estimated_tokens = _estimate_tokens(total_text)
        max_tokens = 128000

        if estimated_tokens >= max_tokens:
            result = self._auto_compact(messages)
            return self._fix_tool_pairs(result)

        ratio = estimated_tokens / max_tokens

        if ratio > 0.70:
            result = self._context_collapse(messages)
            return self._fix_tool_pairs(result)
        elif ratio > 0.50:
            return self._microcompact(messages)

        return messages

    def _microcompact(self, messages: List[Dict]) -> List[Dict]:
        result = list(messages)
        tool_result_indices = [
            i for i, m in enumerate(result)
            if m.get("role") == "tool" and len(m.get("content", "")) > 100
        ]
        if len(tool_result_indices) > 3:
            keep = set(tool_result_indices[-3:])
            for i in tool_result_indices[:-3]:
                if i not in keep:
                    result[i] = dict(result[i], content="[cleared]")
        return result

    def _context_collapse(self, messages: List[Dict]) -> List[Dict]:
        result = list(messages)
        if len(result) < 8:
            return result
        for i in range(len(result) - 6):
            content = result[i].get("content", "")
            if len(content) > 2400:
                head = content[:900]
                tail = content[-500:]
                result[i] = dict(result[i], content=f"{head}\n...[collapse]...\n{tail}")
        return result

    def _auto_compact(self, messages: List[Dict]) -> List[Dict]:
        compact_prompt = (
            "Summarize the following conversation into a concise structured "
            "summary preserving all key findings, data points, and decisions."
        )
        full_text = str([m.get("content", "") for m in messages[-20:]])
        try:
            response = self.llm.chat([
                {"role": "system", "content": compact_prompt},
                {"role": "user", "content": f"Summarize:\n\n{full_text[:8000]}"},
            ])
            summary = response.get("content", "")
            if self._previous_summary:
                summary = self._iterative_update(self._previous_summary, summary)
            self._previous_summary = summary
            return [
                {"role": "system", "content": messages[0]["content"]},
                {"role": "system", "content": f"<compacted-summary>\n{summary}\n</compacted-summary>"},
                messages[-1],
            ]
        except Exception:
            return messages[-6:]

    def _iterative_update(self, prev: str, new_info: str) -> str:
        try:
            response = self.llm.chat([
                {"role": "system", "content": "Merge a previous summary with new conversation turns into a single coherent summary."},
                {"role": "user", "content": f"Previous summary:\n{prev}\n\nNew information:\n{new_info}\n\nMerged summary:"},
            ])
            return response.get("content", new_info)
        except Exception:
            return new_info

    def _fix_tool_pairs(self, messages: List[Dict]) -> List[Dict]:
        call_ids = set()
        for m in messages:
            for tc in m.get("tool_calls", []):
                call_ids.add(tc.get("id", ""))
        result_ids = {m.get("tool_call_id") for m in messages if m.get("role") == "tool"}
        orphan_ids = call_ids - result_ids - {""}
        for oid in orphan_ids:
            messages.append({
                "role": "tool",
                "tool_call_id": oid,
                "content": "{}",
            })
        return messages

    def _emit(self, event_type: str, data: Dict) -> None:
        if self.event_callback:
            try:
                self.event_callback(event_type, data)
            except Exception:
                pass

    def _build_result(
        self,
        status: str,
        content: str,
        iterations: int,
        token_usage: TokenUsage,
        history: List[Dict],
    ) -> Dict:
        return {
            "status": status,
            "content": content,
            "iterations": iterations,
            "token_usage": {
                "total": token_usage.total,
                "prompt": token_usage.prompt,
                "completion": token_usage.completion,
            },
            "history": history[-10:],
        }
