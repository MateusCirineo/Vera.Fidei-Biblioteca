from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.routes.citations import router as citations_router
from api.routes.books import router as books_router
from api.routes.pdfs import router as pdfs_router
from api.routes.authors import router as authors_router

app = FastAPI(
    title="Vera.fidei API",
    version="0.1.0",
    description="Backend do MVP do verificador de citações teológicas.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://192.168.0.3:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(citations_router, prefix="/citations", tags=["Citations"])
app.include_router(books_router, prefix="/books", tags=["Books"])
app.include_router(pdfs_router, prefix="/pdfs", tags=["PDFs"])
app.include_router(authors_router, prefix="/authors", tags=["Authors"])


@app.get("/")
def root() -> dict[str, str]:
    return {"app": "Vera.fidei", "status": "ok"}
