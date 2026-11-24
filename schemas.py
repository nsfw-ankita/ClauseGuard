"""Pydantic models for ClauseGuard AI output validation."""

from typing import Literal

from pydantic import BaseModel, Field, field_validator


class Clause(BaseModel):
    clause_text: str = Field(..., min_length=1)
    color: Literal["red", "yellow", "green"]
    explanation: str = Field(..., min_length=1)

    @field_validator("explanation")
    @classmethod
    def limit_explanation_words(cls, value: str) -> str:
        words = value.split()
        if len(words) > 25:
            return " ".join(words[:25])
        return value.strip()


class SuggestedChange(BaseModel):
    issue: str = Field(..., min_length=1)
    polite_request_message: str = Field(..., min_length=1)


class AnalysisResult(BaseModel):
    document_type_ok: bool
    clauses: list[Clause] = Field(default_factory=list)
    missing_clauses: list[str] = Field(default_factory=list)
    suggested_changes: list[SuggestedChange] = Field(default_factory=list)


class RuleCheck(BaseModel):
    key: str
    label_en: str
    label_hi: str
    present: bool
    evidence: str = ""
