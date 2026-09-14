"""Structured agent state and output.

The agent's PUBLIC output is always a validated `AgentAssessment` - never
arbitrary text used for application logic, and never the model's private
chain-of-thought (see agent_guardrails.py and flockguard_agent.py).
`AgentState` is the bookkeeping record persisted as one document under
organizations/{org_id}/agent_runs/{run_id} for auditability, debugging,
and cost analysis.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


class Priority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class Confidence(str, Enum):
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"


class KnowledgeSource(BaseModel):
    """Citation-only - never the chunk content itself. If a source isn't
    in here, the agent must not claim to have used it."""

    document_id: str
    title: str
    publisher: str | None = None
    section: str | None = None
    page: int | None = None
    source_url: str | None = None


class AgentAssessment(BaseModel):
    """The agent's validated, structured output - the only thing ever used
    for application logic or persisted as a recommendation. Model output
    that doesn't fit this shape is rejected, not coerced (see
    flockguard_agent.py's validate-or-retry-once handling)."""

    priority: Priority
    house_id: str | None = None
    summary: str
    observed_data: list[str] = Field(default_factory=list)
    calculated_signals: list[str] = Field(default_factory=list)
    historical_context: list[str] = Field(default_factory=list)
    reference_guidance: list[str] = Field(default_factory=list)
    knowledge_sources: list[KnowledgeSource] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)
    confidence: Confidence
    requires_inspection: bool = False
    requires_human_action: bool = False


class ToolCallRecord(BaseModel):
    """One tool invocation for the audit trail - name and arguments only,
    never the model's private reasoning about why it chose the tool."""

    tool: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class AgentState(BaseModel):
    run_id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    trigger: str
    org_id: str
    farm_id: str | None = None
    house_id: str | None = None
    flock_id: str | None = None
    source_event_id: str | None = None

    skill: str
    question: str | None = None

    tools_called: list[ToolCallRecord] = Field(default_factory=list)
    rag_queries: list[str] = Field(default_factory=list)
    rag_sources_used: list[KnowledgeSource] = Field(default_factory=list)

    assessment: AgentAssessment | None = None
    status: Literal["running", "completed", "failed"] = "running"
    error_summary: str | None = None
    model: str | None = None

    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    completed_at: str | None = None

    def to_run_document(self) -> dict:
        """The trimmed shape actually persisted to Firestore - deliberately
        excludes anything resembling private model reasoning, API keys, or
        full raw payloads."""
        assessment = self.assessment
        return {
            "run_id": self.run_id,
            "trigger": self.trigger,
            "org_id": self.org_id,
            "farm_id": self.farm_id,
            "house_id": self.house_id,
            "flock_id": self.flock_id,
            "source_event_id": self.source_event_id,
            "skill": self.skill,
            "tools_used": [t.tool for t in self.tools_called],
            "tool_calls": [t.model_dump() for t in self.tools_called],
            "rag_queries": self.rag_queries,
            "rag_sources_used": [s.model_dump() for s in self.rag_sources_used],
            "evidence_summary": assessment.summary if assessment else None,
            "priority": assessment.priority.value if assessment else None,
            "recommendation_summary": (
                "; ".join(assessment.recommended_actions) if assessment and assessment.recommended_actions else None
            ),
            "requires_human_action": assessment.requires_human_action if assessment else False,
            "status": self.status,
            "model": self.model,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
            "error_summary": self.error_summary,
        }
