"""Cross-service contract scan (Phase 1, static): does every call reach a real route, with fields the route accepts?

Two halves, both taken from the code itself so they cannot drift:

* PRODUCERS: build every service's FastAPI app and read its OpenAPI document. Per route: method, path, query
  parameters (+ which are required), and the JSON body fields (+ which are required).
* CONSUMERS: parse every service's source with `ast`, find each HTTP call (`.get/.post/.put/.patch/.delete/.request`)
  whose URL resolves to a path, and read the query keys (`params=` or `?a=..` in the URL) and the JSON body keys
  (`json=`) it sends.

`compare()` then reports, per call: path/method with no route, required fields not sent (the route would answer
422), and fields sent that the route does not declare (silently ignored: the data is dropped).

Limits, stated plainly: only calls whose URL and field names are visible in the source are checked (a URL passed
through a helper function, a body built from `**kwargs`, or a field whose value is the wrong type are not); it checks
Phase 1 shape, not behaviour with real data. Calls it could not fully read are marked `dynamic` and never produce a
"missing field" finding.

Run:  python -m vinu_infra.contract_scan --root <vinu-components> --out <folder>   (writes contracts.json and
02-contract-registry.md into <folder>; exits 1 if there are ERROR findings not listed in the allowlist).
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import re
import subprocess
import sys
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

# name -> (directory, app module).  `create_app()` is called with temp data roots.
SERVICES: dict[str, tuple[str, str]] = {
    "stock-price": ("vinu-stock-price", "vinu_stock.server.app"),
    "news": ("vinu-news", "vinu_news.server.app"),
    "initial-analysis": ("vinu-initial-analysis", "vinu_initial_analysis.server.app"),
    "tools": ("vinu-tools", "vinu_tools.server.app"),
    "strategy": ("vinu-strategy", "vinu_strategy.server.app"),
    "simulator": ("vinu-simulator", "vinu_simulator.server.app"),
    "research": ("vinu-research", "vinu_research.server.app"),
    "agent": ("vinu-agent", "vinu_agent.server.app"),
    "portfolio": ("vinu-portfolio", "vinu_portfolio.server.app"),
    "live": ("vinu-live", "vinu_live.server.app"),
    "screener": ("vinu-screener", "vinu_screener.server.app"),
    "reflection": ("vinu-reflection", "vinu_reflection.server.app"),
    "models": ("vinu-models", "vinu_models.server.app"),
}

HTTP_VERBS = {"get", "post", "put", "patch", "delete"}
SKIP_DIRS = {".venv", "site-packages", "node_modules", "tests", "__pycache__", "build", "dist", "vinu-ui", "scripts"}

_DUMP_CODE = """
import json, sys, importlib
app = importlib.import_module(sys.argv[1]).create_app()
print('OPENAPI_JSON=' + json.dumps(app.openapi()))
"""


# ----------------------------------------------------------------------------------------------- producers

@dataclass
class Route:
    service: str
    method: str
    path: str
    query: dict[str, bool] = field(default_factory=dict)        # name -> required
    body: dict[str, bool] | None = None                          # field -> required (None = no body)
    body_open: bool = False                                      # body is an untyped object: any key accepted
    callers: int = 0

    @property
    def norm(self) -> str:
        return norm_path(self.path)


def norm_path(p: str) -> str:
    p = p.split("?")[0]
    p = re.sub(r"\{[^}]*\}", "{}", p)
    return p.rstrip("/") or "/"


def _resolve(schema: dict, components: dict, depth: int = 0) -> dict:
    if depth > 6 or not isinstance(schema, dict):
        return schema or {}
    if "$ref" in schema:
        return _resolve(components.get(schema["$ref"].split("/")[-1], {}), components, depth + 1)
    for key in ("anyOf", "oneOf"):
        if key in schema:
            options = [o for o in schema[key] if o.get("type") != "null"]
            if options:
                return _resolve(options[0], components, depth + 1)
    if "allOf" in schema and schema["allOf"]:
        merged: dict[str, Any] = {"properties": {}, "required": []}
        for part in schema["allOf"]:
            part = _resolve(part, components, depth + 1)
            merged["properties"].update(part.get("properties", {}))
            merged["required"] += part.get("required", [])
        return merged
    return schema


def routes_from_openapi(service: str, doc: dict) -> list[Route]:
    components = doc.get("components", {}).get("schemas", {})
    out: list[Route] = []
    for path, ops in doc.get("paths", {}).items():
        for method, op in ops.items():
            if method.lower() not in HTTP_VERBS:
                continue
            r = Route(service=service, method=method.upper(), path=path)
            for prm in op.get("parameters", []):
                if prm.get("in") == "query":
                    r.query[prm["name"]] = bool(prm.get("required"))
            rb = op.get("requestBody")
            if rb:
                content = rb.get("content", {})
                js = content.get("application/json")
                if js is not None:
                    sch = _resolve(js.get("schema", {}), components)
                    props = sch.get("properties")
                    if props:
                        req = set(sch.get("required", []))
                        r.body = {k: (k in req) for k in props}
                    else:
                        r.body, r.body_open = {}, True
                else:
                    r.body, r.body_open = {}, True            # form / multipart / file: not checked
            out.append(r)
    return out


def dump_openapi(root: Path, services: dict[str, tuple[str, str]], python_for: dict[str, str] | None = None,
                 timeout: int = 240) -> tuple[dict[str, dict], dict[str, str]]:
    """Build each app in a subprocess; returns ({service: openapi}, {service: error})."""
    root = Path(root).resolve()
    docs: dict[str, dict] = {}
    errors: dict[str, str] = {}
    sibling = os.pathsep.join(str(root / d) for d in os.listdir(root) if d.startswith("vinu-") and (root / d).is_dir())
    for name, (d, mod) in services.items():
        tmp = tempfile.mkdtemp()
        env = {**os.environ, "PYTHONPATH": sibling, "PYTHONIOENCODING": "utf-8", "VINU_DATA_ROOT": tmp}
        for var in ("STOCK", "NEWS", "INITIAL_ANALYSIS", "RESEARCH", "AGENT", "PORTFOLIO", "LIVE", "SCREENER",
                    "REFLECTION", "STRATEGY", "TOOLS", "SIMULATOR", "STOCK_PRICE"):
            env[f"VINU_{var}_DATA_ROOT"] = tmp
        env["VINU_NEWS_DB_PATH"] = os.path.join(tmp, "news.db")
        py = (python_for or {}).get(name, sys.executable)
        try:
            p = subprocess.run([py, "-c", _DUMP_CODE, mod], cwd=root / d, env=env, capture_output=True, text=True,
                               timeout=timeout)
        except subprocess.TimeoutExpired:
            errors[name] = "timeout"
            continue
        line = [l for l in p.stdout.splitlines() if l.startswith("OPENAPI_JSON=")]
        if line:
            docs[name] = json.loads(line[0][len("OPENAPI_JSON="):])
        else:
            tail = (p.stderr or p.stdout).strip().splitlines()[-1:] or ["?"]
            errors[name] = tail[0][:300]
    return docs, errors


# ----------------------------------------------------------------------------------------------- consumers

@dataclass
class Call:
    service: str                 # the service whose code makes the call
    file: str
    line: int
    method: str
    path: str                    # normalised, '{}' for every dynamic segment
    raw_path: str
    query: list[str] = field(default_factory=list)
    body: list[str] | None = None
    dynamic_query: bool = False
    dynamic_body: bool = False


def _render(node: ast.AST, env: dict[str, ast.AST], depth: int = 0) -> str | None:
    """A URL expression as a template string: constants kept, every other piece '{}'."""
    if depth > 4:
        return None
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        out = ""
        for part in node.values:
            if isinstance(part, ast.Constant):
                out += str(part.value)
            elif isinstance(part, ast.FormattedValue):
                inner = part.value
                if isinstance(inner, ast.Name) and inner.id in env:
                    sub = _render(env[inner.id], env, depth + 1)
                    out += sub if sub is not None else "{}"
                else:
                    out += "{}"
        return out
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left, right = _render(node.left, env, depth + 1), _render(node.right, env, depth + 1)
        if right is not None:
            return (left if left is not None else "{}") + right
        return None
    if isinstance(node, ast.Name) and node.id in env:
        return _render(env[node.id], env, depth + 1)
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in ("format",):
        return _render(node.func.value, env, depth + 1)
    return None


def _dict_keys(node: ast.AST, env: dict[str, ast.AST], extra: dict[str, set[str]]) -> tuple[list[str], bool] | None:
    """(keys, dynamic) for a dict literal / name bound to one; None if it cannot be read at all."""
    name = None
    if isinstance(node, ast.Name):
        name = node.id
        node = env.get(node.id)
    if isinstance(node, ast.Dict):
        keys, dynamic = [], False
        for k in node.keys:
            if k is None:
                dynamic = True                          # **unpacking
            elif isinstance(k, ast.Constant) and isinstance(k.value, str):
                keys.append(k.value)
            else:
                dynamic = True
        if name and name in extra:
            keys += sorted(extra[name])
        return keys, dynamic
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "dict":
        keys = [kw.arg for kw in node.keywords if kw.arg]
        return keys, any(kw.arg is None for kw in node.keywords)
    return None


_KEY_IN_URL = re.compile(r"[?&]([A-Za-z_][A-Za-z0-9_\-]*)=")


def _decorator_call_ids(tree: ast.AST) -> set[int]:
    ids: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            for dec in node.decorator_list:
                for sub in ast.walk(dec):
                    ids.add(id(sub))
    return ids


def _scan_function(body_nodes: list[ast.stmt], service: str, file: str, calls: list[Call], known_first: set[str],
                   skip: set[int] | None = None) -> None:
    env: dict[str, ast.AST] = {}
    extra: dict[str, set[str]] = {}
    skip = skip or set()
    for stmt in body_nodes:
        for node in ast.walk(stmt):
            if id(node) in skip:
                continue
            if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.value is not None:
                env[node.target.id] = node.value
            elif isinstance(node, ast.Assign) and len(node.targets) == 1:
                t = node.targets[0]
                if isinstance(t, ast.Name):
                    env[t.id] = node.value
                elif (isinstance(t, ast.Subscript) and isinstance(t.value, ast.Name)
                      and isinstance(t.slice, ast.Constant) and isinstance(t.slice.value, str)):
                    extra.setdefault(t.value.id, set()).add(t.slice.value)
            elif isinstance(node, ast.Call):
                _maybe_call(node, env, extra, service, file, calls, known_first)


def _maybe_call(node: ast.Call, env, extra, service, file, calls, known_first) -> None:
    is_attr = isinstance(node.func, ast.Attribute)
    attr = node.func.attr if is_attr else getattr(node.func, "id", "")
    method = None
    url_node = None
    helper = False
    if is_attr and attr in HTTP_VERBS and node.args:
        method, url_node = attr.upper(), node.args[0]
    elif is_attr and attr == "request" and len(node.args) >= 2 and isinstance(node.args[0], ast.Constant) \
            and isinstance(node.args[0].value, str):
        method, url_node = node.args[0].value.upper(), node.args[1]
    elif node.args:
        # A helper that takes the URL in its first or second argument, e.g. `_fetch_json(f"{base}/live/decisions/..")` or
        # `_post(client, "/research/signal-evidence/{id}/outcome")`. The argument must start with a base-url placeholder, or
        # be a path of at least two segments whose first segment is a service prefix, so a log line or a dict key can never
        # look like a call.
        for cand in node.args[:2]:
            text = _render(cand, env)
            if not text or " " in text:               # a path has no spaces: a log message must never look like a call
                continue
            if text.startswith("{}/") or (text.startswith("/") and text.strip("/").count("/") >= 1
                                          and text.strip("/").split("/")[0] in known_first):
                method, url_node, helper = "ANY", cand, True
                break
    if method is None or url_node is None:
        return
    rendered = _render(url_node, env)
    if not rendered:
        return
    # drop the leading {} base-url placeholders, keep the path that starts at the first literal '/'
    m = re.match(r"^(?:\{\})*(/.*)$", rendered)
    if not m:
        return
    raw = m.group(1)
    path_part = raw.split("?")[0]
    first = path_part.strip("/").split("/")[0]
    if first not in known_first and not path_part.startswith("/"):
        return
    if helper and (first not in known_first or "/" not in path_part.strip("/")):
        return           # not one of our routes (or a bare service prefix: a client constructor's base URL)
    call = Call(service=service, file=file, line=node.lineno, method=method, path=norm_path(path_part), raw_path=raw)
    call.query = _KEY_IN_URL.findall(raw)
    if helper:
        call.dynamic_query = call.dynamic_body = True       # the helper decides which fields it adds
    for kw in node.keywords:
        if kw.arg == "params":
            r = _dict_keys(kw.value, env, extra)
            if r is None:
                call.dynamic_query = True
            else:
                call.query += r[0]
                call.dynamic_query = call.dynamic_query or r[1]
        elif kw.arg == "json":
            r = _dict_keys(kw.value, env, extra)
            if r is None:
                call.body, call.dynamic_body = [], True
            else:
                call.body, call.dynamic_body = r[0], r[1]
        elif kw.arg is None:
            call.dynamic_query = call.dynamic_body = True
    if "?" in raw and re.search(r"\?\{\}", raw):
        call.dynamic_query = True
    calls.append(call)


def scan_callers(root: Path, known_first: set[str]) -> list[Call]:
    calls: list[Call] = []
    for svc_dir in sorted(p for p in root.iterdir() if p.is_dir() and p.name.startswith("vinu-")):
        if svc_dir.name in SKIP_DIRS:
            continue
        for f in svc_dir.rglob("*.py"):
            if any(part in SKIP_DIRS or part.endswith(".egg-info") for part in f.relative_to(svc_dir).parts[:-1]):
                continue
            if f.relative_to(svc_dir).parts[:1] == ("vinu_infra",):       # stray duplicate folder
                continue
            try:
                tree = ast.parse(f.read_text(encoding="utf-8", errors="ignore"))
            except SyntaxError:
                continue
            rel = str(f.relative_to(root)).replace("\\", "/")
            svc = svc_dir.name.removeprefix("vinu-")
            skip = _decorator_call_ids(tree)
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    _scan_function(node.body, svc, rel, calls, known_first, skip)
            # module level statements
            _scan_function([s for s in tree.body if not isinstance(s, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))],
                           svc, rel, calls, known_first, skip)
    # the same call can be reached twice (nested functions): dedupe
    seen, uniq = set(), []
    for c in calls:
        key = (c.file, c.line, c.method, c.path)
        if key not in seen:
            seen.add(key)
            uniq.append(c)
    return uniq


# ----------------------------------------------------------------------------------------------- compare

@dataclass
class Finding:
    level: str                   # ERROR | WARN
    kind: str
    call: Call
    route: str | None
    detail: str


def match_routes(call: Call, routes: list[Route]) -> tuple[list[Route], bool]:
    """Routes this call can mean. Second value: matched only by path suffix (base-prefixed client)."""
    if call.path.strip("/") in ("", "{}"):
        return [], True                       # a bare '/{x}' on a base-prefixed client says nothing about the route
    exact = [r for r in routes if segments_match(call.path, r.norm)]
    if exact:
        return exact, False
    suffix = [r for r in routes if call.path.count("/") >= 2 and _suffix_match(call.path, r.norm)]
    return suffix, True


def segments_match(call_path: str, route_norm: str) -> bool:
    """Same number of segments; a route '{}' accepts any literal (an angle name filled into the template), and a call
    '{}' accepts any route segment."""
    a, b = call_path.strip("/").split("/"), route_norm.strip("/").split("/")
    return len(a) == len(b) and all(x == y or y == "{}" or x == "{}" for x, y in zip(a, b))


def _suffix_match(call_path: str, route_norm: str) -> bool:
    a, b = call_path.strip("/").split("/"), route_norm.strip("/").split("/")
    tail = b[-len(a):]
    # at least one literal segment must agree, otherwise '/chat/completions' would "match" any all-template tail
    return (len(a) < len(b) and segments_match("/" + "/".join(a), "/" + "/".join(tail))
            and any(x == y and x != "{}" for x, y in zip(a, tail)))


def compare(calls: list[Call], routes: list[Route]) -> tuple[list[Finding], list[tuple[Call, Route]]]:
    findings: list[Finding] = []
    matched: list[tuple[Call, Route]] = []
    known_first = {r.path.strip("/").split("/")[0] for r in routes}
    for c in calls:
        cands, by_suffix = match_routes(c, routes)
        if not cands:
            first = c.path.strip("/").split("/")[0]
            if first in known_first:
                findings.append(Finding("ERROR", "no_route", c, None, f"no service serves {c.path}"))
            else:
                findings.append(Finding("INFO", "unresolved", c, None,
                                        f"{c.path} starts with no service prefix: an external API or a client with a base path"))
            continue
        same_method = [r for r in cands if c.method == "ANY" or r.method == c.method]
        if not same_method:
            have = ", ".join(sorted({f"{r.method} {r.path}" for r in cands}))
            findings.append(Finding("ERROR", "wrong_method", c, cands[0].path,
                                    f"called with {c.method}, the route offers: {have}"))
            continue
        # judge against the best candidate (fewest problems) when several services share a path
        best, best_problems = None, None
        for r in same_method:
            problems = _field_problems(c, r)
            if best is None or len(problems) < len(best_problems):
                best, best_problems = r, problems
        best.callers += 1
        matched.append((c, best))
        for level, kind, detail in best_problems:
            findings.append(Finding(level, kind, c, f"{best.method} {best.path}", detail))
    return findings, matched


def _field_problems(c: Call, r: Route) -> list[tuple[str, str, str]]:
    out: list[tuple[str, str, str]] = []
    sent_q = set(c.query)
    for name in sorted(sent_q - set(r.query)):
        out.append(("WARN", "query_ignored", f"query '{name}' is sent but the route does not declare it (silently ignored)"))
    if not c.dynamic_query:
        for name, required in sorted(r.query.items()):
            if required and name not in sent_q:
                out.append(("ERROR", "query_missing", f"required query '{name}' is not sent (route answers 422)"))
    if c.body is not None and r.body is not None and not r.body_open:
        for name in sorted(set(c.body) - set(r.body)):
            out.append(("WARN", "body_ignored", f"body field '{name}' is sent but the route does not declare it (dropped)"))
        if not c.dynamic_body:
            for name, required in sorted(r.body.items()):
                if required and name not in c.body:
                    out.append(("ERROR", "body_missing", f"required body field '{name}' is not sent (route answers 422)"))
    elif c.body is None and not c.dynamic_body and r.body and not r.body_open and any(r.body.values()):
        out.append(("ERROR", "body_missing", "the route needs a JSON body but the call sends none"))
    return out


# ----------------------------------------------------------------------------------------------- output

def load_route_notes(path: Path | None) -> list[dict[str, str]]:
    """Hand-maintained classification of routes nothing calls: [{"pattern": regex on 'METHOD path', "class", "reason"}]."""
    if path is None or not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8")).get("notes", [])


def note_for(r: Route, notes: list[dict[str, str]]) -> tuple[str, str] | None:
    key = f"{r.method} {r.path}"
    for n in notes:
        if re.search(n["pattern"], key):
            return n["class"], n["reason"]
    return None


def unread_routes(routes: list[Route], notes: list[dict[str, str]]) -> list[tuple[Route, str, str]]:
    """Routes with no caller, each with its class (UNCLASSIFIED when no note matches)."""
    out = []
    for r in routes:
        if r.callers == 0 and not r.path.endswith("/health"):
            hit = note_for(r, notes)
            out.append((r, hit[0] if hit else "UNCLASSIFIED", hit[1] if hit else "needs a decision"))
    return out


def registry_markdown(routes: list[Route], matched: list[tuple[Call, Route]], findings: list[Finding],
                      errors: dict[str, str], n_calls: int, notes: list[dict[str, str]] | None = None) -> str:
    notes = notes or []
    by_route: dict[tuple[str, str, str], list[Call]] = {}
    for c, r in matched:
        by_route.setdefault((r.service, r.method, r.path), []).append(c)
    unread = unread_routes(routes, notes)
    by_class: dict[str, int] = {}
    for _, cls, _ in unread:
        by_class[cls] = by_class.get(cls, 0) + 1
    lines = [
        "# Contract registry (GENERATED — do not edit by hand)",
        "",
        "Produced by `python -m vinu_infra.contract_scan`. Producers = the real OpenAPI of every service app; consumers = every",
        "HTTP call found in the source. Re-run it after any route or caller change; `contracts.json` next to this file is the",
        "machine-readable copy.",
        "",
        f"- Services read: {len({r.service for r in routes})} of {len(SERVICES)}"
        + (f" (could not build: {', '.join(f'{k}: {v}' for k, v in errors.items())})" if errors else ""),
        f"- Routes: {len(routes)}; HTTP calls found in source: {n_calls}; calls matched to a route: {len(matched)}",
        f"- Findings: {sum(1 for f in findings if f.level == 'ERROR')} ERROR, {sum(1 for f in findings if f.level == 'WARN')} WARN"
        " (see `03-findings.md` for what each means and its fix status)",
        f"- Routes nothing in the code calls: {len(unread)} ("
        + ", ".join(f"{k}: {v}" for k, v in sorted(by_class.items())) + "); each is classified in the last column.",
        "",
        "Legend: `*` = required. Body `(open)` = untyped object, any key accepted. Callers are `file:line`.",
        "",
    ]
    for svc in sorted({r.service for r in routes}):
        lines += [f"## {svc}", "", "| Route | Query | JSON body | Called by |", "|---|---|---|---|"]
        for r in sorted((x for x in routes if x.service == svc), key=lambda x: (x.path, x.method)):
            q = ", ".join(f"{k}{'*' if v else ''}" for k, v in sorted(r.query.items())) or "-"
            if r.body is None:
                b = "-"
            elif r.body_open:
                b = "(open)"
            else:
                b = ", ".join(f"{k}{'*' if v else ''}" for k, v in r.body.items()) or "-"
            callers = by_route.get((r.service, r.method, r.path), [])
            who = "; ".join(sorted({f"{c.file.split('/')[0].removeprefix('vinu-')}" for c in callers}))
            if not who and not r.path.endswith("/health"):
                hit = note_for(r, notes)
                who = f"**nobody** — {hit[0]}: {hit[1]}" if hit else "**nobody** — UNCLASSIFIED: needs a decision"
            lines.append(f"| `{r.method} {r.path}` | {q} | {b} | {who} |")
        lines.append("")
    return "\n".join(lines) + "\n"


def contracts_json(routes: list[Route], matched: list[tuple[Call, Route]], findings: list[Finding]) -> dict[str, Any]:
    return {
        "routes": [asdict(r) for r in routes],
        "calls": [{**asdict(c), "route": f"{r.method} {r.path}", "service_served": r.service} for c, r in matched],
        "findings": [{"level": f.level, "kind": f.kind, "route": f.route, "detail": f.detail, **asdict(f.call)}
                     for f in findings],
    }


def load_allowlist(path: Path | None) -> set[tuple[str, str, str]]:
    if path is None or not path.exists():
        return set()
    data = json.loads(path.read_text(encoding="utf-8"))
    return {(e["file"], e["kind"], e.get("detail_contains", "")) for e in data.get("allow", [])}


def apply_client_prefixes(calls: list[Call], path: Path | None) -> int:
    """Hand-maintained facts for clients whose base URL (and so the service prefix) is set elsewhere, e.g.
    `StrategyClient(f"{url}/strategy")` then `.get("/weights")`. Entries: {"file", "prefix", optional "line"}."""
    if path is None or not path.exists():
        return 0
    entries = json.loads(path.read_text(encoding="utf-8")).get("clients", [])
    n = 0
    for c in calls:
        for e in entries:
            if c.file == e["file"] and e.get("line") in (None, c.line) and not c.path.startswith(e["prefix"] + "/"):
                c.path = norm_path(e["prefix"] + c.path)
                n += 1
                break
    return n


def is_allowed(f: Finding, allow: set[tuple[str, str, str]]) -> bool:
    return any(f.call.file == a[0] and f.kind == a[1] and a[2] in f.detail for a in allow)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--root", type=Path, required=True, help="the vinu-components folder")
    ap.add_argument("--out", type=Path, required=True, help="folder for contracts.json and 02-contract-registry.md")
    ap.add_argument("--allowlist", type=Path, default=None)
    ap.add_argument("--route-notes", type=Path, default=None,
                    help="json file classifying routes nothing calls (human-view, file-read, covered, candidate-gap)")
    ap.add_argument("--client-prefixes", type=Path, default=None,
                    help="json file naming the service prefix of clients whose base URL is set elsewhere")
    ap.add_argument("--python", action="append", default=[], metavar="SERVICE=PYTHON",
                    help="interpreter to build one service's app with (e.g. agent=C:/venv/python.exe)")
    ap.add_argument("--openapi-cache", type=Path, default=None, help="reuse/write the dumped OpenAPI documents here")
    args = ap.parse_args(argv)
    python_for = dict(x.split("=", 1) for x in args.python)

    if args.openapi_cache and args.openapi_cache.exists():
        cached = json.loads(args.openapi_cache.read_text(encoding="utf-8"))
        docs, errors = cached["docs"], cached["errors"]
    else:
        docs, errors = dump_openapi(args.root, SERVICES, python_for)
        if args.openapi_cache:
            args.openapi_cache.write_text(json.dumps({"docs": docs, "errors": errors}), encoding="utf-8")
    routes = [r for svc, doc in docs.items() for r in routes_from_openapi(svc, doc)]
    known_first = {r.path.strip("/").split("/")[0] for r in routes}
    calls = scan_callers(args.root, known_first)
    apply_client_prefixes(calls, args.client_prefixes)
    findings, matched = compare(calls, routes)
    allow = load_allowlist(args.allowlist)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "contracts.json").write_text(json.dumps(contracts_json(routes, matched, findings), indent=1), encoding="utf-8")
    (args.out / "02-contract-registry.md").write_text(registry_markdown(routes, matched, findings, errors, len(calls),
                                                                         load_route_notes(args.route_notes)),
                                                     encoding="utf-8")
    unclassified = [r for r, cls, _ in unread_routes(routes, load_route_notes(args.route_notes)) if cls == "UNCLASSIFIED"]
    real_errors = [f for f in findings if f.level == "ERROR" and not is_allowed(f, allow)]
    print(f"services={len(docs)} routes={len(routes)} calls={len(calls)} matched={len(matched)} "
          f"errors={sum(1 for f in findings if f.level == 'ERROR')} warns={sum(1 for f in findings if f.level == 'WARN')} "
          f"info={sum(1 for f in findings if f.level == 'INFO')} "
          f"(unallowed errors: {len(real_errors)}; unread routes with no classification: {len(unclassified)})")
    for f in findings:
        if f.level == "INFO":
            continue
        print(f"{f.level:5s} {f.kind:14s} {f.call.file}:{f.call.line}  {f.call.method} {f.call.path}  -> {f.detail}")
    for k, v in errors.items():
        print(f"could not build {k}: {v}")
    return 1 if real_errors else 0


if __name__ == "__main__":
    sys.exit(main())
