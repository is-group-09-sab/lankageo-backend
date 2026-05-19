from fastapi import APIRouter
from app.api.endpoints import auth, analyze, case_studies

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(analyze.router, prefix="/analyze", tags=["analyze"])
api_router.include_router(case_studies.router, prefix="/case-studies", tags=["case-studies"])
