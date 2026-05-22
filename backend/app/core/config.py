from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    # API Settings
    PROJECT_NAME: str = "Lanka Geo API"
    VERSION: str = "0.1.0"
    API_V1_STR: str = "/api/v1"
    
    # Supabase Settings
    SUPABASE_URL: str = ""
    SUPABASE_KEY: str = "" # Anon key for client side, service role for backend logic if needed
    
    # Google Earth Engine Settings
    GEE_SERVICE_ACCOUNT: Optional[str] = None
    GEE_PRIVATE_KEY: Optional[str] = None
    GEE_SERVICE_ACCOUNT_FILE: Optional[str] = None
    
    # GEE User Credential Fallback (for restricted accounts)
    GEE_CLIENT_ID: Optional[str] = None
    GEE_CLIENT_SECRET: Optional[str] = None
    GEE_REFRESH_TOKEN: Optional[str] = None
    
    GEE_PROJECT: Optional[str] = "lanka-geo"
    
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True)

settings = Settings()
