# Routing: find and fix

Checks that every connection between services is wired correctly (Phase 1, code only; see `../working-rules.md`): the call reaches a real route, with the fields the route accepts. The result is kept here as a living contract.

| File | What it is |
|---|---|
| `01-plan.md` | The approach and what each layer covers. Read this first. |
| `02-contract-registry.md` | **Generated.** Every route with its query and body fields, and who calls it. |
| `contracts.json` | **Generated.** The same, machine-readable (routes, matched calls, findings). |
| `03-findings.md` | What was found, what it means, fix status. |
| `04-implementation-status.md` | What is built, files touched, tests, what is still open. |
| `contract_allowlist.json` | Findings that are correct to leave, each with a reason. |
| `client_prefixes.json` | Clients whose base URL carries the service prefix (hand-verified). |

Re-run after any route or caller change (from `vinu-components/`):

```
python -m vinu_infra.contract_scan --root . \
  --out ../newer-thinking-with-discussed/routing-find-and-fix \
  --allowlist ../newer-thinking-with-discussed/routing-find-and-fix/contract_allowlist.json \
  --client-prefixes ../newer-thinking-with-discussed/routing-find-and-fix/client_prefixes.json
```

It builds every service's real app, so it needs all service dependencies (run it where the services run, or pass `--python agent=<interpreter>` for one service). It exits 1 if there is any ERROR not in the allowlist.
