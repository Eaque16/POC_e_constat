from fastapi import FastAPI

app = FastAPI(
    title="E-Constat IA API",
    version="0.1.0"
)


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
