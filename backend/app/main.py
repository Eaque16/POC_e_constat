from fastapi import FastAPI

from backend.app.api.claims import router as claims_router
from backend.app.api.transcription import router as transcription_router

app = FastAPI(
    title="E-Constat IA API",
    version="0.1.0"
)

app.include_router(transcription_router)
app.include_router(claims_router)


@app.get("/")
def root():
    return {
        "project": "E-Constat IA",
        "status": "running"
    }


@app.get("/health")
def health():
    return {
        "status": "ok"
    }
