
from pydantic import BaseModel, Field
from typing import Literal


class AnalyzeRequest(BaseModel):
    pull_request_url: str


class PullRequestInfo(BaseModel):
    title: str
    number: int
    repository: str
    url: str


class ChangedFile(BaseModel):
    path: str
    status: str
    additions: int
    deletions: int
    changed_functions: list[str] = Field(default_factory=list)
    changed_classes: list[str] = Field(default_factory=list)


class RecommendedTest(BaseModel):
    test_file: str
    test_name: str
    priority: Literal["low", "medium", "high", "critical"]
    confidence: float = Field(ge=0, le=1)
    reasons: list[str]


class AnalysisResponse(BaseModel):
    pull_request: PullRequestInfo
    risk_score: int = Field(ge=0, le=100)
    risk_level: Literal["low", "medium", "high", "critical"]
    summary: str
    changed_files: list[ChangedFile]
    recommended_tests: list[RecommendedTest]
