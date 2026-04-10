from fastapi import FastAPI
from api.routes.citations import router as citations_router

app = FastAPI(
    title="Vera.fidei API",
    version="0.1.0",
    description="Backend do MVP do verificador de citações teológicas.",
)

app.include_router(citations_router, prefix="/citations", tags=["Citations"])


@app.get("/")
def root() -> dict[str, str]:
    return {"app": "Vera.fidei", "status": "ok"}
