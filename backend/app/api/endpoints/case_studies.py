from fastapi import APIRouter, HTTPException, status, Path
from typing import List
from app.schemas.case_study import CaseStudyListItem, CaseStudyDetail
from app.services.case_study_service import case_study_service

router = APIRouter()

@router.get("/", response_model=List[CaseStudyListItem])
async def list_case_studies():
    """
    Retrieve a lightweight list of case studies for the listing page.
    """
    try:
        return await case_study_service.get_all_case_studies()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching case studies: {str(e)}"
        )

@router.get("/{id}", response_model=List[CaseStudyDetail])
async def get_case_study(
    id: str = Path(..., description="The unique identifier of the case study (e.g., 'colombo-port-2024')")
):
    """
    Fetch detailed data for a specific case study.
    Returns as a list containing a single item to match frontend expectations.
    """
    try:
        case_study = await case_study_service.get_case_study_by_id(id)
        if not case_study:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Case study with ID {id} not found"
            )
        return [case_study]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching case study: {str(e)}"
        )
