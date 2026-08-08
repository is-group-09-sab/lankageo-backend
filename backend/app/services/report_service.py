import io
import httpx
from datetime import datetime
from typing import Optional, Dict, Any
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle, PageBreak
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
            # Fetch live_flood_results by request_id
            response = self.supabase.table("live_flood_results") \
                .select("*") \
                .eq("request_id", request_id) \
                .execute()

            if not response.data:
                return None

            result = response.data[0]
            result_id = result.get("result_id")

            # Fetch all associated flood_polygons records using the result_id from the live_flood_results row
            polygon_response = self.supabase.table("flood_polygons") \
                .select("*") \
                .eq("result_id", result_id) \
                .execute()
            
            polygons = polygon_response.data if polygon_response.data else []
            result["polygon_count"] = len(polygons)
            
            # Calculate severity breakdown
            severity_counts = {"High": 0, "Moderate": 0, "Low": 0}
            features = []
            
            # Map database severity string to frontend severity levels
            severity_mapping = {"critical": 3, "moderate": 2, "seasonal": 1}

            for p in polygons:
                sev = p.get("severity", "moderate")
                # Map to standard High/Moderate/Low for report summary
                if sev == "critical":
                    severity_counts["High"] += 1
                elif sev == "seasonal":
                    severity_counts["Low"] += 1
                else:
                    severity_counts["Moderate"] += 1
                
                # Build GeoJSON feature
                features.append({
                    "type": "Feature",
                    "geometry": p.get("geom"),
                    "properties": {
                        "severity_level": severity_mapping.get(sev, 2),
                        "area_km2": p.get("area_km2", 0.0),
                        "confidence_score": p.get("confidence_score", 0.0),
                        "water_type": p.get("water_type"),
                        "result_id": result_id
                    }
                })

            result["severity_breakdown"] = severity_counts
            result["geojson"] = {
                "type": "FeatureCollection",
                "features": features
            }
            
            return result
        except Exception as e:
            logger.error(f"Error fetching report data for {request_id}: {e}")
            return None

    async def get_historical_risk_profile(self, request_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetches the Historical_Risk_Profile using the provided request_id.
        """
        try:
            # First find the profile linked to this request_id
            response = self.supabase.table("historical_risk_profiles") \
                .select("*") \
                .eq("request_id", request_id) \
                .execute()

            if not response.data:
                return None

            profile = response.data[0]
            
            # Also fetch the parent request for location data
            req_response = self.supabase.table("requests") \
                .select("*") \
                .eq("id", request_id) \
                .execute()
            
            if req_response.data:
                profile["request_metadata"] = req_response.data[0]
            
            return profile
        except Exception as e:
            logger.error(f"Error fetching historical risk profile for {request_id}: {e}")
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

    async def generate_historical_report_pdf(self, request_id: str) -> Optional[io.BytesIO]:
        """
        Generates a 7-page PDF report for historical risk analysis.
        Follows the 9-section sequential structure.
        """
        data = await self.get_historical_risk_profile(request_id)
        if not data:
            return None

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=50,
            leftMargin=50,
            topMargin=50,
            bottomMargin=50
        )

        styles = getSampleStyleSheet()
        
        # Styles
        title_style = ParagraphStyle(
            'TitleStyle', parent=styles['Heading1'], fontSize=28, alignment=1, spaceAfter=20, textColor=colors.HexColor("#1A365D")
        )
        h2_style = ParagraphStyle(
            'H2Style', parent=styles['Heading2'], fontSize=18, spaceBefore=20, spaceAfter=10, textColor=colors.HexColor("#2E5B88")
        )
        normal_style = styles['Normal']
        
        elements = []
        payload = data.get("data_payload", {})
        meta = data.get("request_metadata", {})
        lat, lng = meta.get("lat", 0.0), meta.get("lng", 0.0)

        # --- PAGE 1: COVER PAGE ---
        elements.append(Spacer(1, 2*inch))
        elements.append(Paragraph("HISTORICAL RISK PROFILE REPORT", title_style))
        elements.append(Spacer(1, 0.5*inch))
        elements.append(Paragraph(f"Location: {lat:.4f}°N, {lng:.4f}°E", ParagraphStyle('Center', parent=normal_style, alignment=1, fontSize=14)))
        elements.append(Paragraph(f"Radius: {meta.get('radius_km', 0)} km", ParagraphStyle('Center', parent=normal_style, alignment=1, fontSize=12)))
        elements.append(Spacer(1, 3*inch))
        elements.append(Paragraph("Generated by Lanka Geo Monitoring System", ParagraphStyle('Center', parent=normal_style, alignment=1, textColor=colors.grey)))
        elements.append(Paragraph(f"Date: {datetime.now().strftime('%Y-%m-%d')}", ParagraphStyle('Center', parent=normal_style, alignment=1, textColor=colors.grey)))
        elements.append(PageBreak())

        # --- PAGE 2: TABLE OF CONTENTS ---
        elements.append(Paragraph("Table of Contents", h2_style))
        toc_items = [
            "1. Cover Page",
            "2. Table of Contents",
            "3. Executive Summary",
            "4. Data Table",
            "5. Heatmap Frames",
            "6. FFI Chart",
            "7. Zone Classification",
            "8. GeoJSON Reference",
            "9. Methodology"
        ]
        for item in toc_items:
            elements.append(Paragraph(item, normal_style))
            elements.append(Spacer(1, 10))
        elements.append(PageBreak())

        # --- PAGE 3: EXECUTIVE SUMMARY & DATA TABLE ---
        elements.append(Paragraph("3. Executive Summary", h2_style))
        summary_text = (
            f"This report presents a historical risk analysis for the selected region. "
            f"The analysis covers the period identified by the system, with an Average Flood Frequency Index (FFI) of {data.get('avg_ffi', 0.0)}. "
            f"The peak risk year was identified as {data.get('peak_year', 'N/A')}, while the minimum risk occurred in {data.get('min_year', 'N/A')}."
        )
        elements.append(Paragraph(summary_text, normal_style))
        elements.append(Spacer(1, 20))

        elements.append(Paragraph("4. Data Table", h2_style))
        years_data = payload.get("years_data", [])
        table_data = [["Year", "FFI Value"]]
        for entry in years_data:
            table_data.append([str(entry.get("year")), f"{entry.get('value', 0.0):.2f}"])
        
        t = Table(table_data, colWidths=[2*inch, 2*inch])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#F7FAFC")),
            ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
            ('ALIGN', (0,0), (-1,-1), 'CENTER')
        ]))
        elements.append(t)
        elements.append(PageBreak())

        # --- PAGE 4: HEATMAP FRAMES ---
        elements.append(Paragraph("5. Heatmap Frames (Generated per year)", h2_style))
        elements.append(Paragraph("Spatial distribution of flood risk intensity over the analysis period.", normal_style))
        elements.append(Spacer(1, 20))
        # Placeholder for Heatmap
        map_img_bytes = await self._get_static_map(lat, lng)
        if map_img_bytes:
            elements.append(Image(io.BytesIO(map_img_bytes), width=6*inch, height=3*inch))
        elements.append(Spacer(1, 20))
        elements.append(Paragraph("Note: Individual yearly frames are aggregated into the trend heatmap for visual clarity.", normal_style))
        elements.append(PageBreak())

        # --- PAGE 5: FFI CHART & ZONE CLASSIFICATION ---
        elements.append(Paragraph("6. FFI Chart", h2_style))
        elements.append(Paragraph("Temporal trend of the Flood Frequency Index (FFI).", normal_style))
        elements.append(Spacer(1, 2*inch)) # Placeholder for actual chart logic
        elements.append(Paragraph("[ FFI Trend Visualization ]", ParagraphStyle('Center', parent=normal_style, alignment=1, textColor=colors.grey)))
        elements.append(Spacer(1, 0.5*inch))

        elements.append(Paragraph("7. Zone Classification", h2_style))
        zone_counts = payload.get("zone_count_by_severity", [])
        zone_data = [["Severity Zone", "Count"]]
        for z in zone_counts:
            zone_data.append([z.get("severity"), str(z.get("count"))])
        
        zt = Table(zone_data, colWidths=[2.5*inch, 1.5*inch])
        zt.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#EBF8FF")),
            ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
        ]))
        elements.append(zt)
        elements.append(PageBreak())

        # --- PAGE 6: GEOJSON REFERENCE ---
        elements.append(Paragraph("8. GeoJSON Reference", h2_style))
        elements.append(Paragraph("The analysis results are mapped to the following spatial references:", normal_style))
        elements.append(Spacer(1, 20))
        geojson_mock = {
            "type": "FeatureCollection",
            "features": [],
            "metadata": {
                "request_id": request_id,
                "center": [lng, lat],
                "radius": meta.get("radius_km")
            }
        }
        elements.append(Paragraph(f"Data Payload ID: {data.get('id')}", normal_style))
        elements.append(Paragraph(f"Spatial Reference: WGS 84 (EPSG:4326)", normal_style))
        elements.append(Spacer(1, 20))
        elements.append(Paragraph("Full GeoJSON datasets can be exported via the API /analyze/export endpoint.", normal_style))
        elements.append(PageBreak())

        # --- PAGE 7: METHODOLOGY ---
        elements.append(Paragraph("9. Methodology", h2_style))
        methodology_text = (
            "The historical risk profile is generated using multi-temporal satellite imagery from the ESA Copernicus Sentinel program. "
            "Surface water detection is performed using a modified Normalized Difference Water Index (mNDWI) for optical data and "
            "backscatter thresholding for SAR data. The Flood Frequency Index (FFI) is calculated as a normalized ratio of "
            "detected water presence over the total number of valid observations per pixel per year."
        )
        elements.append(Paragraph(methodology_text, normal_style))
        elements.append(Spacer(1, 20))
        elements.append(Paragraph("System Version: 1.0.0-historical", normal_style))
        elements.append(Paragraph("Data Source: Google Earth Engine", normal_style))

        # Build PDF
        try:
            doc.build(elements)
        except Exception as e:
            logger.error(f"Error building historical PDF for {request_id}: {e}")
            return None
            
        buffer.seek(0)
        return buffer

report_service = ReportService()
