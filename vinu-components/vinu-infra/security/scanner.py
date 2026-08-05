from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class InjectionFinding:
    rule_id: str
    severity: str
    excerpt: str
    description: str


_INJECTION_RULES: list[dict[str, Any]] = [
    {
        "id": "instruction_override",
        "pattern": re.compile(
            r"(ignore|disregard|override|forget|skip)\s+(all\s+)?(previous|above|prior)\s+(instructions|prompt|commands|directions)",
            re.IGNORECASE,
        ),
        "severity": "high",
        "description": "Attempt to override system instructions",
    },
    {
        "id": "system_prompt_exfiltration",
        "pattern": re.compile(
            r"(output|print|show|reveal|display|leak|dump)\s+(your\s+)?(system\s+)?prompt|system\s+message",
            re.IGNORECASE,
        ),
        "severity": "high",
        "description": "Attempt to exfiltrate system prompt",
    },
    {
        "id": "role_or_channel_claim",
        "pattern": re.compile(
            r"(you\s+are\s+(now\s+)?|act\s+as\s+|pretend\s+(to\s+)?be\s+)"
            r"(admin|sudo|root|superuser|system|assistant|developer)",
            re.IGNORECASE,
        ),
        "severity": "medium",
        "description": "Attempt to claim elevated role",
    },
    {
        "id": "secret_exfiltration",
        "pattern": re.compile(
            r"(api[_-]?key|secret|password|token|credential|private[_-]?key)",
            re.IGNORECASE,
        ),
        "severity": "medium",
        "description": "Possible secret exfiltration attempt",
    },
    {
        "id": "tool_abuse",
        "pattern": re.compile(
            r"(run|execute|exec)\s*(shell|command|system|bash|cmd|subprocess)",
            re.IGNORECASE,
        ),
        "severity": "high",
        "description": "Attempt to execute system commands",
    },
]


def scan_prompt_injection(text: str) -> list[InjectionFinding]:
    findings: list[InjectionFinding] = []
    for rule in _INJECTION_RULES:
        match = rule["pattern"].search(text)
        if match:
            start = max(0, match.start() - 20)
            end = min(len(text), match.end() + 20)
            excerpt = text[start:end].replace("\n", " ")
            findings.append(
                InjectionFinding(
                    rule_id=rule["id"],
                    severity=rule["severity"],
                    excerpt=excerpt,
                    description=rule["description"],
                )
            )
    return findings


def with_security_warnings(
    payload: dict[str, Any],
    fields: list[str],
) -> dict[str, Any]:
    result = dict(payload)
    warnings: list[dict[str, Any]] = []
    for field in fields:
        value = payload.get(field)
        if isinstance(value, str):
            findings = scan_prompt_injection(value)
            for f in findings:
                warnings.append({
                    "field": field,
                    "rule_id": f.rule_id,
                    "severity": f.severity,
                    "description": f.description,
                })
    if warnings:
        result["security_warnings"] = warnings
    return result
