from __future__ import annotations

import re
from dataclasses import dataclass

from app.models import AttackType, Channel, RuleHit

BENIGN_INTENT = re.compile(
    r"\b("
    r"explain|what is|what are|how (do|does|can)|define|example of|"
    r"write (an? )?(essay|article|blog)|summarize|translate|"
    r"detect(ing)? prompt injection|security (research|education)"
    r")\b",
    re.I,
)


@dataclass(frozen=True)
class Pattern:
    attack_type: AttackType
    regex: re.Pattern[str]
    weight: int


PATTERNS: list[Pattern] = [
    Pattern(
        "instruction_override",
        re.compile(
            r"(ignore|disregard|forget|override|discard)\s+"
            r"(all\s+|the\s+)?"
            r"((previous|prior|above|your|the|system|safety|hidden)\s+)*"
            r"(instructions?|rules?|prompts?|guidelines?|directions?)",
            re.I,
        ),
        35,
    ),
    Pattern(
        "instruction_override",
        re.compile(
            r"(new|updated)\s+(system\s+)?(instructions?|prompt)\s*(:|are|follow)",
            re.I,
        ),
        30,
    ),
    Pattern(
        "instruction_override",
        re.compile(r"\bdo not (follow|obey|use) (your )?(system |safety )?(rules?|instructions?|guidelines?)\b", re.I),
        32,
    ),
    Pattern(
        "role_change",
        re.compile(
            r"\byou (are|will be) (now |no longer .{0,20})?(dan|an? unrestricted|an? administrator|"
            r"jailbroken|without (any )?(limits?|restrictions?|ethics))\b",
            re.I,
        ),
        32,
    ),
    Pattern(
        "role_change",
        re.compile(
            r"\b(pretend|act as if|roleplay as)\s+(you (have )?no |being )?(guidelines?|restrictions?|safety|"
            r"an? evil|developer mode)\b",
            re.I,
        ),
        28,
    ),
    Pattern(
        "role_change",
        re.compile(r"\bdeveloper mode (enabled|on)\b", re.I),
        30,
    ),
    Pattern(
        "secret_extraction",
        re.compile(
            r"\b(reveal|show|print|dump|repeat|output|give)\s+(me\s+)?(us\s+)?"
            r"((your|the|hidden|secret)\s+)*(system prompt|hidden instructions?|initial instructions?)\b",
            re.I,
        ),
        38,
    ),
    Pattern(
        "secret_extraction",
        re.compile(
            r"\b(api[_ ]?keys?|access tokens?|credentials?|secrets?|passwords?)\b.{0,40}"
            r"\b(reveal|show|dump|print|send|give|exfiltrate)\b"
            r"|\b(reveal|show|dump|print|send|give|exfiltrate)\b.{0,40}"
            r"\b(api[_ ]?keys?|access tokens?|credentials?|secrets?|passwords?)\b",
            re.I,
        ),
        40,
    ),
    Pattern(
        "tool_abuse",
        re.compile(
            r"\b(call|execute|run|invoke|use)\s+(the\s+)?(tool\s+)?"
            r"(send_email|delete_user|transfer_money|exfiltrate|http_request)\b",
            re.I,
        ),
        36,
    ),
    Pattern(
        "tool_abuse",
        re.compile(
            r"\b(send (an? )?email to|transfer (funds?|money)|delete (the )?user|"
            r"do not ask (for )?confirmation|without confirmation)\b",
            re.I,
        ),
        30,
    ),
    Pattern(
        "credential_theft",
        re.compile(
            r"\b(steal|harvest|capture|phish|exfiltrate)\s+"
            r"((the|all|user|customer)\s+)*(passwords?|credentials?|cookies?|tokens?|credit cards?)\b",
            re.I,
        ),
        38,
    ),
    Pattern(
        "credential_theft",
        re.compile(
            r"\b(send|post|upload|forward)\s+"
            r"((all|the|user|customer)\s+)*(passwords?|credentials?|session cookies?|auth tokens?)\s+"
            r"(to|at)\b",
            re.I,
        ),
        36,
    ),
    Pattern(
        "credential_theft",
        re.compile(
            r"\b(password|passwd|credit card|cvv|ssn|session cookie)s?\b.{0,40}"
            r"\b(attacker|evil\.|pastebin|webhook)\b",
            re.I,
        ),
        34,
    ),
    Pattern(
        "indirect_prompt_injection",
        re.compile(
            r"\b(important|note|attention|system|ai|assistant)\s*[:\-].{0,40}"
            r"(ignore|you must|new instructions?|from now on)\b",
            re.I,
        ),
        28,
    ),
    Pattern(
        "indirect_prompt_injection",
        re.compile(r"\bwhen (an? )?(ai|llm|language model|assistant) reads this\b", re.I),
        34,
    ),
]


def _search(channel: Channel, matching: str) -> list[RuleHit]:
    hits: list[RuleHit] = []
    seen: set[tuple[str, str]] = set()
    for pat in PATTERNS:
        for m in pat.regex.finditer(matching):
            snippet = m.group(0)
            key = (pat.attack_type, snippet.casefold())
            if key in seen:
                continue
            seen.add(key)
            hits.append(
                RuleHit(
                    attack_type=pat.attack_type,
                    channel=channel,
                    text=snippet,
                    weight=pat.weight,
                    start=m.start(),
                    end=m.end(),
                )
            )
    return hits


def looks_like_benign_question(user_matching: str) -> bool:
    return bool(BENIGN_INTENT.search(user_matching)) and not re.search(
        r"\b(now|instead)\b.{0,30}\b(ignore|reveal|send)\b", user_matching, re.I
    )


def run_rules(user_matching: str, untrusted_matching: str) -> list[RuleHit]:
    hits = _search("user_intent", user_matching)
    if untrusted_matching:
        untrusted_hits = _search("untrusted_content", untrusted_matching)
        remapped: list[RuleHit] = []
        for hit in untrusted_hits:
            if hit.attack_type != "indirect_prompt_injection":
                remapped.append(
                    RuleHit(
                        attack_type="indirect_prompt_injection",
                        channel="untrusted_content",
                        text=hit.text,
                        weight=hit.weight + 10,
                        start=hit.start,
                        end=hit.end,
                    )
                )
                remapped.append(hit.model_copy(update={"weight": max(8, hit.weight // 2)}))
            else:
                remapped.append(hit)
        hits.extend(remapped)

    if looks_like_benign_question(user_matching):
        hits = [
            h
            for h in hits
            if not (h.channel == "user_intent" and h.attack_type in {"instruction_override", "role_change"})
        ]
    return hits
