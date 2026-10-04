# Plan: contracts between services

## The idea

How real systems keep services from drifting apart: every producer states exactly what it accepts and returns (a schema generated from its own code), and every consumer is checked against that schema automatically. A mismatch is then found by a tool, not by a 404 in production. This is the same idea as consumer-driven contract testing (Pact, Schemathesis), done statically for Phase 1.

## Three layers

| Layer | What it checks | Needs data? | Status |
|---|---|---|---|
| **A. Static contract scan** | Every HTTP call in the source reaches a real route (path and method), sends the required fields, and does not send fields the route drops. | No | **Built** (`vinu-infra/contract_scan.py`, 15 tests) |
| **B. Contract in the edge manifest** | Per data connection (`pipeline_edges.yaml`): the fields it must carry and an example payload, so the contract is written down next to the "who sends, who reads" entry. | No | Not built |
| **C. Runtime shape check** | The edge recorder compares the shape of a real payload with the contract and logs a mismatch (missing field, wrong type, empty where it should not be). | Yes (Phase 2) | Not built |

Layer A is the foundation: it generates `contracts.json`, the machine-readable contract that B and C reuse.

## How layer A works

1. **Producers:** build each service's real FastAPI app and read its OpenAPI document. Per route: method, path, query parameters (and which are required), JSON body fields (and which are required).
2. **Consumers:** parse every service's source (`ast`) and find each `.get/.post/.put/.patch/.delete/.request` call whose URL resolves to a path; read the query keys (`params=` or `?a=` in the URL) and JSON body keys (`json=`). URLs held in a local variable, built from a base variable, or fields added afterwards (`payload["x"] = ...`) are followed.
3. **Compare:** path or method with no route (ERROR), required field not sent (ERROR, the route would answer 422), field sent that the route does not declare (WARN, silently dropped).
4. **Keep it honest:** calls that cannot be fully read are marked `dynamic` and never produce a "missing field" error; external APIs are INFO, not errors; clients whose base URL carries the service prefix are listed by hand in `client_prefixes.json` (each verified against its constructor); a finding that is correct to leave goes in `contract_allowlist.json` with a reason.

## Known limits of layer A

- It checks that fields exist, not their types or values, and not the response a caller reads.
- A URL passed through a helper function, or a body built from `**kwargs`, is not checked field by field.
- It cannot see anything that only fails with real data (Phase 2).

## Maintenance rules

- Re-run the scan after changing any route or any caller; commit the regenerated `02-contract-registry.md` and `contracts.json`.
- Never add to the allowlist without a written reason.
- A new service must be added to `SERVICES` in `contract_scan.py`.
- Findings go in `03-findings.md` with a status; the status of the work goes in `04-implementation-status.md`.
