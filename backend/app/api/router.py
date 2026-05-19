from fastapi import APIRouter
from app.api.endpoints import auth, case_studies, gee

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(case_studies.router, prefix="/case-studies", tags=["case-studies"])
api_router.include_router(gee.router, prefix="/gee", tags=["gee"])
