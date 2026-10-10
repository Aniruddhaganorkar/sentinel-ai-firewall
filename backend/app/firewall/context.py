from __future__ import annotations

import re

from app.models import RuleHit

TASK_RE = re.compile(
    r"\b(summarize|summarise|extract|translate|parse|read|analyze|analyse|"
    r"what does|describe|review|fetch)\b",
    re.I,
)

INSTRUCTION_IN_DATA = re.compile(
    r"\b(ignore (all )?(previous|prior)|you are now|reveal (your|the) (system prompt|api)|"
    r"send (all )?(data|credentials|secrets)|new instructions?:|from now on you must)\b",
    re.I,
)


def analyze_context(user_matching: str, untrusted_matching: str, hits: list[RuleHit]) -> list[RuleHit]:
    extra = list(hits)
    if not untrusted_matching:
        return extra
    user_is_task = bool(TASK_RE.search(user_matching)) or len(user_matching) < 200
    data_has_instructions = bool(INSTRUCTION_IN_DATA.search(untrusted_matching))
    already_indirect = any(h.attack_type == "indirect_prompt_injection" for h in hits)
    if user_is_task and data_has_instructions and not already_indirect:
        m = INSTRUCTION_IN_DATA.search(untrusted_matching)
        extra.append(
            RuleHit(
                attack_type="indirect_prompt_injection",
                channel="untrusted_content",
                text=m.group(0) if m else untrusted_matching[:80],
                weight=36,
                start=m.start() if m else None,
                end=m.end() if m else None,
            )
        )
    return extra
