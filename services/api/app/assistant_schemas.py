from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Topic = Literal[
    "OVERVIEW",
    "COMPLETION",
    "SCHEDULE",
    "COST",
    "FORECAST",
    "RAG",
    "RISKS",
    "EVIDENCE",
    "NEXT_REVIEW",
]


class SnapshotQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    question: str = Field(default="", max_length=2000)
    topic: Topic | None = None

    @model_validator(mode="after")
    def requires_query(self):
        if not self.question and self.topic is None:
            raise ValueError("Provide a status question or selected topic")
        return self


class SnapshotAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid")
    snapshot_id: str
    data_date: str
    topic: str
    status: str
    generator_version: str
    semantic_notice: str
    facts: list[dict[str, Any]]
    considerations: list[dict[str, Any]]
    limitations: list[str]
    answer_hash: str
