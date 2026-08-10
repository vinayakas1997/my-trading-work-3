import re
from typing import Any, Dict, Tuple


def parse_frontmatter(text: str) -> Tuple[Dict[str, Any], str]:
    match = re.match(r"^---\s*\n(.*?)\n?---\s*\n?(.*)", text, re.DOTALL)
    if not match:
        return {}, text

    raw_metadata = match.group(1).strip()
    body = match.group(2).strip()

    metadata = {}
    for line in raw_metadata.split("\n"):
        line = line.strip()
        if not line or ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()

        if value.startswith("[") and value.endswith("]"):
            inner = value[1:-1].strip()
            # Real fix: "[]".split(",") is [""], a one-item list holding an
            # empty string, not an empty list -- every empty-list field
            # (e.g. `tools: []`, `depends_on: []`) parsed to [""] instead
            # of []. TEAM.md/AGENT.md rely on `tools: []` genuinely meaning
            # "no tools", so this mattered in practice, not just in theory.
            value = [] if not inner else [
                v.strip().strip('"').strip("'") for v in inner.split(",")
            ]
        elif value.lower() in ("true", "false"):
            value = value.lower() == "true"
        elif (value.startswith('"') and value.endswith('"')) or \
             (value.startswith("'") and value.endswith("'")):
            value = value[1:-1]

        metadata[key] = value

    return metadata, body
