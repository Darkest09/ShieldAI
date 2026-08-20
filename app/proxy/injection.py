"""Heuristic prompt-injection / jailbreak scans (defense-in-depth, not exhaustive)."""

import re

from app.core.models import InjectionFinding


def _normalize(prompt: str) -> str:
    return re.sub(r"\s+", " ", prompt.casefold())


_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    (
        "ignore_previous_instructions",
        re.compile(r"ignore (all )?(previous|prior|above) instructions", re.I),
    ),
    (
        "ignore_all_instructions",
        re.compile(r"\bignore\s+all\s+instructions\b", re.I),
    ),
    (
        "dan_jailbreak",
        re.compile(r"\b(do anything now|jailbroken|developer mode)\b", re.I),
    ),
    (
        "system_prompt_override",
        re.compile(r"(\*{3,})\s*(new )?system\b", re.I),
    ),
    (
        "json_tool_injection",
        re.compile(r"\"role\"\s*:\s*\"system\"", re.I),
    ),
    (
        "system_prompt_exfiltration",
        re.compile(
            r"\b(reveal|show|print|repeat|leak|disclose)\b.{0,30}"
            r"\b(system prompt|initial instructions|your instructions|prompt above)\b",
            re.I,
        ),
    ),
    (
        "role_play_override",
        re.compile(r"\b(you are now|pretend to be|act as)\b.{0,40}\b(no restrictions|unfiltered|without rules)\b", re.I),
    ),
    (
        "instruction_negation",
        re.compile(r"\b(disregard|forget|override)\b.{0,20}\b(rules|guidelines|policy|safety)\b", re.I),
    ),
    (
        "data_exfiltration_request",
        re.compile(r"\b(send|exfiltrate|post|upload|email)\b.{0,30}\b(to|http|https)\b.{0,40}\b(all|data|records|secrets|keys)\b", re.I),
    ),
    (
        "encoding_evasion",
        re.compile(r"\b(base64|rot13|hex[\s-]?encode|decode the following)\b", re.I),
    ),
]


def scan_prompt_messages(messages: list[dict]) -> InjectionFinding:
    parts: list[str] = []
    for m in messages:
        role = m.get("role")
        content = m.get("content")
        if role == "tool":
            parts.append("__tool_payload__")  # do not blindly embed tool payloads
            continue
        if isinstance(content, str):
            parts.append(content)
        elif isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    parts.append(str(block.get("text", "")))
    blob = "\n".join(parts)
    return scan_text(blob)


def scan_text(blob: str) -> InjectionFinding:
    n = _normalize(blob)
    triggers: list[str] = []
    for name, pat in _PATTERNS:
        if pat.search(blob) or pat.search(n):
            triggers.append(name)
    return InjectionFinding(matched_rules=triggers)
