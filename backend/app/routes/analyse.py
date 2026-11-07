from functools import lru_cache

from fastapi import APIRouter, Depends, HTTPException

from app.models.analyse import AnalyzeRequest, AnalysisResponse
from app.services.analysis import PullRequestAnalysisService
from app.services.github import GitHubClientError, InvalidPullRequestUrl


router = APIRouter()


@lru_cache
def get_analysis_service() -> PullRequestAnalysisService:
    return PullRequestAnalysisService()


@router.post("/analyse", response_model=AnalysisResponse)
async def analyze_pull_request(
    request: AnalyzeRequest,
    service: PullRequestAnalysisService = Depends(get_analysis_service),
):
    try:
        return await service.analyse(request.pull_request_url)
    except InvalidPullRequestUrl as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except GitHubClientError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error
    except OSError as error:
        raise HTTPException(
            status_code=500,
            detail="The repository could not be prepared for analysis",
        ) from error
