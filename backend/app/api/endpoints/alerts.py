from fastapi import APIRouter, BackgroundTasks, Depends
from typing import Dict, Any
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/scan")
async def trigger_system_scan(background_tasks: BackgroundTasks) -> Dict[str, Any]:
    """
    Trigger a manual system scan for the automated flood alert system.
    This runs the pipeline across defined tiles and sends notifications.
    """
    from app.services.alert_service import alert_service
    
    # We run the actual heavy scanning in the background
    background_tasks.add_task(alert_service.run_full_scan)
    
    return {
        "status": "success",
        "message": "System scan initiated in the background."
    }
