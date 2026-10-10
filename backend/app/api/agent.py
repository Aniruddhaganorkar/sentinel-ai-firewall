from fastapi import APIRouter

from app.agent.runner import run_agent
from app.firewall.pipeline import scan_content
from app.models import AgentRunRequest, AgentRunResponse

router = APIRouter(prefix="/agent", tags=["agent"])


@router.post("/run", response_model=AgentRunResponse)
def agent_run(req: AgentRunRequest) -> AgentRunResponse:
    scan = scan_content(req, use_llm=False)
    return run_agent(req, scan)
