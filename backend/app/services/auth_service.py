from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from supabase import create_client, Client
from app.core.config import settings

# OAuth2 scheme for token extraction
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Initialize Supabase client
_supabase: Client = None

def get_supabase() -> Client:
    global _supabase
    if _supabase is None:
        if not settings.SUPABASE_URL or not settings.SUPABASE_KEY:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Supabase credentials are not configured in .env"
            )
        try:
            _supabase = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Supabase client could not be initialized: {str(e)}"
            )
    return _supabase

async def get_current_user(token: str = Depends(oauth2_scheme)):
    """
    Dependency to verify the Supabase JWT and return the user object.
    """
    supabase = get_supabase()
    try:
        # Verify the JWT with Supabase
        user_response = supabase.auth.get_user(token)
        if not user_response or not user_response.user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return user_response.user
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Could not validate credentials: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )

def check_admin_role(user: any):
    """
    Utility to check if a user has the 'admin' or 'agency_admin' role in their metadata.
    """
    user_metadata = user.user_metadata or {}
    role = user_metadata.get("role", "public")
    if role not in ["admin", "agency_admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The user does not have sufficient permissions",
        )
    return True
