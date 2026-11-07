import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes.analyse import router as analyse_router


def create_app() -> FastAPI:
    application = FastAPI(
        title="TestPilot API",
        description="Dependency-aware automated test recommendations for GitHub pull requests.",
        version="1.0.0",
    )

    origins = [
        origin.strip()
        for origin in os.getenv("TESTPILOT_CORS_ORIGINS", "http://localhost:5173").split(",")
        if origin.strip()
    ]
    application.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "Authorization"],
    )

    application.include_router(analyse_router, prefix="/api")

    @application.get("/")
    async def root():
        return {"message": "Welcome to the TestPilot API", "version": "1.0.0"}

    @application.get("/health")
    async def health():
        return {"status": "healthy"}

    return application


app = create_app()
