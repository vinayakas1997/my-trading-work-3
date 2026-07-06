# Appendix E — Yet to Build (vinu-features)

| Field | Value |
|-------|-------|
| **Package** | vinu-features |
| **Module** | — |
| **Status** | REVIEW |
| **Verified** | 2026-07-06 |
| **Prerequisites** | — |

**Quick dashboard:** open this chapter when you need **only what is not built yet**. For done + todo together, see [Appendix D — Roadmap & Gaps](apx-d-roadmap-gaps.md).

**Sister volume:** [vinu-news — Yet to build](../../../../vinu-news/docs/book/part-5-appendices/apx-e-yet-to-build.md)

---

## Open enhancement tasks (vinu-features)

| ID | Priority | Title | Status | Spec | Document when done |
|----|----------|-------|--------|------|-------------------|
| TASK-F02 | MEDIUM | Cross-symbol feature stacking | **TODO** | Combine multiple symbols in one parquet with symbol dimension | [ch07](../part-2-engine/ch07-manifest-and-parquet.md) |
| TASK-F03 | MEDIUM | Portfolio-level features | **TODO** | Equal-weight / cap-weight composite features | [ch05](../part-2-engine/ch05-request-lifecycle.md) |
| TASK-F04 | LOW | Automated model retraining | **TODO** | Cron-triggered retrain on new data | [ch05](../part-1-presets/ch05-ml-models.md) |
| TASK-F05 | LOW | WebSocket status updates | **TODO** | Push run completion events | [ch10](../part-4-operations/ch10-http-api.md) |
| TASK-F06 | LOW | Feature drift monitoring | **TODO** | Compare feature distributions across runs | [ch04](../part-1-presets/ch04-indicator-catalog.md) |

---

## Feature gaps

| Gap | Notes | Target |
|-----|-------|--------|
| Cross-symbol feature stacking | Current: per-symbol parquet rows | TASK-F02 |
| Portfolio-level features | No composite features across symbols | TASK-F03 |
| Automated ML retraining | Models train once per submit | TASK-F04 |
| WebSocket push | No real-time status updates | TASK-F05 |
| Feature distribution drift | No monitoring of feature stability | TASK-F06 |

## Related chapters

- [Appendix D — Roadmap & Gaps](apx-d-roadmap-gaps.md)
- [Appendix C — Out of Scope](apx-c-out-of-scope.md)
