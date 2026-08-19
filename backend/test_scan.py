import asyncio
from app.services.alert_service import alert_service
from app.core.config import settings

async def main():
    print(f"Vonage key: {settings.VONAGE_API_KEY}")
    await alert_service.run_full_scan()

asyncio.run(main())
