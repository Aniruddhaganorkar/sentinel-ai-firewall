from __future__ import annotations

import json
import statistics
from pathlib import Path

from app.firewall.pipeline import scan_content
from app.models import ScanRequest, SourceType

DATASET = Path(__file__).with_name("dataset.json")


def load_cases() -> list[dict]:
    return json.loads(DATASET.read_text())


def run_eval() -> dict:
    cases = load_cases()
    rows = []
    latencies = []
    tp = fp = fn = tn = 0
    by_type: dict[str, dict[str, int]] = {}

    for case in cases:
        req = ScanRequest(
            user_input=case["user_input"],
            untrusted_content=case.get("untrusted_content") or "",
            source=SourceType(case.get("source") or "text"),
        )
        result = scan_content(req, use_llm=False)
        latencies.append(result.latency_ms)
        expected = case["expected_action"]
        predicted = result.action.value
        malicious_expected = expected in {"BLOCK", "SANITIZE"}
        malicious_pred = predicted in {"BLOCK", "SANITIZE"}
        if malicious_expected and malicious_pred:
            tp += 1
        elif not malicious_expected and malicious_pred:
            fp += 1
        elif malicious_expected and not malicious_pred:
            fn += 1
        else:
            tn += 1
        family = case.get("type") or "benign"
        bucket = by_type.setdefault(family, {"n": 0, "caught": 0, "false_positive": 0})
        bucket["n"] += 1
        if family != "benign" and malicious_pred:
            bucket["caught"] += 1
        if family == "benign" and malicious_pred:
            bucket["false_positive"] += 1
        rows.append(
            {
                "id": case["id"],
                "type": family,
                "expected": expected,
                "predicted": predicted,
                "risk_score": result.risk_score,
                "attack_types": result.attack_types,
                "ok": predicted == expected
                or (malicious_expected and malicious_pred and predicted in {"BLOCK", "SANITIZE"}),
            }
        )

    n = max(1, len(cases))
    detection = tp / max(1, tp + fn)
    fpr = fp / max(1, fp + tn)
    latencies_sorted = sorted(latencies)
    p50 = latencies_sorted[len(latencies_sorted) // 2] if latencies_sorted else 0
    p95 = latencies_sorted[int(len(latencies_sorted) * 0.95)] if latencies_sorted else 0
    return {
        "total": n,
        "true_positives": tp,
        "false_positives": fp,
        "false_negatives": fn,
        "true_negatives": tn,
        "detection_rate": round(detection, 3),
        "false_positive_rate": round(fpr, 3),
        "avg_latency_ms": round(statistics.mean(latencies), 2) if latencies else 0,
        "p50_latency_ms": round(p50, 2),
        "p95_latency_ms": round(p95, 2),
        "by_type": by_type,
        "cases": rows,
    }
