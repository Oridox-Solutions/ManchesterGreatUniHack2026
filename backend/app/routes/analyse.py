
from fastapi import APIRouter

from app.models.analyse import (
    AnalyzeRequest,
    AnalysisResponse,
    PullRequestInfo,
)

router = APIRouter()


@router.post("/analyse", response_model=AnalysisResponse)
async def analyze_pull_request(request: AnalyzeRequest):

    # Temporary mock response.
    # We will replace this with real GitHub analysis.

    return AnalysisResponse(
        pull_request=PullRequestInfo(
            title="Update authentication",
            number=12,
            repository="example/demo-project",
            url=request.pull_request_url,
        ),
        risk_score=78,
        risk_level="high",
        summary="Authentication changes affect several modules.",
        changed_files=[],
        recommended_tests=[],
    )
