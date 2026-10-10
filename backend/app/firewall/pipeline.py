from __future__ import annotations

import logging
import time

from app.firewall.classifier import classify
from app.firewall.context import analyze_context
from app.firewall.extractors import extract_untrusted
from app.firewall.normalize import normalize
from app.firewall.policy import decide_action
from app.firewall.rules import run_rules
from app.firewall.sanitize import sanitize
from app.firewall.scoring import score_risk
from app.logging_setup import get_request_id, preview
from app.models import Action, AttackType, Evidence, RuleHit, ScanRequest, ScanResult

logger = logging.getLogger(__name__)

VALID_TYPES: set[str] = {
    "instruction_override",
    "role_change",
    "secret_extraction",
    "tool_abuse",
    "credential_theft",
    "encoded_instructions",
    "indirect_prompt_injection",
}


def scan_content(
    req: ScanRequest,
    untrusted_binary: bytes | None = None,
    *,
    use_llm: bool = True,
) -> ScanResult:
    t0 = time.perf_counter()
    rid = get_request_id()
    logger.info(
        "scan start source=%s user=%s untrusted=%s",
        req.source.value,
        preview(req.user_input),
        preview(req.untrusted_content),
    )
    extracted = extract_untrusted(req.untrusted_content, req.source, untrusted_binary)
    user_n = normalize(req.user_input)
    data_n = normalize(extracted)

    hits = run_rules(user_n["matching"], data_n["matching"])
    hits = analyze_context(user_n["matching"], data_n["matching"], hits)
    extras = list(user_n.get("extras") or []) + list(data_n.get("extras") or [])
    if extras and hits and not any(h.attack_type == "encoded_instructions" for h in hits):
        src = "untrusted_content" if data_n.get("extras") else "user_intent"
        hits.append(
            RuleHit(
                attack_type="encoded_instructions",
                channel=src,
                text=str(extras[0])[:160],
                weight=34,
            )
        )
    high_rule = sum(h.weight for h in hits) >= 40
    skip_llm = (not use_llm) or high_rule
    if skip_llm:
        logger.info(
            "classifier skipped high_rule=%s use_llm=%s",
            high_rule,
            use_llm,
        )
        llm = {
            "attack_types": [],
            "is_malicious": False,
            "confidence": 0.0,
            "evidence": [],
            "rationale": "rules already decisive; Gemini skipped to save quota"
            if high_rule
            else "rules-only scan",
            "used": False,
        }
    else:
        llm = classify(user_n["decoded"], data_n["decoded"], hits)
    llm_malicious = bool(llm.get("is_malicious"))
    llm_conf = float(llm.get("confidence") or 0)

    risk = score_risk(hits, llm_malicious, llm_conf)
    if llm.get("used") is False and high_rule:
        risk = max(risk, 75)

    action = decide_action(risk)
    attack_types: list[AttackType] = []
    for h in hits:
        if h.attack_type in VALID_TYPES and h.attack_type not in attack_types:
            attack_types.append(h.attack_type)  # type: ignore[arg-type]
    for t in llm.get("attack_types") or []:
        if t in VALID_TYPES and t not in attack_types:
            attack_types.append(t)

    evidence = [
        Evidence(text=h.text, channel=h.channel, attack_type=h.attack_type, start=h.start, end=h.end)
        for h in hits
    ]
    for span in llm.get("evidence") or []:
        if span and not any(e.text == span for e in evidence):
            channel = "untrusted_content" if span.lower() in data_n["matching"] else "user_intent"
            atype: AttackType = attack_types[0] if attack_types else "instruction_override"
            evidence.append(Evidence(text=span[:240], channel=channel, attack_type=atype))

    rationale_parts = []
    if hits:
        rationale_parts.append(
            f"Rules matched {len(hits)} span(s) across "
            + ", ".join(sorted({h.channel for h in hits}))
            + "."
        )
    if llm.get("used"):
        rationale_parts.append(str(llm.get("rationale") or ""))
    else:
        rationale_parts.append(str(llm.get("rationale") or "rules-only"))
    if action == Action.BLOCK:
        rationale_parts.append("Blocked before the agent or tools could run.")
    elif action == Action.SANITIZE:
        rationale_parts.append("Suspicious spans stripped; remainder wrapped as data, not instructions.")

    sanitized_user, sanitized_untrusted = sanitize(
        user_n["decoded"], data_n["decoded"], hits, action
    )

    latency_ms = round((time.perf_counter() - t0) * 1000, 2)
    logger.info(
        "scan done action=%s risk=%s types=%s classifier=%s latency_ms=%s",
        action.value,
        risk,
        attack_types,
        bool(llm.get("used")),
        latency_ms,
    )
    return ScanResult(
        action=action,
        risk_score=risk,
        attack_types=attack_types,
        evidence=evidence,
        rationale=" ".join(p for p in rationale_parts if p).strip(),
        latency_ms=latency_ms,
        sanitized_user_input=sanitized_user if action != Action.BLOCK else None,
        sanitized_untrusted_content=sanitized_untrusted,
        rule_hits=hits,
        classifier_used=bool(llm.get("used")),
        classifier_confidence=llm_conf if llm.get("used") else None,
        request_id=rid,
        quota_exhausted=bool(llm.get("quota_exhausted")),
        llm_error=llm.get("llm_error"),
    )
