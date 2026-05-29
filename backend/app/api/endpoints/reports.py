from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from app.schemas.report import LiveReportRequest
from app.services.report_service import report_service
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/live")
async def generate_live_report(request: LiveReportRequest):
    """
    Generates a 1-page PDF report for a live flood analysis run.
    """
    try:
        pdf_buffer = await report_service.generate_live_report_pdf(request.request_id)
        
        if not pdf_buffer:
            raise HTTPException(
                status_code=404, 
                detail=f"Flood analysis result with ID {request.request_id} not found."
            )

        return StreamingResponse(
            pdf_buffer,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename=flood_report_{request.request_id}.pdf"
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating report: {e}")
        raise HTTPException(status_code=500, detail="An error occurred while generating the report.")
