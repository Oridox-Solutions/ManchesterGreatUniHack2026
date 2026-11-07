
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes.analyse import router as analyse_router

app = FastAPI(
    title="TestPilot API",
    description="Intelligent automated test recommendations for GitHub pull requests.",
    version="0.1.0"
)

# Allow our React frontend to communicate with the backend.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(analyse_router, prefix="/api")

@app.get("/")
async def root():
    return {"message": "Welcome to the TestPilot API"}


@app.get("/health")
async def health():
    return {"status": "healthy"}
