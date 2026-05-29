from pydantic import BaseModel, Field

class LiveReportRequest(BaseModel):
    request_id: str = Field(..., description="The ID of the Live_Flood_Result record")
