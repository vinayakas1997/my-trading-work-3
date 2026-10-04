"""The contract scanner: reads producers from OpenAPI and consumers from the AST, and reports path / method / field problems."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Query
from pydantic import BaseModel

from vinu_infra import contract_scan as cs
from vinu_infra.contract_scan import Call, Route


# ------------------------------------------------------------------ producers

class Body(BaseModel):
    name: str
    size: int = 1


def test_routes_from_openapi_reads_query_and_body_fields_and_required_flags():
    app = FastAPI()

    @app.get("/svc/items/{item_id}")
    def get_item(item_id: str, kind: str = "a", limit: int = Query(...)):
        return {}

    @app.post("/svc/items")
    def make(body: Body):
        return {}

    @app.post("/svc/free")
    def free(body: dict):
        return {}

    routes = {(r.method, r.path): r for r in cs.routes_from_openapi("svc", app.openapi())}
    g = routes[("GET", "/svc/items/{item_id}")]
    assert g.query == {"kind": False, "limit": True} and g.body is None
    p = routes[("POST", "/svc/items")]
    assert p.body == {"name": True, "size": False} and not p.body_open
    assert routes[("POST", "/svc/free")].body_open


# ------------------------------------------------------------------ consumers

def _scan(tmp_path: Path, source: str, known=("svc", "agent")) -> list[Call]:
    d = tmp_path / "vinu-demo"
    d.mkdir()
    (d / "client.py").write_text(source, encoding="utf-8")
    return cs.scan_callers(tmp_path, set(known))


def test_fstring_url_params_and_json_keys_are_read(tmp_path):
    calls = _scan(tmp_path, '''
async def go(http, base, sym):
    r = await http.get(f"{base}/svc/items/{sym}", params={"kind": "a", "limit": 5})
    payload = {"name": "x"}
    payload["size"] = 2
    await http.post(f"{base}/svc/items", json=payload)
''')
    by = {(c.method, c.path): c for c in calls}
    g = by[("GET", "/svc/items/{}")]
    assert sorted(g.query) == ["kind", "limit"] and not g.dynamic_query
    p = by[("POST", "/svc/items")]
    assert sorted(p.body) == ["name", "size"] and not p.dynamic_body


def test_url_in_a_local_variable_query_string_and_base_variable_are_resolved(tmp_path):
    calls = _scan(tmp_path, '''
def go(client, base):
    url = f"{base}/svc"
    client.get(f"{url}/angles?active=true&x=1")
    other = f"{base}/svc/things"
    client.get(other, params={"a": 1})
''')
    by = {c.path: c for c in calls}
    assert sorted(by["/svc/angles"].query) == ["active", "x"]
    assert by["/svc/things"].query == ["a"]


def test_dict_get_and_route_decorators_are_not_calls(tmp_path):
    calls = _scan(tmp_path, '''
def go(d, router):
    return d.get("svc/key"), d.get("name")

def build(router):
    @router.get("/svc/items")
    def items():
        return {}
    @router.post("/svc/make")
    async def make():
        return {}
''')
    assert calls == []


def test_kwargs_unpacking_and_unreadable_bodies_are_marked_dynamic(tmp_path):
    calls = _scan(tmp_path, '''
def go(http, base, extra, body):
    http.post(f"{base}/svc/a", json={"x": 1, **extra})
    http.post(f"{base}/svc/b", json=body)
    http.get(f"{base}/svc/c", params=extra)
''')
    by = {c.path: c for c in calls}
    assert by["/svc/a"].dynamic_body and by["/svc/a"].body == ["x"]
    assert by["/svc/b"].dynamic_body
    assert by["/svc/c"].dynamic_query


def test_requests_request_form_is_read(tmp_path):
    calls = _scan(tmp_path, '''
def go(session, base):
    session.request("POST", f"{base}/svc/x", json={"a": 1})
''')
    assert [(c.method, c.path, c.body) for c in calls] == [("POST", "/svc/x", ["a"])]


# ------------------------------------------------------------------ compare

def _call(method, path, query=(), body=None, dq=False, db=False):
    return Call(service="demo", file="vinu-demo/client.py", line=1, method=method, path=path, raw_path=path,
                query=list(query), body=None if body is None else list(body), dynamic_query=dq, dynamic_body=db)


ROUTES = [
    Route("svc", "GET", "/svc/items/{item_id}", query={"kind": False, "limit": True}),
    Route("svc", "POST", "/svc/items", body={"name": True, "size": False}),
    Route("svc", "POST", "/svc/free", body={}, body_open=True),
    Route("svc", "GET", "/svc/health"),
    Route("svc", "GET", "/analysis/angle/{angle_name}/{ticker}"),
]


def _kinds(call):
    findings, matched = cs.compare([call], ROUTES)
    return sorted(f.kind for f in findings), len(matched)


def test_a_clean_call_has_no_findings():
    assert _kinds(_call("GET", "/svc/items/{}", ["kind", "limit"])) == ([], 1)
    assert _kinds(_call("POST", "/svc/items", body=["name"])) == ([], 1)


def test_missing_required_fields_are_errors():
    assert _kinds(_call("GET", "/svc/items/{}", ["kind"]))[0] == ["query_missing"]
    assert _kinds(_call("POST", "/svc/items", body=["size"]))[0] == ["body_missing"]
    assert _kinds(_call("POST", "/svc/items"))[0] == ["body_missing"]          # needs a body, sends none


def test_extra_fields_are_warnings_because_the_route_drops_them():
    findings, _ = cs.compare([_call("GET", "/svc/items/{}", ["limit", "nope"])], ROUTES)
    assert [(f.level, f.kind) for f in findings] == [("WARN", "query_ignored")]
    findings, _ = cs.compare([_call("POST", "/svc/items", body=["name", "bogus"])], ROUTES)
    assert [(f.level, f.kind) for f in findings] == [("WARN", "body_ignored")]


def test_dynamic_calls_never_report_missing_fields_and_open_bodies_accept_any_key():
    assert _kinds(_call("GET", "/svc/items/{}", [], dq=True))[0] == []
    assert _kinds(_call("POST", "/svc/items", body=[], db=True))[0] == []
    assert _kinds(_call("POST", "/svc/free", body=["anything"]))[0] == []


def test_unknown_path_and_wrong_method():
    findings, _ = cs.compare([_call("GET", "/svc/nothing")], ROUTES)
    assert [(f.level, f.kind) for f in findings] == [("ERROR", "no_route")]
    findings, _ = cs.compare([_call("DELETE", "/svc/items")], ROUTES)
    assert [(f.level, f.kind) for f in findings] == [("ERROR", "wrong_method")]


def test_a_route_template_segment_accepts_a_literal_and_a_bare_one_segment_path_is_unresolved_info():
    assert _kinds(_call("GET", "/analysis/angle/shock_personality/{}"))[1] == 1
    findings, matched = cs.compare([_call("GET", "/{}")], ROUTES)
    assert matched == [] and [(f.level, f.kind) for f in findings] == [("INFO", "unresolved")]
    findings, _ = cs.compare([_call("POST", "/chat/completions")], ROUTES)
    assert [(f.level, f.kind) for f in findings] == [("INFO", "unresolved")]      # external API


def test_a_base_prefixed_client_matches_by_path_suffix():
    routes = ROUTES + [Route("strategy", "GET", "/strategy/weights", query={"strategy": True})]
    findings, matched = cs.compare([_call("GET", "/strategy/weights", ["strategy"])], routes)
    assert findings == [] and len(matched) == 1


# ------------------------------------------------------------------ output / allowlist

def test_registry_lists_routes_fields_and_marks_unused_routes():
    findings, matched = cs.compare([_call("GET", "/svc/items/{}", ["limit"])], ROUTES)
    md = cs.registry_markdown(ROUTES, matched, findings, {}, 1)
    assert "`GET /svc/items/{item_id}`" in md and "limit*" in md and "**nobody**" in md


def test_allowlist_suppresses_only_the_listed_finding(tmp_path):
    allow_file = tmp_path / "allow.json"
    allow_file.write_text('{"allow": [{"file": "vinu-demo/client.py", "kind": "no_route", "detail_contains": "/svc/nothing"}]}')
    allow = cs.load_allowlist(allow_file)
    f1, _ = cs.compare([_call("GET", "/svc/nothing")], ROUTES)
    f2, _ = cs.compare([_call("GET", "/svc/other")], ROUTES)
    assert cs.is_allowed(f1[0], allow) and not cs.is_allowed(f2[0], allow)
