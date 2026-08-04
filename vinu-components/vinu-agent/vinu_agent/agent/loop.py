import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from vinu_lib.telemetry import LLMCallRecord, StepRecord, record_llm_call_safe, record_step_safe

from .tools import ToolRegistry
from .workflow import WorkflowTracker

#: Conservative fallback when neither an explicit max_context_tokens nor a
#: real llm.context_window is available. Deliberately small — 04-advanced-aim-1
#: found the real cost of guessing too high (the previous hardcoded 128000
#: against a real 32000-token model); guessing too low just compacts more
#: eagerly than necessary, which is the safer failure direction.
_DEFAULT_MAX_CONTEXT_TOKENS = 8000


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
        max_context_tokens: Optional[int] = None,
        data_root: str = "",
        service_name: str = "vinu-agent",
    ) -> None:
        self.registry = registry
        self.llm = llm
        self.memory = memory
        self.event_callback = event_callback
        self.max_iterations = max_iterations
        self.persistent_memory = persistent_memory
        # Priority: explicit param > llm's own resolved context_window
        # (set by create_llm() via resolve_context_window/config override)
        # > conservative default. Never a hardcoded guess presented as fact
        # — see _DEFAULT_MAX_CONTEXT_TOKENS.
        self.max_context_tokens = (
            max_context_tokens
            or getattr(llm, "context_window", None)
            or _DEFAULT_MAX_CONTEXT_TOKENS
        )
        self._data_root = data_root
        self._service_name = service_name
        self._cancel_event = threading.Event()
        self._previous_summary: str = ""
        self._nudge_sent: bool = False
        self._compact_requested: bool = False
        self.tool_timeout: int = 60
        self._workflow_tracker: WorkflowTracker = WorkflowTracker()
        self._workflow_injected: bool = False
        self._ground_truth_system_msg: dict | None = None
        self._facts_system_msg: dict | None = None
        self._freshness_system_msg: dict | None = None
        self._research_digest_system_msg: dict | None = None

    def run(self, messages: List[Dict], session_id: str = "") -> Dict:
        self._cancel_event.clear()
        self._session_id = session_id
        self._run_start_time = time.perf_counter()
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

            # 1b. Inject workflow context
            wf_block = self._workflow_tracker.to_context_block()
            if wf_block:
                compressed.insert(1, {"role": "system", "content": wf_block})

            # 2. Call LLM
            self._emit("llm.call", {
                "iteration": iteration,
                "message_count": len(compressed),
            })

            call_start = time.perf_counter()
            try:
                response = self._call_llm(compressed)
            except Exception as exc:
                error_msg = f"LLM call failed at iteration {iteration}: {exc}"
                self._emit("llm.error", {"error": str(exc)})
                self._record_llm_telemetry(
                    prompt_tokens=0, completion_tokens=0, total_tokens=0,
                    token_count_source="estimated", retry_count=0,
                    latency_sec=time.perf_counter() - call_start,
                    success=False, outcome="error", error=str(exc),
                )
                return self._build_result(
                    "error", error_msg, iteration, token_usage, full_history
                )

            usage = response.get("usage")
            if usage:
                prompt_tokens = usage.get("prompt_tokens", 0)
                completion_tokens = usage.get("completion_tokens", 0)
                token_count_source = "provider"
            else:
                prompt_tokens = _estimate_tokens(
                    str([m["content"] for m in compressed])
                )
                completion_tokens = _estimate_tokens(response.get("content", ""))
                token_count_source = "estimated"
            token_usage.prompt += prompt_tokens
            token_usage.completion += completion_tokens
            token_usage.total = token_usage.prompt + token_usage.completion
            self._record_llm_telemetry(
                prompt_tokens=prompt_tokens, completion_tokens=completion_tokens,
                total_tokens=prompt_tokens + completion_tokens,
                token_count_source=token_count_source,
                retry_count=response.get("retry_count", 0),
                latency_sec=time.perf_counter() - call_start,
                success=True, outcome="completed",
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

    @property
    def workflow_tracker(self) -> WorkflowTracker:
        return self._workflow_tracker

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
                    fut_to_call[fut] = (tc, time.perf_counter())

                for fut in as_completed(fut_to_call):
                    tc, call_start = fut_to_call[fut]
                    name = tc["function"]["name"]
                    call_id = tc.get("id", "")
                    try:
                        result = fut.result(timeout=self.tool_timeout)
                        self._record_tool_telemetry(name, call_start, success=True, outcome="completed")
                    except TimeoutError:
                        result = json.dumps({
                            "status": "error", "tool": name,
                            "error": f"timeout after {self.tool_timeout}s",
                        })
                        self._record_tool_telemetry(name, call_start, success=False, outcome="timeout", error=result)
                    except Exception as exc:
                        result = json.dumps({
                            "status": "error", "tool": name, "error": str(exc),
                        })
                        self._record_tool_telemetry(name, call_start, success=False, outcome="tool_error", error=str(exc))
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
            call_start = time.perf_counter()
            try:
                with ThreadPoolExecutor(max_workers=1) as pool:
                    fut = pool.submit(self.registry.execute, name, params)
                    result = fut.result(timeout=self.tool_timeout)
                self._record_tool_telemetry(name, call_start, success=True, outcome="completed")
            except TimeoutError:
                result = json.dumps({
                    "status": "error", "tool": name,
                    "error": f"timeout after {self.tool_timeout}s",
                })
                self._record_tool_telemetry(name, call_start, success=False, outcome="timeout", error=result)
            except Exception as exc:
                result = json.dumps({
                    "status": "error", "tool": name, "error": str(exc),
                })
                self._record_tool_telemetry(name, call_start, success=False, outcome="tool_error", error=str(exc))
            results.append({
                "role": "tool",
                "tool_call_id": call_id,
                "name": name,
                "content": result,
            })

        return results

    def _record_tool_telemetry(
        self, tool_name: str, call_start: float, *, success: bool, outcome: str, error: str = "",
    ) -> None:
        if not self._data_root:
            return
        record_step_safe(
            StepRecord(
                service=self._service_name,
                step_name=f"tool:{tool_name}",
                duration_sec=time.perf_counter() - call_start,
                success=success,
                outcome=outcome,
                error=error,
            ),
            db_path=Path(self._data_root) / "telemetry.db",
        )

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
        # Real context window (resolved by create_llm() from the backing
        # model's own /models endpoint, or an explicit config override) —
        # not a hardcoded guess. See __init__'s max_context_tokens.
        max_tokens = self.max_context_tokens

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
            result: list[dict] = [
                {"role": "system", "content": messages[0]["content"]},
            ]
            if self._ground_truth_system_msg is not None:
                result.append(self._ground_truth_system_msg)
            if self._facts_system_msg is not None:
                result.append(self._facts_system_msg)
            if self._freshness_system_msg is not None:
                result.append(self._freshness_system_msg)
            if self._research_digest_system_msg is not None:
                result.append(self._research_digest_system_msg)
            result.append(
                {"role": "system", "content": f"<compacted-summary>\n{summary}\n</compacted-summary>"}
            )
            result.append(messages[-1])
            return result
        except Exception:
            result = list(messages[-6:])
            if self._ground_truth_system_msg is not None:
                result.insert(1, self._ground_truth_system_msg)
            if self._facts_system_msg is not None:
                result.insert(1, self._facts_system_msg)
            if self._freshness_system_msg is not None:
                result.insert(1, self._freshness_system_msg)
            if self._research_digest_system_msg is not None:
                result.insert(1, self._research_digest_system_msg)
            return result

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

    def _record_llm_telemetry(
        self,
        *,
        prompt_tokens: int,
        completion_tokens: int,
        total_tokens: int,
        token_count_source: str,
        retry_count: int,
        latency_sec: float,
        success: bool,
        outcome: str,
        error: str = "",
    ) -> None:
        if not self._data_root:
            return
        record_llm_call_safe(
            LLMCallRecord(
                service=self._service_name,
                model=getattr(self.llm, "model", ""),
                base_url=getattr(self.llm, "base_url", ""),
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                token_count_source=token_count_source,
                retry_count=retry_count,
                latency_sec=latency_sec,
                success=success,
                outcome=outcome,
                error=error,
            ),
            db_path=Path(self._data_root) / "telemetry.db",
        )

    def _build_result(
        self,
        status: str,
        content: str,
        iterations: int,
        token_usage: TokenUsage,
        history: List[Dict],
    ) -> Dict:
        if self._data_root:
            record_step_safe(
                StepRecord(
                    service=self._service_name,
                    step_name="agent_loop_run",
                    duration_sec=time.perf_counter() - getattr(self, "_run_start_time", time.perf_counter()),
                    success=status == "completed",
                    # Explicit reason code, not just success/failure — the
                    # whole point of 05-advanced-aim-1-1: 04-advanced-aim-1's
                    # replay found 13/22 days ending without a real decision
                    # and only discovered it by re-reading raw traces after
                    # the fact, because nothing recorded *why* a run ended
                    # the way it did while it was happening.
                    outcome=status,
                    data_volume_in=len(history),
                    data_volume_out=len(content),
                ),
                db_path=Path(self._data_root) / "telemetry.db",
            )

        audit_findings: list[dict] = []
        if status in ("completed", "max_iterations") and content:
            try:
                from ..audit.fact_audit import FactAuditor
                auditor = FactAuditor()
                audit_findings = auditor.audit(
                    content, history,
                    session_id=getattr(self, "_session_id", ""),
                )
            except Exception:
                pass

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
            "trace": history,
            "audit": audit_findings,
        }
