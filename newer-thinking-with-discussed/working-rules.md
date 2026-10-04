# Working rules for this project

These are the rules the project owner set for how the system is built and how "built / audited" is judged.
They apply to every session. If something here conflicts with a habit or a shortcut, these win.

## 1. The aim

The aim of the project is written in [`vision-trding-system.md`](vision-trding-system.md). Everything is measured against that file.

## 2. Wiring first, data later

While the system is being built, the work is **features wired up properly, before any data flows in**. A feature counts as built when the connection exists and is correct, not when it has produced a result on real data.

## 3. The system must be able to tell us what happened when data does flow

The system is built so that, once data starts flowing, we can see **what data arrived, which data, and whether each connection worked**: through logs, a separate table, or whatever fits. In practice this is the pipeline-edge manifest and the runtime recorder (`vinu-infra/pipeline_edges.yaml`, `GET /research/pipeline-edges?only_problems=true`), the order ledger, and the error runs that are recorded instead of silent empty results. A connection that cannot tell us whether it worked is not finished.

## 4. It must work even as a child

The system is new. It has to work **even when it is a child**: with little data and little experience. It needs a brain that understands its own state, how much it actually knows, and believes the facts in proportion to the evidence it really has (not more). The maturity tier, evidence confidence, the uncertainty assessment, the novelty check and "I don't know" abstention exist for this; none of them may assume the system is already experienced.

## 5. Three phases. "Did you build it / did you audit it" always means Phase 1

| Phase | What it is |
|---|---|
| **Phase 1** | **Only the codebase.** The features, the wiring, and the intuition: "this logic works, it has been wired like this." This is what the owner means by built and audited. |
| **Phase 2** | The intuition becoming real as data starts to flow (paper data). |
| **Phase 3** | Real data starts (real trading). |

So when asked "did you build it?" or "did you audit it?", the answer is about Phase 1 only: is the code written, is it wired correctly, does the logic hold. Do not answer with, or hold back an answer for, Phase 2 or Phase 3 results (slippage against real fills, enforcement, calibration from paper data). Say plainly which of those wait for data, but do not count them as unbuilt Phase 1 work.

## How to apply

- When reporting progress, say "Phase 1" first: what is wired and checked. List Phase 2 and 3 items separately as "waits for data".
- Before calling something wired, check that the connection records whether it worked (rule 3).
- Do not design anything that only works once the system is experienced (rule 4).
- Do not ask the owner to re-decide things already decided here.
