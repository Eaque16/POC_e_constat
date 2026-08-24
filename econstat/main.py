from fastapi import FastAPI

from econstat.api.auth import router as auth_router
from econstat.api.jobs import router as jobs_router
from econstat.api.routes import router

app = FastAPI(
    title="E-Constat IA",
    version="0.1.0",
    description="POC d'assistance IA. Aucun envoi sans validation humaine explicite.",
)
app.include_router(auth_router, prefix="/api")
app.include_router(jobs_router, prefix="/api")
app.include_router(router, prefix="/api")


@app.get("/health")
def health():
    return {"status": "ok", "human_validation_required": True}
