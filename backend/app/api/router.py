from fastapi import APIRouter
from app.api.endpoints import auth, analyze, case_studies, gee, config, reports

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(analyze.router, prefix="/analyze", tags=["analyze"])
api_router.include_router(case_studies.router, prefix="/case-studies", tags=["case-studies"])
api_router.include_router(gee.router, prefix="/gee", tags=["gee"])
api_router.include_router(config.router, prefix="/config", tags=["config"])
api_router.include_router(reports.router, prefix="/reports", tags=["reports"])
