import json
import time
import urllib.request

ENDPOINT = "http://localhost:8092/v1/chat/completions"
MODEL = "qwen3.5-9b-q4_k_m-local"

# Chapter 3 -- cross-analysis. Reads Chapter 2's output ONLY (the 7 real
# cluster synthesis sentences just produced by the split-cluster test),
# per 02-time-format-richness.md's question: is the second timeframe
# earning its cost -- real corroboration vs. redundant/unchanging.
SYSTEM_PROMPT = (
    "You are doing Chapter 3 of a ticker comprehension book: cross-analysis. "
    "You are given 7 cluster synthesis sentences (Chapter 2's real output, one "
    "per cluster A-G) for one ticker. You do NOT have the raw per-angle data -- "
    "only these 7 sentences. Your job: "
    "(1) Find real corroboration -- two or more clusters independently pointing "
    "to the same underlying pattern (e.g. a forecast cluster and a regime cluster "
    "both showing the same shift across timeframes). Only call this out if the "
    "sentences actually support it -- never invent an agreement that isn't there. "
    "(2) Find clusters that show NO real cross-timeframe change -- these are "
    "candidates for 'not worth checking a second timeframe for.' "
    "(3) Say what this means for a downstream trading decision: is there a "
    "genuine, corroborated signal here, or does the picture just look busy "
    "without adding real information? "
    "Return prose covering all 3 points, citing the actual cluster letters and "
    "quoting the relevant part of their sentences. Then end with a fenced "
    '```json block: {"corroborations": [{"clusters": ["B","D"], "why": "..."}], '
    '"redundant_clusters": ["G", ...], "verdict": "one sentence, forecast-relevant"}.'
)

for name in ["clean", "uneven"]:
    with open(f"chapter2_digest_{name}.json", encoding="utf-8") as f:
        digest = json.load(f)

    lines = [f"Cluster {c}: {s}" for c, s in digest.items()]
    user_prompt = "Ticker: AAPL\n\n=== Chapter 2 output (7 cluster syntheses) ===\n" + "\n\n".join(lines)

    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.2,
        "max_tokens": 3000,
        "chat_template_kwargs": {"enable_thinking": False},
    }
    req = urllib.request.Request(
        ENDPOINT,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    start = time.time()
    with urllib.request.urlopen(req, timeout=200) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    elapsed = time.time() - start
    content = body["choices"][0]["message"].get("content", "")
    safe = content.encode("ascii", errors="replace").decode("ascii")
    print(f"=== chapter3 / {name} done in {elapsed:.1f}s ===")
    print(safe)
    print()
    with open(f"chapter3_result_{name}.json", "w", encoding="utf-8") as f:
        json.dump({"body": body, "elapsed_sec": elapsed}, f, indent=2)
