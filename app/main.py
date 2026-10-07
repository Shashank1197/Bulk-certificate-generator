from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from app.config import settings
from app.database import init_db
from app.routers import health, jobs, certificates


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifecycle management.
    Initializes database schema and storage directories on startup.
    """
    init_db()
    settings.STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    yield


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description=settings.DESCRIPTION,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# Enable CORS for frontend clients / dashboards
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(health.router, prefix=settings.API_V1_STR)
app.include_router(jobs.router, prefix=settings.API_V1_STR)
app.include_router(certificates.router, prefix=settings.API_V1_STR)

# Alias endpoint for POST /api/v1/certificates/generate as specified in problem statement
@app.post(
    f"{settings.API_V1_STR}/certificates/generate",
    tags=["Certificates"],
    summary="Submit Bulk Certificate Request (Alias for /jobs)",
    include_in_schema=True,
    response_model=jobs.JobCreateResponse,
    status_code=202,
)
def alias_submit_certificates(
    request: jobs.CertificateCreateRequest,
    background_tasks: jobs.BackgroundTasks,
    db=jobs.Depends(jobs.get_db),
):
    """Alias endpoint routing directly to the bulk generation job submission handler."""
    return jobs.submit_generation_job(request, background_tasks, db)


@app.get("/", include_in_schema=False)
def root():
    """Redirect root path to interactive Swagger documentation."""
    return RedirectResponse(url="/docs")
