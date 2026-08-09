"""Generic single-symbol walk-forward backtest loop.

Slides through history one step at a time: at each point, hand the caller
everything knowable up to that point plus the next `horizon` actual bars to
score against, collect what the caller returns, move forward one step,
repeat. All angle-specific logic (how to forecast, what counts as a hit,
whether/what to train) lives in the caller's `step_fn` — this module only
owns window slicing, refit cadence, and wiring tags/weights onto the output
rows.

Generic on purpose: this lives in `vinu_tools` and must not import anything
from `vinu-initial-analysis` (see 05-storage-enhancement-levels/plan.md for
why — that would create a circular package dependency). Tagging and
weight-persistence are accepted as plain callables instead.
"""

from __future__ import annotations

import os
import pickle
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Literal

import pandas as pd


def _default_n_workers(n_workers: int | None) -> int:
    """Resolve `n_workers=None` to a hardware-aware default: all logical
    cores except one, so the pool doesn't claim every core on the
    machine and starve the caller's own process (and anything else
    running on it) -- rather than ProcessPoolExecutor's own default of
    `os.cpu_count()` (every core). Explicit `n_workers` always wins.
    """
    if n_workers is not None:
        return n_workers
    cpu_count = os.cpu_count() or 1
    return max(1, cpu_count - 1)


def _chunk_checkpoint_path(checkpoint_dir: Path, key: str, start: int, end: int) -> Path:
    safe_key = "".join(c if c.isalnum() or c in "-_." else "_" for c in key)
    return checkpoint_dir / f"{safe_key}__{start}_{end}.pkl"


def _atomic_write_checkpoint(path: Path, rows: list[dict[str, Any]]) -> None:
    """Writes one chunk's completed rows to disk without ever leaving a
    partial/corrupt checkpoint file at `path` -- the exact same lesson
    (and the exact same fix: temp file in the same directory + os.replace)
    as the real corrupt-live-parquet-file bug found and fixed earlier
    this session (known-issues.md Resolved #3). A crash mid-write here
    must not poison a future resume by leaving a checkpoint that looks
    present but reads back broken.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    os.close(fd)
    tmp_path = Path(tmp_name)
    try:
        with open(tmp_path, "wb") as f:
            pickle.dump(rows, f)
        os.replace(tmp_path, path)
    except BaseException:
        tmp_path.unlink(missing_ok=True)
        raise


def _load_checkpoint(path: Path) -> list[dict[str, Any]] | None:
    """Returns the checkpointed rows, or None if there's nothing usable
    (missing, or corrupt -- e.g. a partial write from a run that was
    killed before this module's atomic-write fix existed, or a file from
    an incompatible pickle version). None means "recompute this chunk",
    same as if it had never been checkpointed -- a corrupt checkpoint
    must never silently poison a resume.
    """
    if not path.is_file():
        return None
    try:
        with open(path, "rb") as f:
            return pickle.load(f)
    except Exception:
        return None


@dataclass
class ChunkFailure:
    key: str
    """The WalkForwardJob.key this failed chunk belongs to."""
    start_position: int
    end_position: int
    attempts: int
    error: str


@dataclass
class BatchResult:
    data: dict[str, pd.DataFrame]
    """job.key -> DataFrame of every successfully-computed row. May be
    incomplete for a job with failed chunks (see `failures`) -- never
    silently dropped in favor of raising, so already-completed work from
    other chunks/jobs in the same batch is never thrown away just
    because one chunk failed."""
    failures: list[ChunkFailure] = field(default_factory=list)
    """Chunks that failed even after retries were exhausted. Empty means
    every chunk in the batch succeeded."""

    @property
    def ok(self) -> bool:
        return not self.failures


@dataclass
class WalkForwardStep:
    step_index: int
    history: pd.DataFrame
    """Bars up to and including this step (bar_ts, close, ...), oldest first."""
    future: pd.DataFrame
    """The next `horizon` actual bars, for scoring the forecast against."""
    bar_ts: int
    """bar_ts of the last row in `history` — the point the forecast is made from."""
    is_refit_step: bool
    """False when refit_cadence > 1 and this step reuses `prior_state`."""
    prior_state: Any | None
    """Whatever the previous step's StepResult.state was, or None on the first step."""


@dataclass
class StepResult:
    row: dict[str, Any]
    """The angle's own fields only (forecast/CI/hit/...) — no tags, no weights_ref; those are added by the harness."""
    weights: Any | None = None
    state: Any | None = None
    """Carried forward as the next step's `prior_state`."""


StepFn = Callable[[WalkForwardStep], StepResult]
TagFn = Callable[[int], dict[str, Any]]
WeightsSink = Callable[[str, str, int, Any], str]


@dataclass
class WalkForwardJob:
    key: str
    """Caller-chosen identifier for this job (e.g. the symbol, or
    "{symbol}:{angle}") -- results come back keyed by this, not
    positionally, so jobs can be submitted in any order and may even
    mix different angles/step_fns in one batch, not just different
    symbols of the same angle."""
    symbol: str
    timeframe: str
    bars: pd.DataFrame
    step_fn: StepFn
    min_observations: int
    window: int
    horizon: int = 1
    tag_fn: TagFn | None = None
    chunk_size: int = 200


def run_walk_forward(
    symbol: str,
    timeframe: str,
    bars: pd.DataFrame,
    step_fn: StepFn,
    *,
    min_observations: int,
    horizon: int = 1,
    refit_cadence: int = 1,
    window: Literal["expanding"] | int = "expanding",
    tag_fn: TagFn | None = None,
    weights_sink: WeightsSink | None = None,
) -> pd.DataFrame:
    """Runs a walk-forward backtest, returning one row per step.

    bars must have a `bar_ts` (int) column plus whatever price columns
    step_fn needs, sorted ascending. A step is only emitted once a full
    `horizon`-bar future window is available to score against — the final
    `horizon - 1` bars of `bars` never become decision points, since there
    isn't enough real future data left to check them against.

    Each output row = symbol/timeframe/bar_ts/step_index, merged with
    tag_fn(bar_ts) (if given), merged with step_fn's own row dict, plus
    weights_ref = weights_sink(symbol, timeframe, bar_ts, weights) when
    step_fn returns weights and a sink was provided.
    """
    if min_observations < 1:
        raise ValueError("min_observations must be >= 1")
    if horizon < 1:
        raise ValueError("horizon must be >= 1")
    if refit_cadence < 1:
        raise ValueError("refit_cadence must be >= 1")

    n = len(bars)
    rows: list[dict[str, Any]] = []
    state: Any | None = None
    step_index = 0

    # position is the index (0-based) of the last bar included in `history`
    position = min_observations - 1
    while position < n and position + horizon < n:
        if isinstance(window, int):
            start = max(0, position + 1 - window)
        else:
            start = 0
        history = bars.iloc[start : position + 1]
        future = bars.iloc[position + 1 : position + 1 + horizon]
        bar_ts = int(history.iloc[-1]["bar_ts"])
        is_refit_step = step_index % refit_cadence == 0

        step = WalkForwardStep(
            step_index=step_index,
            history=history,
            future=future,
            bar_ts=bar_ts,
            is_refit_step=is_refit_step,
            prior_state=state,
        )
        result = step_fn(step)
        state = result.state

        row: dict[str, Any] = {
            "symbol": symbol,
            "timeframe": timeframe,
            "bar_ts": bar_ts,
            "step_index": step_index,
        }
        if tag_fn is not None:
            row.update(tag_fn(bar_ts))
        row.update(result.row)
        if result.weights is not None and weights_sink is not None:
            row["weights_ref"] = weights_sink(symbol, timeframe, bar_ts, result.weights)

        rows.append(row)
        step_index += 1
        position += 1

    return pd.DataFrame(rows)


def _run_position_range(
    symbol: str,
    timeframe: str,
    bars: pd.DataFrame,
    step_fn: StepFn,
    *,
    window: int,
    horizon: int,
    tag_fn: TagFn | None,
    first_position: int,
    start_position: int,
    end_position: int,
) -> list[dict[str, Any]]:
    """One worker's share of the loop body in run_walk_forward_parallel --
    module-level (not a closure) so it survives being pickled to a
    separate process. Runs positions [start_position, end_position),
    computing each one's own bounded window directly (cheap, since
    `window` is fixed) rather than depending on any other worker's output.
    """
    rows: list[dict[str, Any]] = []
    for position in range(start_position, end_position):
        start = max(0, position + 1 - window)
        history = bars.iloc[start : position + 1]
        future = bars.iloc[position + 1 : position + 1 + horizon]
        bar_ts = int(history.iloc[-1]["bar_ts"])
        step_index = position - first_position

        step = WalkForwardStep(
            step_index=step_index,
            history=history,
            future=future,
            bar_ts=bar_ts,
            is_refit_step=True,
            prior_state=None,
        )
        result = step_fn(step)

        row: dict[str, Any] = {
            "symbol": symbol,
            "timeframe": timeframe,
            "bar_ts": bar_ts,
            "step_index": step_index,
        }
        if tag_fn is not None:
            row.update(tag_fn(bar_ts))
        row.update(result.row)
        rows.append(row)

    return rows


def _execute_with_retry(
    executor: Any,
    tasks: list[tuple[str, int, int, int]],
    job_by_key: dict[str, WalkForwardJob],
    max_retries: int,
    on_success: Callable[[str, int, int, list[dict[str, Any]]], None] | None = None,
) -> tuple[dict[str, list[dict[str, Any]]], list[ChunkFailure]]:
    """Runs `tasks` (key, first_position, start, end) through an already-
    open executor, retrying a failed chunk up to `max_retries` times
    before giving up on it -- shared by run_walk_forward_parallel and
    run_walk_forward_parallel_batch so both get the same fault-isolation
    behavior instead of two separate hand-rolled versions.

    A chunk failing (even permanently) never aborts the others: every
    other chunk's result is still collected. `on_success`, if given, is
    called with each chunk's own rows right after it completes -- used by
    the batch function to checkpoint to disk incrementally, not just at
    the very end.
    """
    from concurrent.futures import FIRST_COMPLETED, wait

    results: dict[str, list[dict[str, Any]]] = {key: [] for key in job_by_key}
    failures: list[ChunkFailure] = []
    attempt_counts: dict[tuple[str, int, int], int] = {}
    future_to_task: dict[Any, tuple[str, int, int, int]] = {}

    def _submit(key: str, first_position: int, start: int, end: int) -> Any:
        job = job_by_key[key]
        future = executor.submit(
            _run_position_range,
            job.symbol, job.timeframe, job.bars, job.step_fn,
            window=job.window, horizon=job.horizon, tag_fn=job.tag_fn,
            first_position=first_position, start_position=start, end_position=end,
        )
        future_to_task[future] = (key, first_position, start, end)
        return future

    pending = set()
    for key, first_position, start, end in tasks:
        attempt_counts[(key, start, end)] = 1
        pending.add(_submit(key, first_position, start, end))

    while pending:
        done, pending = wait(pending, return_when=FIRST_COMPLETED)
        for future in done:
            key, first_position, start, end = future_to_task.pop(future)
            task_id = (key, start, end)
            try:
                rows = future.result()
                results[key].extend(rows)
                if on_success is not None:
                    on_success(key, start, end, rows)
            except Exception as exc:
                if attempt_counts[task_id] <= max_retries:
                    attempt_counts[task_id] += 1
                    pending.add(_submit(key, first_position, start, end))
                else:
                    failures.append(ChunkFailure(
                        key=key, start_position=start, end_position=end,
                        attempts=attempt_counts[task_id], error=f"{type(exc).__name__}: {exc}",
                    ))

    return results, failures


def run_walk_forward_parallel(
    symbol: str,
    timeframe: str,
    bars: pd.DataFrame,
    step_fn: StepFn,
    *,
    min_observations: int,
    window: int,
    horizon: int = 1,
    tag_fn: TagFn | None = None,
    chunk_size: int = 200,
    n_workers: int | None = None,
    max_retries: int = 2,
) -> pd.DataFrame:
    """Chunked-parallel version of run_walk_forward -- same output shape,
    computed by splitting the step range across a process pool instead of
    one sequential loop.

    Only valid for a FIXED `window` (an int, same as run_walk_forward's
    own `window=<int>` mode), never `"expanding"` -- with a fixed window
    each step's history is already a bounded, self-contained slice, so
    chunks can be computed independently with zero cross-chunk dependency
    and zero duplicated work. An expanding window has no such bound (every
    step's history is everything since t=0), so chunking it would silently
    cap what later steps actually see -- call run_walk_forward instead for
    those angles, or resolve that as a deliberate methodology decision
    first, not something this function does implicitly.

    `step_fn` (and `tag_fn`, if given) must be plain module-level functions
    (importable by reference), not closures or lambdas -- each worker
    process pickles a reference to them, not any captured state. Confirmed
    directly: a lambda `tag_fn` fails with `AttributeError: Can't get
    local object` from the pickler. `refit_cadence`/`prior_state` chaining
    and `weights_sink` are not supported here yet: every step runs with
    `is_refit_step=True, prior_state=None`, correct for angles that refit
    fresh every step (refit_cadence=1, the common case) but not yet wired
    for cadence>1's cross-step state reuse.

    **Fault tolerance**: a failed chunk (an exception in step_fn, a
    worker process dying outright) is retried up to `max_retries` times
    before this function gives up -- confirmed directly (this session)
    that without this, a single bad chunk raised and threw away every
    other chunk's already-computed result too. If any chunk still fails
    after retries, this raises RuntimeError listing every failed chunk
    (not just the first) -- callers that want partial results instead of
    an exception should use run_walk_forward_parallel_batch (wraps this
    one job in a batch of one and returns a BatchResult with `.data`/
    `.failures` instead of raising).

    Results come back in the same step order as run_walk_forward would
    produce, and (for the fixed-window angles this is valid for) are
    row-for-row identical -- this only changes how the work is scheduled,
    not what gets computed.
    """
    from concurrent.futures import ProcessPoolExecutor

    if not isinstance(window, int):
        raise ValueError(
            "run_walk_forward_parallel requires a fixed int `window` -- "
            "expanding-window angles change semantics under chunking; "
            "use run_walk_forward for those."
        )
    if min_observations < 1:
        raise ValueError("min_observations must be >= 1")
    if horizon < 1:
        raise ValueError("horizon must be >= 1")

    n = len(bars)
    first_position = min_observations - 1
    last_position_exclusive = n - horizon  # position must satisfy position + horizon < n
    if last_position_exclusive <= first_position:
        return pd.DataFrame()

    ranges: list[tuple[int, int]] = []
    pos = first_position
    while pos < last_position_exclusive:
        end = min(pos + chunk_size, last_position_exclusive)
        ranges.append((pos, end))
        pos = end

    job = WalkForwardJob(
        key=symbol, symbol=symbol, timeframe=timeframe, bars=bars, step_fn=step_fn,
        min_observations=min_observations, window=window, horizon=horizon,
        tag_fn=tag_fn, chunk_size=chunk_size,
    )
    tasks = [(symbol, first_position, start, end) for start, end in ranges]

    with ProcessPoolExecutor(max_workers=_default_n_workers(n_workers)) as executor:
        results, failures = _execute_with_retry(executor, tasks, {symbol: job}, max_retries)

    if failures:
        detail = "; ".join(
            f"[{f.start_position},{f.end_position}) attempts={f.attempts}: {f.error}"
            for f in failures
        )
        raise RuntimeError(
            f"run_walk_forward_parallel: {len(failures)} chunk(s) for {symbol!r} "
            f"failed after retries: {detail}"
        )

    df = pd.DataFrame(results[symbol])
    if not df.empty:
        df = df.sort_values("step_index").reset_index(drop=True)
    return df


def run_walk_forward_parallel_batch(
    jobs: list[WalkForwardJob],
    *,
    n_workers: int | None = None,
    min_total_steps_for_parallel: int = 1500,
    max_retries: int = 2,
    checkpoint_dir: str | Path | None = None,
    resume: bool = True,
) -> BatchResult:
    """Runs multiple walk-forward jobs through ONE shared process pool --
    this is the actual lever, not run_walk_forward_parallel's own
    single-job form. A fresh pool per single-symbol call pays its
    worker-import/model-load tax (~4-6s/worker, measured directly on a
    real pretrained-model angle) on *every* call -- measured to be worse
    than plain sequential for one symbol at a time (40.98s parallel vs
    32.30s sequential, 3 real symbols run one call each). Sharing one pool
    across a whole batch of jobs amortizes that fixed tax across all of
    it instead (measured: 24.02-26.23s for the same 3 symbols in one
    batch -- 1.26-1.34x faster than sequential, ~1.6-1.7x faster than
    fresh-pool-per-call).

    Things this function decides on the caller's behalf, so callers don't
    have to re-derive the tradeoffs above every time:

    1. **Whether to parallelize at all.** If the batch's total step count
       is below `min_total_steps_for_parallel`, this runs every job
       sequentially in-process (via run_walk_forward, one call per job,
       same interpreter -- so a cached model/import from job 1 is still
       reused by job 2, same as this session's sequential baseline)
       instead of paying for a process pool that measured worse than
       just not bothering. This is a **total-work** decision, not a
       job-count one -- a single job with enough steps still takes the
       process-pool path (same reasoning run_walk_forward_parallel
       already relies on for one job's own chunks), it isn't forced
       sequential just for being alone. The default threshold (1500) is
       a conservative rule of thumb sitting between the two real
       measured points -- one ~921-step job was a net loss, three jobs
       totaling ~2,783 steps was a real win -- not a precise universal
       constant. The sequential-fallback path does not retry or
       checkpoint -- it's the "small enough that none of this matters"
       case by construction. **Exception**: if `checkpoint_dir` is given,
       this size-based decision is skipped entirely and the process-pool
       path always runs, regardless of size -- passing `checkpoint_dir`
       is the caller explicitly asking for retry/resume safety, which
       only exists on that path.
    2. **How many workers to use**, via `_default_n_workers`.
    3. **Fault tolerance**: each chunk that fails is retried up to
       `max_retries` times. A chunk that still fails after that is
       recorded in the returned `BatchResult.failures`, not raised --
       confirmed directly (this session) that without this, one job's
       failing chunk silently discarded another, already-fully-computed
       job's entire result too. Check `result.ok` (or `result.failures`)
       rather than assuming success.
    4. **Checkpoint/resume**, when `checkpoint_dir` is given: every
       chunk's rows are written to disk (atomically -- see
       `_atomic_write_checkpoint`, same temp-file+os.replace fix as the
       real corrupt-parquet bug found and fixed earlier this session) as
       soon as that chunk completes. On a later call with the same
       `checkpoint_dir` and `resume=True` (the default), any chunk whose
       checkpoint already exists is loaded from disk instead of
       recomputed -- so a crashed or killed batch can be re-run and only
       pays for the work it hadn't finished yet. Pass `resume=False` to
       ignore (and overwrite) any existing checkpoints for this batch's
       exact chunks and start clean. A corrupt/partial checkpoint file is
       treated as missing (recomputed), never trusted as-is.

    Each job's own (symbol, timeframe, bars, step_fn, min_observations,
    window, horizon, tag_fn) behave exactly like run_walk_forward_parallel's
    -- same fixed-window-only requirement (raises otherwise), same
    module-level-function requirement for step_fn/tag_fn. Jobs may use
    entirely different step_fns/angles, not just different symbols of the
    same one -- this function only cares about scheduling all of it
    across one pool.

    Returns a BatchResult: `.data` is {job.key: DataFrame} (each
    row-for-row identical to what run_walk_forward would produce for
    that job, whichever path actually ran it), `.failures` lists any
    chunk that never succeeded even after retries.
    """
    from concurrent.futures import ProcessPoolExecutor

    for job in jobs:
        if not isinstance(job.window, int):
            raise ValueError(
                f"job {job.key!r}: run_walk_forward_parallel_batch requires a "
                "fixed int window -- expanding-window angles change semantics "
                "under chunking; use run_walk_forward for those."
            )

    job_by_key = {job.key: job for job in jobs}
    tasks: list[tuple[str, int, int, int]] = []  # (key, first_position, start, end)
    for job in jobs:
        n = len(job.bars)
        first_position = job.min_observations - 1
        last_position_exclusive = n - job.horizon
        pos = first_position
        while pos < last_position_exclusive:
            end = min(pos + job.chunk_size, last_position_exclusive)
            tasks.append((job.key, first_position, pos, end))
            pos = end

    total_steps = sum(end - start for _, _, start, end in tasks)
    # A total-work decision, not a job-count one -- a single job with
    # enough steps still takes the process-pool path below (see the
    # docstring for why len(jobs) alone must never force this branch).
    # checkpoint_dir means the caller explicitly wants retry/checkpoint
    # safety -- that only exists on the process-pool path, so a given
    # checkpoint_dir always takes that path regardless of size, overriding
    # this size-based sequential-fallback decision entirely.
    if checkpoint_dir is None and total_steps < min_total_steps_for_parallel:
        data = {}
        failures: list[ChunkFailure] = []
        for job in jobs:
            try:
                data[job.key] = run_walk_forward(
                    job.symbol, job.timeframe, job.bars, job.step_fn,
                    min_observations=job.min_observations, window=job.window,
                    horizon=job.horizon, tag_fn=job.tag_fn,
                )
            except Exception as exc:
                data[job.key] = pd.DataFrame()
                failures.append(ChunkFailure(
                    key=job.key, start_position=job.min_observations - 1,
                    end_position=len(job.bars), attempts=1,
                    error=f"{type(exc).__name__}: {exc}",
                ))
        return BatchResult(data=data, failures=failures)

    checkpoint_path = Path(checkpoint_dir) if checkpoint_dir is not None else None
    if checkpoint_path is not None:
        checkpoint_path.mkdir(parents=True, exist_ok=True)
        if not resume:
            for key, _first_position, start, end in tasks:
                _chunk_checkpoint_path(checkpoint_path, key, start, end).unlink(missing_ok=True)

    results: dict[str, list[dict[str, Any]]] = {job.key: [] for job in jobs}
    pending_tasks: list[tuple[str, int, int, int]] = []
    for key, first_position, start, end in tasks:
        loaded = None
        if checkpoint_path is not None:
            loaded = _load_checkpoint(_chunk_checkpoint_path(checkpoint_path, key, start, end))
        if loaded is not None:
            results[key].extend(loaded)
        else:
            pending_tasks.append((key, first_position, start, end))

    def _on_success(key: str, start: int, end: int, rows: list[dict[str, Any]]) -> None:
        if checkpoint_path is not None:
            _atomic_write_checkpoint(_chunk_checkpoint_path(checkpoint_path, key, start, end), rows)

    failures = []
    if pending_tasks:
        with ProcessPoolExecutor(max_workers=_default_n_workers(n_workers)) as executor:
            fresh_results, failures = _execute_with_retry(
                executor, pending_tasks, job_by_key, max_retries, on_success=_on_success
            )
        for key, rows in fresh_results.items():
            results[key].extend(rows)

    data = {}
    for job in jobs:
        df = pd.DataFrame(results[job.key])
        if not df.empty and "step_index" in df.columns:
            df = df.sort_values("step_index").reset_index(drop=True)
        data[job.key] = df

    return BatchResult(data=data, failures=failures)
