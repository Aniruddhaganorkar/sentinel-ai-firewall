from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class SourceType(str, Enum):
    text = "text"
    html = "html"
    markdown = "markdown"
    pdf = "pdf"
    json = "json"
    url = "url"


class Action(str, Enum):
    ALLOW = "ALLOW"
    SANITIZE = "SANITIZE"
    BLOCK = "BLOCK"


AttackType = Literal[
    "instruction_override",
    "role_change",
    "secret_extraction",
    "tool_abuse",
    "credential_theft",
    "encoded_instructions",
    "indirect_prompt_injection",
]

Channel = Literal["user_intent", "untrusted_content"]


class ScanRequest(BaseModel):
    user_input: str = Field(..., min_length=1)
    untrusted_content: str = ""
    source: SourceType = SourceType.text


class Evidence(BaseModel):
    text: str
    channel: Channel
    attack_type: AttackType
    start: int | None = None
    end: int | None = None


class RuleHit(BaseModel):
    attack_type: AttackType
    channel: Channel
    text: str
    weight: int
    start: int | None = None
    end: int | None = None


class ScanResult(BaseModel):
    action: Action
    risk_score: int
    attack_types: list[AttackType]
    evidence: list[Evidence]
    rationale: str
    latency_ms: float
    sanitized_user_input: str | None = None
    sanitized_untrusted_content: str | None = None
    rule_hits: list[RuleHit] = Field(default_factory=list)
    classifier_used: bool = False
    classifier_confidence: float | None = None
    request_id: str = ""
    quota_exhausted: bool = False
    llm_error: str | None = None


class AgentRunRequest(ScanRequest):
    pass


class ToolEvent(BaseModel):
    name: str
    arguments: dict
    allowed: bool
    reason: str
    result: str | None = None


class AgentRunResponse(BaseModel):
    scan: ScanResult
    agent_ran: bool
    agent_output: str | None = None
    tool_events: list[ToolEvent] = Field(default_factory=list)
    request_id: str = ""
