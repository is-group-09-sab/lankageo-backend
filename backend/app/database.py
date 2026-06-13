from supabase import create_client, Client
from pydantic_settings import BaseSettings
import psycopg2
from psycopg2.extras import RealDictCursor


class Settings(BaseSettings):
    SUPABASE_URL: str
    SUPABASE_KEY: str          # anon key — for client-facing operations
    SUPABASE_SERVICE_KEY: str  # service_role key — bypasses RLS
    DATABASE_URL: str          # PostgreSQL connection string

    class Config:
        env_file = ".env"


settings = Settings()

# Supabase client — use for Auth and simple CRUD
supabase: Client = create_client(
    settings.SUPABASE_URL,
    settings.SUPABASE_SERVICE_KEY  # service role bypasses RLS for backend writes
)

# Direct PostgreSQL connection — use for PostGIS spatial queries
# psycopg2 supports ST_GeomFromGeoJSON and other PostGIS functions natively
def get_db_connection():
    conn = psycopg2.connect(
        settings.DATABASE_URL,
        cursor_factory=RealDictCursor
    )
    try:
        yield conn
    finally:
        conn.close()