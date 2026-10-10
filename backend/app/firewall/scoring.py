from __future__ import annotations

from app.models import RuleHit

FAMILY_BONUS = {
    "secret_extraction": 15,
    "credential_theft": 15,
    "tool_abuse": 15,
    "encoded_instructions": 12,
    "indirect_prompt_injection": 12,
    "instruction_override": 8,
    "role_change": 8,
}


def score_risk(hits: list[RuleHit], llm_malicious: bool, llm_confidence: float) -> int:
    rule_weight = min(55, sum(h.weight for h in hits))
    llm_part = int(llm_confidence * 40) if llm_malicious else 0
    families = {h.attack_type for h in hits}
    family_bonus = sum(FAMILY_BONUS.get(f, 0) for f in families)
    untrusted_bonus = 15 if any(h.channel == "untrusted_content" for h in hits) else 0
    total = rule_weight + llm_part + min(20, family_bonus) + untrusted_bonus
    if hits:
        top = max(h.weight for h in hits)
        if top >= 30:
            total = max(total, 75)
        elif top >= 20:
            total = max(total, 45)
    if not hits and not llm_malicious:
        total = min(total, 10)
    return max(0, min(100, total))
