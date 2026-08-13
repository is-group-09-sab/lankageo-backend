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

    # GEE behavior and thresholds (configurable)
    # Number of years to consider for historical aggregation
    GEE_HISTORICAL_YEARS: int = 5
    # Historical classification thresholds (percent occurrence)
    GEE_HIST_LOW_THRESH: int = 10      # >0 and <=10 => Low
    GEE_HIST_MODERATE_THRESH: int = 40 # >10 and <=40 => Moderate
    # JRC occurrence threshold (percent) below which a current detection is considered anomalous
    GEE_JRC_OCCURRENCE_THRESHOLD: int = 20
    # If seasonal water exists, allow detection to exceed seasonal footprint by this fraction (percent)
    GEE_SEASONAL_EXCEED_PERCENT: int = 20
    # Toggle using seasonal exceedance logic when deciding anomalies
    GEE_USE_SEASONAL_EXCEED: bool = True

    # Google Maps Platform Settings
    GOOGLE_MAPS_JS_API_KEY: Optional[str] = None
    GOOGLE_PLACES_API_KEY: Optional[str] = None
    GOOGLE_MAPS_STATIC_API_KEY: Optional[str] = None
    
    # Vonage SMS Settings
    VONAGE_API_KEY: Optional[str] = None
    VONAGE_API_SECRET: Optional[str] = None
    VONAGE_BRAND_NAME: Optional[str] = "LankaGeo"
    
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True)

settings = Settings()
