from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.services.github import parse_github_pull_request_url


class AnalyzeRequest(BaseModel):
    pull_request_url: str = Field(min_length=20, max_length=500)

    @field_validator("pull_request_url")
    @classmethod
    def validate_pull_request_url(cls, value: str) -> str:
        parse_github_pull_request_url(value)
        return value.strip()


class PullRequestInfo(BaseModel):
    title: str
    number: int
    repository: str
    url: str
    base_sha: str
    head_sha: str


class ChangedFile(BaseModel):
    path: str
    status: str
    additions: int
    deletions: int
    changed_functions: list[str] = Field(default_factory=list)
    changed_classes: list[str] = Field(default_factory=list)
    changed_lines: list[int] = Field(default_factory=list)
    analysis_status: Literal[
        "analysed", "file_level", "unsupported", "missing_source", "parse_failed"
    ] = "analysed"
    module_level_change: bool = False


class RecommendedTest(BaseModel):
    test_file: str
    test_name: str
    test_class: str | None = None
    node_id: str
    framework: Literal["pytest", "unittest"]
    priority: Literal["low", "medium", "high", "critical"]
    confidence: float = Field(ge=0, le=1)
    reasons: list[str]


class AnalysisResponse(BaseModel):
    pull_request: PullRequestInfo
    risk_score: int = Field(ge=0, le=100)
    risk_level: Literal["low", "medium", "high", "critical"]
    selection_mode: Literal["targeted", "conservative"]
    summary: str
    changed_files: list[ChangedFile]
    recommended_tests: list[RecommendedTest]
    total_tests_discovered: int
    tests_selected: int
