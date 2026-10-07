# Trial NN — <short scenario name>

**Checkpoint:** <checkpoint name> (<real file/team this tests>)
**Status:** PENDING — awaiting a real LLM endpoint (see the container blocker
noted in this folder's parent `README.md`)

## Expected result

<What a production-grade LLM response must do here. Be specific and
checkable — not "should be good," but a concrete pass/fail bar: which
field(s) must have which value/range, what it must NOT say, what it must
refuse or flag. This section is written BEFORE the trial is ever run —
it's the known-correct answer this trial is checked against, same
discipline as `llm-scenarios-test/`'s `expected.md` files.>

## Why this trial exists (the failure mode being probed)

<One or two sentences: what kind of hallucination, rule violation, or
inconsistency this specific input is designed to surface, and why that
failure mode would matter in production (what real decision it would
distort).>

## Situation / scenario

<The realistic backstory this input represents, and why it's realistic
(not synthetic-for-its-own-sake) — grounded in what a real caller would
actually pass at this call site.>

## Prompt sent

### System prompt
```
<exact system prompt string, copied verbatim from the real source file —
never paraphrased>
```

### User prompt / task
```
<exact user prompt text, built the same way the real code builds it, or
the exact task string a manager agent would be given>
```

## Parameters

| Param | Value |
|---|---|
| Model | |
| Endpoint | |
| Temperature | |
| max_tokens | |
| timeout_sec | |
| Run timestamp (UTC) | |
| Attempt # (of N repeats of this same trial) | |
| Retry count | |

## Response received

```
<raw response, verbatim, unedited — including if it's malformed>
```

## Verdict

- Parsed as valid JSON matching the expected schema? Y/N
- Matches "Expected result" above? Y/N
- Verdict stable across repeated runs of this same trial (attempt N vs N-1)? Y/N
- Latency (sec):
- Hallucination / rule violation observed (quote the exact offending text verbatim):
- Notes:
