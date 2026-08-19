from app.services.auth_service import get_supabase
supabase = get_supabase()
res = supabase.table("profiles").select("*").execute()
for r in res.data:
    print(r)
