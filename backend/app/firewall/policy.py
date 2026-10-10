from app.models import Action


def decide_action(risk_score: int) -> Action:
    if risk_score >= 70:
        return Action.BLOCK
    if risk_score >= 30:
        return Action.SANITIZE
    return Action.ALLOW
