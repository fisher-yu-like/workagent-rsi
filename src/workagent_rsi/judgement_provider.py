"""Schemas retained for reading historical visual-review records."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator



class VisualObservation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    image_id: str = Field(min_length=1)
    artifact_location: str = Field(min_length=1)
    region: str = Field(min_length=1)
    observation: str = Field(min_length=1)


class VisualJudgement(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)
    status: Literal["PASS", "PARTIAL", "FAIL", "NEEDS_REVIEW"]
    completion: float | None = Field(default=None, ge=0, le=1)
    observed: str = Field(min_length=1)
    confidence: float | None = Field(default=None, ge=0, le=1)
    observations: list[VisualObservation] = Field(min_length=1)

    @model_validator(mode="after")
    def score_matches_status(self):
        if self.status == "PASS" and self.completion != 1:
            raise ValueError("PASS requires completion=1")
        if self.status == "FAIL" and self.completion != 0:
            raise ValueError("FAIL requires completion=0")
        if self.status == "PARTIAL" and (self.completion is None or not 0 < self.completion < 1):
            raise ValueError("PARTIAL requires 0 < completion < 1")
        if self.status == "NEEDS_REVIEW" and self.completion is not None:
            raise ValueError("NEEDS_REVIEW cannot carry a score")
        return self
