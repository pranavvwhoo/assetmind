"""Structured Pydantic results returned by the CrewAI agents."""

from pydantic import BaseModel, Field


class Finding(BaseModel):
    title: str
    detail: str
    severity: str = "info"
    evidence: str = ""


class QualityAnalysis(BaseModel):
    findings: list[Finding] = Field(default_factory=list)
    correction_actions: list[str] = Field(default_factory=list)


class AnalyticsInterpretation(BaseModel):
    observations: list[Finding] = Field(default_factory=list)
    hypotheses_to_investigate: list[str] = Field(default_factory=list)


class Recommendation(BaseModel):
    priority: str
    action: str
    rationale: str


class ReportDraft(BaseModel):
    executive_summary: str
    findings: list[Finding] = Field(default_factory=list)
    recommendations: list[Recommendation] = Field(default_factory=list)


class ReviewResult(BaseModel):
    passed: bool
    required_sections_present: list[str] = Field(default_factory=list)
    unsupported_claims: list[str] = Field(default_factory=list)
    issues: list[str] = Field(default_factory=list)
    revision_instructions: list[str] = Field(default_factory=list)
