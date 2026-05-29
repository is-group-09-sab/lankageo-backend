import io
import httpx
from typing import Optional, Dict, Any
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle
from reportlab.lib.units import inch
from app.services.auth_service import get_supabase
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

class ReportService:
    @property
    def supabase(self):
        return get_supabase()

    async def get_report_data(self, request_id: str) -> Optional[Dict[str, Any]]:
        try:
            # Fetch Live_Flood_Result
            response = self.supabase.table("Live_Flood_Result") \
                .select("*") \
                .eq("id", request_id) \
                .execute()

            if not response.data:
                return None

            result = response.data[0]

            # Fetch all associated Flood_Polygon records
            polygon_response = self.supabase.table("Flood_Polygon") \
                .select("id, severity") \
                .eq("result_id", request_id) \
                .execute()
            
            polygons = polygon_response.data if polygon_response.data else []
            result["polygon_count"] = len(polygons)
            
            # Calculate severity breakdown
            severity_counts = {"High": 0, "Moderate": 0, "Low": 0}
            for p in polygons:
                sev = p.get("severity", "Moderate")
                if sev in severity_counts:
                    severity_counts[sev] += 1
                else:
                    severity_counts["Moderate"] += 1
            
            result["severity_breakdown"] = severity_counts
            
            return result
        except Exception as e:
            logger.error(f"Error fetching report data for {request_id}: {e}")
            return None

    async def _get_static_map(self, lat: float, lng: float) -> Optional[bytes]:
        if not settings.GOOGLE_MAPS_STATIC_API_KEY:
            logger.warning("GOOGLE_MAPS_STATIC_API_KEY not set, skipping map thumbnail")
            return None

        url = "https://maps.googleapis.com/maps/api/staticmap"
        params = {
            "center": f"{lat},{lng}",
            "zoom": 12,
            "size": "600x300",
            "maptype": "roadmap",
            "markers": f"color:red|{lat},{lng}",
            "key": settings.GOOGLE_MAPS_STATIC_API_KEY
        }

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, params=params)
                if response.status_code == 200:
                    return response.content
                else:
                    logger.error(f"Static Maps API error: {response.status_code}")
            except Exception as e:
                logger.error(f"Error fetching static map: {e}")
        
        return None

    async def generate_live_report_pdf(self, request_id: str) -> Optional[io.BytesIO]:
        data = await self.get_report_data(request_id)
        if not data:
            return None

        buffer = io.BytesIO()
        # Use tighter margins to ensure 1-page fit
        doc = SimpleDocTemplate(
            buffer, 
            pagesize=A4,
            rightMargin=30,
            leftMargin=30,
            topMargin=30,
            bottomMargin=30
        )

        styles = getSampleStyleSheet()
        
        # Professional Custom Styles
        title_style = ParagraphStyle(
            'TitleStyle',
            parent=styles['Heading1'],
            fontSize=22,
            spaceAfter=10,
            alignment=1, # Center
            textColor=colors.HexColor("#1A365D")
        )
        
        location_style = ParagraphStyle(
            'LocationStyle',
            parent=styles['Normal'],
            fontSize=11,
            alignment=1,
            spaceAfter=15,
            textColor=colors.grey
        )
        
        section_style = ParagraphStyle(
            'SectionStyle',
            parent=styles['Heading2'],
            fontSize=14,
            spaceBefore=10,
            spaceAfter=8,
            borderPadding=2,
            borderColor=colors.HexColor("#2E5B88"),
            borderWidth=0,
            borderLeftWidth=3,
            textColor=colors.HexColor("#2E5B88")
        )

        elements = []

        # Extract values with safe defaults
        lat = data.get('lat', 0.0)
        lng = data.get('lng', 0.0)
        timestamp = data.get('analysis_timestamp', 'Unknown')
        area = data.get('affected_area_km2', 0.0)
        confidence = data.get('confidence_score', 0.0)
        risk = data.get('risk_level', 'Unknown')
        source = data.get('satellite_source', 'Sentinel-1/2')
        poly_count = data.get('polygon_count', 0)
        
        pop = data.get('estimated_population', 0)
        buildings = data.get('buildings_exposed', 0)
        roads = data.get('road_length_km', 0.0)
        crops = data.get('cropland_area_km2', 0.0)

        # 1. Header Section
        elements.append(Paragraph("Lanka Geo: Live Flood Analysis Report", title_style))
        elements.append(Paragraph(f"Location: {lat:.4f}°N, {lng:.4f}°E | Timestamp: {timestamp}", location_style))

        # 2. Map Thumbnail (Main Visual)
        map_image_bytes = await self._get_static_map(lat, lng)
        if map_image_bytes:
            # Scale to fit nicely
            map_img = Image(io.BytesIO(map_image_bytes), width=6*inch, height=2.6*inch)
            elements.append(map_img)
            elements.append(Spacer(1, 15))
        else:
            # Placeholder box if map fails
            placeholder_data = [["[ Satellite Map View Unavailable ]"]]
            placeholder_table = Table(placeholder_data, colWidths=[6*inch], rowHeights=[1.5*inch])
            placeholder_table.setStyle(TableStyle([
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('GRID', (0, 0), (-1, -1), 1, colors.lightgrey),
                ('TEXTCOLOR', (0, 0), (-1, -1), colors.grey)
            ]))
            elements.append(placeholder_table)
            elements.append(Spacer(1, 10))

        # 3. Detection Metrics Section
        elements.append(Paragraph("Detection Metrics", section_style))
        
        # Include severity breakdown in metrics
        sev = data.get('severity_breakdown', {})
        sev_str = f"High: {sev.get('High', 0)}, Mod: {sev.get('Moderate', 0)}, Low: {sev.get('Low', 0)}"

        metrics_data = [
            ["Metric", "Value"],
            ["Affected Area", f"{area:.2f} km²"],
            ["Confidence Score", f"{confidence:.1%}"],
            ["Risk Level", risk.upper()],
            ["Satellite Source", source],
            ["Detected Polygons", f"{poly_count} ({sev_str})"]
        ]
        
        metrics_table = Table(metrics_data, colWidths=[2.5*inch, 3.5*inch])
        metrics_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#F7FAFC")),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor("#4A5568")),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE')
        ]))
        elements.append(metrics_table)

        # 4. Impact Assessment Section
        elements.append(Paragraph("Impact Assessment", section_style))
        impact_data = [
            ["Category", "Estimated Exposure"],
            ["Population Affected", f"{pop:,} people"],
            ["Buildings Affected", f"{buildings:,} units"],
            ["Roads Affected", f"{roads:.2f} km"],
            ["Cropland Affected", f"{crops:.2f} km²"]
        ]
        
        impact_table = Table(impact_data, colWidths=[2.5*inch, 3.5*inch])
        impact_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#EBF8FF")),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor("#2C5282")),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#BEE3F8")),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE')
        ]))
        elements.append(impact_table)

        # 5. Footer / Source Attributions
        elements.append(Spacer(1, 40))
        footer_style = ParagraphStyle(
            'FooterStyle',
            parent=styles['Normal'],
            fontSize=8,
            textColor=colors.grey,
            alignment=1,
            leading=10
        )
        footer_text = (
            "<b>Data Sources:</b> ESA Copernicus Sentinel-1/2 (via Google Earth Engine), OpenStreetMap Contributors, "
            "WorldPop. Impact metrics are estimations based on spatial intersection analysis.<br/>"
            "<b>Disclaimer:</b> This report is generated automatically for rapid assessment purposes and should "
            "be verified with ground truth data where possible."
        )
        elements.append(Paragraph(footer_text, footer_style))
        elements.append(Paragraph(f"Report ID: {request_id} | Generated by Lanka Geo Monitoring System", footer_style))

        # Build PDF
        try:
            doc.build(elements)
        except Exception as e:
            logger.error(f"Error building PDF for {request_id}: {e}")
            return None
            
        buffer.seek(0)
        return buffer

report_service = ReportService()
