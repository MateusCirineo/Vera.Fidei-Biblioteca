import os

# Must be set before any torch/tokenizer import to prevent deadlocks
# when PyTorch OpenMP threads conflict with uvicorn's thread pool.
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("TORCH_NUM_THREADS", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes.api_keys import router as api_keys_router
from api.routes.api_v1 import router as api_v1_router
from api.routes.auth import router as auth_router
from api.routes.authors import router as authors_router
from api.routes.billing import router as billing_router
from api.routes.books import router as books_router
from api.routes.citations import router as citations_router
from api.routes.favorites import router as favorites_router
from api.routes.institutions import router as institutions_router
from api.routes.pdfs import router as pdfs_router
from api.routes.search import router as search_router
from core.auth import require_api_key
from models.database import init_db

app = FastAPI(
    title="Vera.fidei API",
    version="0.1.0",
    description="Backend do MVP do verificador de citacoes teologicas.",
    redirect_slashes=False,
)

_cors_origins = os.getenv(
    "CORS_ORIGINS",
    "http://localhost:3000,http://192.168.0.3:3000",
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(
    citations_router,
    prefix="/citations",
    tags=["Citations"],
    dependencies=[Depends(require_api_key)],
)
app.include_router(
    books_router,
    prefix="/books",
    tags=["Books"],
    dependencies=[Depends(require_api_key)],
)
app.include_router(
    pdfs_router,
    prefix="/pdfs",
    tags=["PDFs"],
    dependencies=[Depends(require_api_key)],
)
app.include_router(
    authors_router,
    prefix="/authors",
    tags=["Authors"],
    dependencies=[Depends(require_api_key)],
)
app.include_router(
    favorites_router,
    prefix="/favorites",
    tags=["Favorites"],
    dependencies=[Depends(require_api_key)],
)
app.include_router(auth_router, prefix="/auth", tags=["Auth"])
app.include_router(
    institutions_router,
    prefix="/instituicao",
    tags=["Institutions"],
    dependencies=[Depends(require_api_key)],
)
app.include_router(
    api_keys_router,
    prefix="/api-keys",
    tags=["API Keys"],
    dependencies=[Depends(require_api_key)],
)
app.include_router(billing_router, prefix="/billing", tags=["Billing"])
app.include_router(api_v1_router, prefix="/v1", tags=["API Publica"])
app.include_router(
    search_router,
    prefix="/search",
    tags=["Search"],
    dependencies=[Depends(require_api_key)],
)


@app.on_event("startup")
def startup() -> None:
    import logging

    log = logging.getLogger(__name__)
    init_db()
    if os.getenv("VERIFIER_PRELOAD_SEMANTIC", "").lower() in {"1", "true", "yes"}:
        try:
            from search.semantic_search import _get_model

            _get_model()
            log.info("[startup] embedding model loaded")
        except Exception as e:
            log.warning("[startup] model load error (non-fatal): %s", e)


@app.get("/", dependencies=[Depends(require_api_key)])
def root() -> dict[str, str]:
    return {"app": "Vera.fidei", "status": "ok"}
