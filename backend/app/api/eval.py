import logging

from fastapi import APIRouter

from app.eval.runner import run_eval
from app.logging_setup import get_request_id

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/eval", tags=["eval"])


@router.post("/run")
def eval_run() -> dict:
    logger.info("eval start")
    result = run_eval()
    result["request_id"] = get_request_id()
    logger.info(
        "eval done total=%s detection=%s fpr=%s fp=%s fn=%s",
        result.get("total"),
        result.get("detection_rate"),
        result.get("false_positive_rate"),
        result.get("false_positives"),
        result.get("false_negatives"),
    )
    return result
