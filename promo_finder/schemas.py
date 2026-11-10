"""Pydantic schemas: the contract between code and the LLM, and between pipeline stages.

LLM outputs are parsed straight into these models with LangChain's
`with_structured_output(...)`. A reply that breaks a field rule (bad beat ID, score out
of range, missing field) raises a validation error and is retried. Bad data never
reaches the timeline arithmetic.
"""
from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator

BEAT_RE = re.compile(r"B\d{3}")


def _beat_id(v: str) -> str:
    m = BEAT_RE.search(str(v).upper())
    if not m:
        raise ValueError(f"'{v}' is not a beat ID like B012")
    return m.group(0)


# ----------------------------------------------------------------- LLM output: promo picker
class SegmentPick(BaseModel):
    start_beat: str = Field(description="Beat ID where this segment starts, e.g. B012")
    end_beat: str = Field(description="Beat ID where this segment ends (inclusive), e.g. B031")

    @field_validator("start_beat", "end_beat")
    @classmethod
    def _norm(cls, v: str) -> str:
        return _beat_id(v)


class PromoPick(BaseModel):
    title: str = Field(description="Short internal name for the promo")
    segments: list[SegmentPick] = Field(min_length=1, max_length=3,
                                        description="1-3 segments in story order; 20-60 s in total")
    hook_beat: str = Field(description="Beat ID of the hook; must start within 3 s of the first segment's start")
    hook: str = Field(description="What the viewer sees/hears in the first 3 seconds")
    cliffhanger_beat: str = Field(description="Beat ID of the last line/action the promo cuts on")
    cliffhanger: str = Field(description="The unresolved moment the promo ends on")
    why: str = Field(description="One line on why it works as an ad")
    pattern: str = Field(description="Name of the playbook pattern this follows, or 'other'")
    hook_score: int = Field(ge=1, le=10)
    cliffhanger_score: int = Field(ge=1, le=10)
    standalone_score: int = Field(ge=1, le=10, description="How well a stranger follows it with zero context")
    spoiler_risk: Literal["low", "medium", "high"]
    context_needed: str = Field(description="What a brand-new viewer would not understand; empty if nothing")

    @field_validator("hook_beat", "cliffhanger_beat")
    @classmethod
    def _norm(cls, v: str) -> str:
        return _beat_id(v)


class EpisodePicks(BaseModel):
    promos: list[PromoPick] = Field(max_length=3, description="1-3 non-overlapping promos, best first")
    skipped_reason: str = Field(description="Why fewer than 3 promos were returned; empty if not applicable")


# ----------------------------------------------------------------- LLM output: blind viewer
class BlindVerdict(BaseModel):
    what_is_happening: str = Field(description="One sentence, in your own words")
    confused_by: list[str] = Field(description="Things you could not follow; empty list if none")
    stop_scrolling: int = Field(ge=1, le=10, description="Did the first 3 seconds make you stop?")
    want_next: int = Field(ge=1, le=10, description="How badly do you need to know what happens next?")
    understood: int = Field(ge=1, le=10, description="How well did you follow it with zero context?")


# ----------------------------------------------------------------- LLM output: montage composer
class MontagePlan(BaseModel):
    title: str
    moment_ids: list[str] = Field(min_length=2, max_length=4, description="Moment IDs (M###) in story order")
    hook: str
    cliffhanger: str
    why: str
    hook_score: int = Field(ge=1, le=10)
    cliffhanger_score: int = Field(ge=1, le=10)
    standalone_score: int = Field(ge=1, le=10)
    spoiler_risk: Literal["low", "medium", "high"]


class MontagePlans(BaseModel):
    montages: list[MontagePlan] = Field(max_length=3)


# ----------------------------------------------------------------- pipeline objects
class Segment(BaseModel):
    ep: int
    start: float
    end: float
    start_beat: str = ""
    end_beat: str = ""

    @property
    def duration(self) -> float:
        return round(self.end - self.start, 2)


class Promo(BaseModel):
    id: str
    kind: Literal["single", "multi-moment", "montage", "rules"]
    segments: list[Segment]
    title: str = ""
    hook: str = ""
    cliffhanger: str = ""
    why: str = ""
    pattern: str = ""
    hook_beat: str = ""
    cliffhanger_beat: str = ""
    scores: dict[str, float] = Field(default_factory=dict)
    rules_score: float = 0.0
    blind: BlindVerdict | None = None
    spoiler_risk: str = "low"
    context_needed: str = ""
    passed: bool = True
    problems: list[str] = Field(default_factory=list)
    fixes: list[str] = Field(default_factory=list)
    retrieved_patterns: list[str] = Field(default_factory=list)
    model: str = ""
    final_score: float = 0.0
    rank: int = 0

    @property
    def duration(self) -> float:
        return round(sum(s.duration for s in self.segments), 2)

    @property
    def episodes(self) -> list[int]:
        return sorted({s.ep for s in self.segments})
