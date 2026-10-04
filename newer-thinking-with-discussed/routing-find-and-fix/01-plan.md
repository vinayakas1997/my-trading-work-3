# Plan: contracts between services

## The idea

How real systems keep services from drifting apart: every producer states exactly what it accepts and returns (a schema generated from its own code), and every consumer is checked against that schema automatically. A mismatch is then found by a tool, not by a 404 in production. This is the same idea as consumer-driven contract testing (Pact, Schemathesis), done statically for Phase 1.

## Three layers

| Layer | What it checks | Needs data? | Status |
|---|---|---|---|
| **A. Static contract scan** | Every HTTP call in the source reaches a real route (path and method), sends the required fields, and does not send fields the route drops; routes nobody calls are classified. | No | **Built** (`vinu-infra/contract_scan.py`, 19 tests) |
| **B. Contract in the edge manifest** | Per data connection (`pipeline_edges.yaml`): a pydantic model (`vinu-infra/edge_contracts.py`) of the fields it carries, with an example payload, or a written reason why the connection has no JSON payload. Both sides of the connection are checked against it. | No | **Built** (15 of 38 connections have a model, the other 23 a written reason; 24 tests) |
| **C. Runtime shape check** | The edge recorder compares the shape of a real payload with the contract and logs a mismatch (missing field, wrong type, empty where it should not be). | Yes (Phase 2) | Not built |

Layer A is the foundation: it generates `contracts.json`, the machine-readable contract that B and C reuse.

## How layer B works

One pydantic model per connection that carries a JSON payload, registered under the edge id(s) that carry it (`@contract_for("edge.id")` in `vinu-infra/edge_contracts.py`). In `pipeline_edges.yaml` each wired edge names it (`contract: PortfolioState`) or gives the reason it has none (`contract_none: "..."`); a wired edge with neither fails the test. Pydantic was chosen because FastAPI already uses it: nothing new to run.

Rules for a model: a field is **required** when the producer always emits it and a consumer depends on it, everything else has a default; extra keys are allowed (a producer adding a field must not break a consumer); an answer the producer legitimately sends in a different shape (`{"status": "none"}`, an empty book) is modelled so it still validates.

What is checked, with no data:

1. the model has an example payload and it validates;
2. every field appears as a quoted literal in the producer's source (`contract_producer_files` adds files where the route's body is built elsewhere);
3. every required field appears in the consumer's source (a nested field counts only when its parents are required, so a consumer that never reads an optional section is not held to it).

A key renamed on either side fails a test instead of arriving as "missing" in production. The same model is what layer C will call at run time: `check_payload(edge_id, payload)` returns one short line per problem and never raises.

Producer-side tests: each service validates its **real** answer against the model (portfolio state, daily allocation and risk status through the real service; maturity, unconfirmed moves, notable beliefs, synthesis, screener, strategy config, models service and novelty through their real routes or functions). So a model cannot drift from what the producer really sends.

## How layer A works

1. **Producers:** build each service's real FastAPI app and read its OpenAPI document. Per route: method, path, query parameters (and which are required), JSON body fields (and which are required).
2. **Consumers:** parse every service's source (`ast`) and find each `.get/.post/.put/.patch/.delete/.request` call whose URL resolves to a path; read the query keys (`params=` or `?a=` in the URL) and JSON body keys (`json=`). URLs held in a local variable, built from a base variable, or fields added afterwards (`payload["x"] = ...`) are followed.
3. **Compare:** path or method with no route (ERROR), required field not sent (ERROR, the route would answer 422), field sent that the route does not declare (WARN, silently dropped).
4. **Keep it honest:** calls that cannot be fully read are marked `dynamic` and never produce a "missing field" error; external APIs are INFO, not errors; clients whose base URL carries the service prefix are listed by hand in `client_prefixes.json` (each verified against its constructor); a finding that is correct to leave goes in `contract_allowlist.json` with a reason.

## Known limits (layers A and B)

- Layer A checks that fields exist, not their types or values, and not the response a caller reads (layer B adds the response shape for 15 connections).
- Layer B finds field names by quoted-literal search, so a dynamically built key is invisible to it, and a name used for something else in the same file can satisfy it by accident. It checks names and shapes, not that a value is right.
- Helper calls (`_fetch_json(f"{base}/..")`, `_post(client, "/..")`) are seen for path and method, but their fields are not compared; a body built from `**kwargs` is not checked field by field.
- It cannot see anything that only fails with real data (Phase 2).

## Maintenance rules

- Re-run the scan after changing any route or any caller; commit the regenerated `02-contract-registry.md` and `contracts.json`.
- Never add to the allowlist without a written reason.
- A new service must be added to `SERVICES` in `contract_scan.py`.
- Findings go in `03-findings.md` with a status; the status of the work goes in `04-implementation-status.md`.
