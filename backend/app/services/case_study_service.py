from typing import List, Optional
from supabase import Client
from app.services.auth_service import get_supabase
from app.schemas.case_study import CaseStudyListItem, CaseStudyDetail

class CaseStudyService:
    def __init__(self):
        self.table = "case_studies"

    async def get_all_case_studies(self) -> List[CaseStudyListItem]:
        """
        Fetch a lightweight list of case studies for the listing page.
        """
        supabase: Client = get_supabase()
        response = supabase.table(self.table).select(
            "id, title, summary, image_url, date, location, category"
        ).execute()
        
        return [CaseStudyListItem(**item) for item in response.data]

    async def get_case_study_by_id(self, case_study_id: str) -> Optional[CaseStudyDetail]:
        """
        Fetch detailed data for a specific case study.
        """
        supabase: Client = get_supabase()
        response = supabase.table(self.table).select(
            "id, title, summary, image_url, date, location, category, content, images, analysis, stats"
        ).eq("id", case_study_id).execute()
        
        if not response.data:
            return None
            
        return CaseStudyDetail(**response.data[0])

case_study_service = CaseStudyService()
