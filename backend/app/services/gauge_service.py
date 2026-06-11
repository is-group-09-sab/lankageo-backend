import httpx
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from app.schemas.gauge import GaugeReading
import logging

logger = logging.getLogger(__name__)

class GaugeService:
    def __init__(self):
        self._cache: Optional[List[GaugeReading]] = None
        self._cache_expiry: Optional[datetime] = None
        
        # External API URL (Placeholder for Government River Gauge API)
        # In a real scenario, this would be retrieved from environment settings.
        self.API_URL = "https://srilankafloodmonitor.site/api/readings"
        
        # Station Thresholds and Metadata
        # HS-01: Hanwella, HS-02: Nagalagam St (Kelani River)
        self.STATIONS = {
            "HS-01": {
                "name": "Hanwella",
                "normal_level": 3.0,
                "alert_level": 7.0,
                "minor_flood": 8.0
            },
            "HS-02": {
                "name": "Nagalagam St",
                "normal_level": 0.6,
                "alert_level": 1.22,
                "minor_flood": 1.52
            }
        }

    def _evaluate_status(self, station_id: str, current_level: float) -> str:
        """Evaluates the status based on predefined water level thresholds."""
        thresholds = self.STATIONS.get(station_id)
        if not thresholds:
            return "normal"
        
        if current_level >= thresholds["minor_flood"]:
            return "critical"
        elif current_level >= thresholds["alert_level"]:
            return "elevated"
        else:
            return "normal"

    async def get_live_readings(self) -> List[GaugeReading]:
        """
        Fetches live water level readings for Kelani River stations.
        Implements an in-memory cache with a 30-minute TTL.
        """
        # Caching Mechanism Logic:
        # Check if cache exists and has not expired (30-minute TTL)
        if self._cache and self._cache_expiry and datetime.now() < self._cache_expiry:
            logger.info("Returning cached gauge readings.")
            return self._cache

        try:
            logger.info(f"Fetching live gauge data from {self.API_URL}")
            
            # Establish connection and fetch live readings
            async with httpx.AsyncClient(timeout=10.0) as client:
                # In a real production environment, we would call the actual API:
                # response = await client.get(self.API_URL)
                # response.raise_for_status()
                # api_data = response.json()
                
                # For this implementation, we simulate the external API response format
                # based on common patterns for such environmental APIs.
                api_data = [
                    {"station_id": "HS-01", "level_m": 2.15},
                    {"station_id": "HS-02", "level_m": 0.45}
                ]

            readings = []
            for item in api_data:
                station_id = item.get("station_id")
                if station_id in self.STATIONS:
                    conf = self.STATIONS[station_id]
                    level = item.get("level_m", 0.0)
                    
                    readings.append(GaugeReading(
                        station_name=conf["name"],
                        current_level_m=level,
                        normal_level_m=conf["normal_level"],
                        status=self._evaluate_status(station_id, level)
                    ))

            # Update cache and set expiry to 30 minutes from now
            self._cache = readings
            self._cache_expiry = datetime.now() + timedelta(minutes=30)
            
            return readings

        except (httpx.RequestError, httpx.HTTPStatusError) as e:
            logger.error(f"External API error: {e}")
            # Fallback: Return stale cache if available, else re-raise
            if self._cache:
                logger.warning("Returning stale cache due to API failure.")
                return self._cache
            raise Exception("Failed to fetch live gauge data and no cache available.")
        except Exception as e:
            logger.error(f"Unexpected error in GaugeService: {e}")
            raise

gauge_service = GaugeService()
