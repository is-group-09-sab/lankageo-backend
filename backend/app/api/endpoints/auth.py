from fastapi import APIRouter, Depends
from app.services.auth_service import get_current_user

router = APIRouter()

@router.get("/me")
async def read_users_me(current_user: any = Depends(get_current_user)):
    """
    Returns the currently authenticated user's information.
    """
    user_metadata = getattr(current_user, "user_metadata", {}) or {}
    return {
        "id": current_user.id,
        "email": current_user.email,
        "role": user_metadata.get("role", "public")
    }

@router.get("/health")
async def health_check():
    """
    Simple health check endpoint.
    """
    return {"status": "healthy"}
