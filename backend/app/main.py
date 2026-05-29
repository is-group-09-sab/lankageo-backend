from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.router import api_router
from app.core.config import settings
from app.services.gee_service import gee_service

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
)

@app.on_event("startup")
async def startup_event():
    try:
        gee_service.initialize()
    except Exception as e:
        print(f"Warning: GEE initialization failed: {e}")
        print("The application will continue to run, but GEE features may not work.")

# Set all CORS enabled origins
# In production, you should restrict this to your frontend URL
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.API_V1_STR)

@app.get("/")
async def root():
    return {"message": "Welcome to Lanka Geo API"}
