from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Dict, Any

class CaseStudyBase(BaseModel):
    title: str
    category: str
    date: str  # Matches frontend "2024.Q1" style
    location: Optional[str] = None

class CaseStudyListItem(CaseStudyBase):
    id: str  # Frontend uses string IDs like "colombo-port-2024"
    summary: str
    image_url: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

class CaseStudyDetail(CaseStudyListItem):
    content: str
    images: List[str] = []
    analysis: Dict[str, Any] = {}
    stats: List[Dict[str, str]] = []

    model_config = ConfigDict(from_attributes=True)
