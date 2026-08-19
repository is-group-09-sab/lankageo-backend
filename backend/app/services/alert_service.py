import logging
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, List
from app.services.auth_service import get_supabase
from app.services.gee_service import gee_service
from app.services.flood_service import flood_service
from app.core.config import settings
import vonage

logger = logging.getLogger(__name__)

class AlertService:
    @property
    def supabase(self):
        return get_supabase()

    async def run_full_scan(self):
        """
        Executes the scheduled alert scan workflow.
        1. Checks for new imagery (skipped in mock).
        2. Queries tiles or points for analysis.
        3. Persists detection polygons.
        4. Matches against user profiles.
        5. Notifies verified users.
        """
        logger.info("Starting automated flood alert system scan.")
        scan_id = datetime.utcnow().isoformat()
        
        try:
            # 0. Initialize scan run record
            self._init_scan_record(scan_id)
            
            # 1. Fetch verified users' profiles
            profiles = self._get_verified_user_profiles()
            if not profiles:
                logger.info("No verified users to alert. Completing scan early.")
                self._update_scan_status(scan_id, "success")
                return

            # 2. Pipeline Execution: Run Live Analysis Module
            # In a full production system, we would iterate over a predefined grid of critical zones.
            # For this pipeline demonstration, we scan a known critical zone.
            critical_lat = 6.4450694
            critical_lng = 80.641192
            
            logger.info(f"Running live GEE analysis pipeline on zone: {critical_lat}, {critical_lng}")
            analysis_data = gee_service.run_live_analysis(critical_lat, critical_lng, radius_km=5.0)
            
            affected_area = analysis_data.get("affected_area_km2", 0)
            logger.info(f"Live analysis complete. Affected area detected: {affected_area} km²")
            
            # 3. Decision Gate: Is there a flood?
            if affected_area > 0:
                logger.info("Flood detected! Executing alert dispatch pipeline.")
                self._process_alerts(scan_id, profiles, critical_lat, critical_lng, affected_area)
            else:
                logger.info("No flooding detected in the critical zone. No alerts dispatched.")
            
            self._update_scan_status(scan_id, "success")
            logger.info(f"Scan {scan_id} completed successfully.")
            
        except Exception as e:
            logger.error(f"Error during scan {scan_id}: {e}")
            self._update_scan_status(scan_id, "failed")

    def trigger_alerts(self, lat: float, lng: float, affected_area: float):
        """
        Manually trigger alerts based on specific coordinates and affected area.
        Used when live map analysis detects flooding.
        """
        if affected_area <= 0:
            return
            
        logger.info(f"Triggering manual alerts for zone: {lat}, {lng} with area {affected_area} km²")
        scan_id = datetime.utcnow().isoformat() + "_manual"
        
        try:
            self._init_scan_record(scan_id)
            profiles = self._get_verified_user_profiles()
            
            if profiles:
                self._process_alerts(scan_id, profiles, lat, lng, affected_area)
                self._update_scan_status(scan_id, "success")
            else:
                logger.info("No verified users to alert for manual trigger.")
                self._update_scan_status(scan_id, "success")
        except Exception as e:
            logger.error(f"Error during manual alert trigger {scan_id}: {e}")
            self._update_scan_status(scan_id, "failed")

    def _init_scan_record(self, scan_id: str):
        try:
            payload = {
                "scan_id": scan_id,
                "started_at": datetime.utcnow().isoformat(),
                "status": "running"
            }
            # Suppress error if table missing (graceful degradation)
            self.supabase.table("scan_runs").insert(payload).execute()
        except Exception as e:
            logger.warning(f"Could not create scan_runs record: {e}")

    def _update_scan_status(self, scan_id: str, status: str):
        try:
            self.supabase.table("scan_runs").update({
                "status": status,
                "completed_at": datetime.utcnow().isoformat()
            }).eq("scan_id", scan_id).execute()
        except Exception as e:
            logger.warning(f"Could not update scan_runs record: {e}")

    def _get_verified_user_profiles(self) -> List[Dict[str, Any]]:
        try:
            res = self.supabase.table("profiles").select("*").execute()
            # In a real app we filter by `is_verified` or similar
            return res.data if res.data else []
        except Exception as e:
            logger.warning(f"Could not fetch profiles: {e}")
            return []

    def _process_alerts(self, scan_id: str, profiles: List[Dict], detected_lat: float, detected_lng: float, affected_area: float):
        logger.info(f"Processing alerts for {len(profiles)} profiles...")
        for profile in profiles:
            user_id = profile.get("id")
            phone = profile.get("phone_number")
            user_lat = profile.get("latitude")
            user_lng = profile.get("longitude")
            
            # For this test scenario, we check if the user is within ~50km (approx 0.5 degrees) for easier testing
            is_in_flood_zone = False
            if user_lat and user_lng:
                try:
                    dist = ((float(user_lat) - detected_lat)**2 + (float(user_lng) - detected_lng)**2)**0.5
                    logger.info(f"Checking user {user_id} (Lat: {user_lat}, Lng: {user_lng}). Distance to flood: {dist:.4f} degrees.")
                    if dist < 0.5: # Increased from 0.05 to 0.5 (50km) for testing
                        is_in_flood_zone = True
                        logger.info(f"User {user_id} is within the 50km alert radius.")
                    else:
                        logger.info(f"User {user_id} is outside the 50km alert radius. Skipping SMS.")
                except (ValueError, TypeError):
                    logger.warning(f"Invalid coordinates for user {user_id}. Skipping distance check.")
            else:
                # Fallback for test scenario if lat/lng are missing in DB
                is_in_flood_zone = True
                logger.info(f"User {user_id} has no coordinates. Assuming in flood zone for testing.")

            if is_in_flood_zone:
                if phone:
                    # Format phone number to E.164 format for Sri Lanka if necessary
                    formatted_phone = phone.strip().replace(" ", "")
                    if formatted_phone.startswith("0"):
                        formatted_phone = "+94" + formatted_phone[1:]
                    elif not formatted_phone.startswith("+"):
                        formatted_phone = "+94" + formatted_phone
                    
                    msg = f"Critical Flood Alert: Severe inundation ({affected_area} km²) detected near {detected_lat:.4f}, {detected_lng:.4f}."
                    logger.info(f"Dispatching SMS to {formatted_phone}...")
                    self._send_sms(formatted_phone, msg)
                    self._log_notification(scan_id, user_id, "sms", "sent")
                else:
                    logger.info(f"User {user_id} is in flood zone, but has no phone number on file. SMS skipped.")

    def _send_sms(self, phone: str, message: str):
        if settings.VONAGE_API_KEY and settings.VONAGE_API_SECRET:
            try:
                try:
                    # Attempt older Vonage SDK (v3.x)
                    client = vonage.Client(key=settings.VONAGE_API_KEY, secret=settings.VONAGE_API_SECRET)
                    sms = vonage.Sms(client)
                    response = sms.send_message({
                        "from": settings.VONAGE_BRAND_NAME or "LankaGeo",
                        "to": phone,
                        "text": message,
                    })
                    if response["messages"][0]["status"] == "0":
                        logger.info(f"SMS sent to {phone} via Vonage (v3).")
                    else:
                        logger.error(f"Failed to send Vonage SMS to {phone}: {response['messages'][0]['error-text']}")
                except AttributeError:
                    # Attempt newer Vonage SDK (v4.x+)
                    from vonage import Vonage, Auth
                    from vonage_sms import SmsMessage, SmsResponse
                    client = Vonage(Auth(api_key=settings.VONAGE_API_KEY, api_secret=settings.VONAGE_API_SECRET))
                    
                    message_obj = SmsMessage(
                        to=phone,
                        from_=settings.VONAGE_BRAND_NAME or "LankaGeo",
                        text=message
                    )
                    response: SmsResponse = client.sms.send(message_obj)
                    logger.info(f"SMS sent to {phone} via Vonage (v4).")
                    
            except Exception as e:
                logger.error(f"Failed to send Vonage SMS to {phone} (Exception): {e}")
        else:
            logger.info(f"[MOCK SMS] To: {phone} - Message: {message} (Vonage not configured)")

    def _log_notification(self, scan_id: str, user_id: str, channel: str, status: str):
        try:
            payload = {
                "scan_id": scan_id,
                "user_id": user_id,
                "channel": channel,
                "status": status,
                "sent_at": datetime.utcnow().isoformat()
            }
            self.supabase.table("notification_log").insert(payload).execute()
        except Exception as e:
            logger.warning(f"Could not log notification: {e}")

alert_service = AlertService()
