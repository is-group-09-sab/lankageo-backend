from fastapi import APIRouter, Depends, status
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

@router.post("/logout")
async def logout(current_user: any = Depends(get_current_user)):
    """
    Endpoint to handle any server-side logout logic.
    For Supabase, the main logout happens client-side, 
    but this can be used for logging or other cleanup.
    """
    return {"message": "Successfully logged out"}

@router.get("/health")
async def health_check():
    """
    Simple health check endpoint.
    """
    return {"status": "healthy"}
