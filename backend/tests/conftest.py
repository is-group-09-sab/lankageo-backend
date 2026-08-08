"""
Pytest configuration and fixtures for Lanka Geo API tests.
Includes mocked GEE service, sample data, and test client setup.
"""

import pytest
import sys
import os
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Any

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi.testclient import TestClient
from app.main import app
from app.schemas.analyze import YearData, ZoneSeverityCount, TrendAnalysisResponse


# ==================== TEST CLIENT ====================
@pytest.fixture(scope="session")
def test_client():
    """FastAPI test client for making requests to endpoints."""
    from app.services.auth_service import get_current_user, get_supabase

    class MockUser:
        id = "test-user-123"
        email = "test@lankageo.com"
        user_metadata = {}

    async def mock_get_current_user_override():
        return MockUser()

    def mock_get_supabase_override():
        """Returns a mock Supabase client (no real DB calls)."""
        class MockSupabaseClient:
            def table(self, name):
                return self

            def select(self, *args, **kwargs):
                return self

            def eq(self, col, val):
                return self

            def order(self, col, **kwargs):
                return self

            def limit(self, n):
                return self

            def insert(self, data):
                return self

            def execute(self):
                class MockResponse:
                    data = [{"id": "mock-id-123", "request_id": "mock-req-123", "result_id": "mock-result-123"}]
                return MockResponse()

        return MockSupabaseClient()

    # Override FastAPI dependencies
    client = TestClient(app)
    client.app.dependency_overrides[get_current_user] = mock_get_current_user_override
    client.app.dependency_overrides[get_supabase] = mock_get_supabase_override

    return client


# ==================== SAMPLE DATA FIXTURES ====================
@pytest.fixture
def sample_live_roi():
    """Sample ROI for live flood analysis (Colombo region, Sri Lanka)."""
    return {
        "lat": 6.927,
        "lng": 80.773,
        "radius_km": 5
    }


@pytest.fixture
def sample_historical_roi():
    """Sample ROI for historical trend analysis (Colombo region, Sri Lanka)."""
    return {
        "lat": 6.927,
        "lng": 80.773,
        "radius_km": 10,
        "years": 5
    }


# ==================== MOCK GEE SERVICE ====================
@pytest.fixture(autouse=True)
def mock_gee_service(monkeypatch):
    """
    Monkeypatch GEE service to return realistic mock data without requiring
    real GEE credentials or network calls.
    """

    # Mock live flood analysis response
    def mock_run_live_analysis(lat: float, lon: float, radius_km: float, override_date: str = None):
        """Returns realistic mock live flood detection data."""
        return {
            "tile_url": f"https://earthengine.googleapis.com/v1/projects/lankageo/maps/live-flood-{lat}-{lon}/tiles/{{z}}/{{x}}/{{y}}",
            "geojson": {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "geometry": {
                            "type": "Polygon",
                            "coordinates": [[
                                [80.768, 6.922],
                                [80.778, 6.922],
                                [80.778, 6.932],
                                [80.768, 6.932],
                                [80.768, 6.922]
                            ]]
                        },
                        "properties": {
                            "severity_level": 3,
                            "area_km2": 2.5,
                            "water_type": "new_flood"
                        }
                    },
                    {
                        "type": "Feature",
                        "geometry": {
                            "type": "Polygon",
                            "coordinates": [[
                                [80.760, 6.915],
                                [80.765, 6.915],
                                [80.765, 6.920],
                                [80.760, 6.920],
                                [80.760, 6.915]
                            ]]
                        },
                        "properties": {
                            "severity_level": 2,
                            "area_km2": 1.2,
                            "water_type": "seasonal_water"
                        }
                    }
                ]
            },
            "affected_area_km2": 3.7,
            "confidence_score": 87.5,
            "satellite_source": "Sentinel-1/2 Ensemble (RF)",
            "cloud_cover_pct": 5.0,
            "risk_level": "Critical",
            "gee_asset_id": "projects/lankageo/assets/live-flood-20260612",
            "estimated_population": 250,
            "buildings_exposed": 18,
            "road_length_km": 3.5,
            "cropland_area_km2": 1.1
        }

    # Mock historical analysis response
    async def mock_run_historical_analysis(lat: float, lng: float, radius_km: float, years: int = 5):
        """Returns realistic mock historical trend data."""
        current_year = 2026
        years_list = list(range(current_year - years, current_year))

        years_data = [
            YearData(year=2021, value=15.0, details={"water_pixels": 1250}),
            YearData(year=2022, value=28.5, details={"water_pixels": 2140}),
            YearData(year=2023, value=18.3, details={"water_pixels": 1380}),
            YearData(year=2024, value=42.0, details={"water_pixels": 3150}),
            YearData(year=2025, value=22.5, details={"water_pixels": 1690}),
        ]

        return TrendAnalysisResponse(
            years_data=years_data,
            composite_tile_url=f"https://earthengine.googleapis.com/v1/projects/lankageo/maps/historical-composite-{lat}-{lng}/tiles/{{z}}/{{x}}/{{y}}",
            avg_flood_probability=25.26,
            peak_year=2024,
            min_year=2021,
            trend_heatmap_url=f"https://earthengine.googleapis.com/v1/projects/lankageo/maps/historical-heatmap-{lat}-{lng}/tiles/{{z}}/{{x}}/{{y}}",
            zone_count_by_severity=[
                ZoneSeverityCount(severity="High", count=12),
                ZoneSeverityCount(severity="Medium", count=28),
                ZoneSeverityCount(severity="Low", count=45),
            ]
        )

    # Patch the gee_service methods
    from app.services import gee_service
    monkeypatch.setattr(gee_service.gee_service, "run_live_analysis", mock_run_live_analysis)
    monkeypatch.setattr(gee_service.gee_service, "run_historical_analysis", mock_run_historical_analysis)


# ==================== AUTH MOCK ====================
@pytest.fixture(autouse=True)
def mock_auth(monkeypatch):
    """
    Monkeypatch authentication to bypass Supabase auth checks.
    Returns a mock user object for all requests.
    """
    class MockUser:
        id = "test-user-123"
        email = "test@lankageo.com"
        user_metadata = {}

    from app.services import auth_service

    async def mock_get_current_user_async(token: str = None):
        return MockUser()

    def mock_get_current_user_sync():
        return MockUser()

    def mock_get_supabase():
        """Returns a mock Supabase client (no real DB calls)."""
        class MockSupabaseClient:
            def table(self, name):
                return self

            def select(self, *args, **kwargs):
                return self

            def eq(self, col, val):
                return self

            def order(self, col, **kwargs):
                return self

            def limit(self, n):
                return self

            def insert(self, data):
                return self

            def execute(self):
                class MockResponse:
                    data = [{"id": "mock-id-123", "request_id": "mock-req-123", "result_id": "mock-result-123"}]
                return MockResponse()

        return MockSupabaseClient()

    # Patch both sync and async versions
    monkeypatch.setattr(auth_service, "get_current_user", mock_get_current_user_async)
    monkeypatch.setattr(auth_service, "get_supabase", mock_get_supabase)

    # Also override at dependency level by patching oauth2_scheme to not require token
    def mock_oauth2():
        return "mock-token"

    monkeypatch.setattr(auth_service, "oauth2_scheme", lambda: mock_oauth2())


# ==================== VALIDATION HELPERS ====================
@pytest.fixture
def validate_tile_url():
    """Helper to validate GEE tile URL format."""
    def _validate(url: str) -> bool:
        required_parts = [
            "earthengine.googleapis.com",
            "/v1/",
            "/maps/",
            "/tiles/",
            "{z}",
            "{x}",
            "{y}"
        ]
        return all(part in url for part in required_parts)
    return _validate


@pytest.fixture
def validate_geojson():
    """Helper to validate GeoJSON FeatureCollection structure."""
    def _validate(geojson: Dict[str, Any]) -> Dict[str, Any]:
        """Returns dict with validation results and any errors."""
        errors = []

        if geojson.get("type") != "FeatureCollection":
            errors.append("Missing or invalid 'type': should be 'FeatureCollection'")

        if not isinstance(geojson.get("features"), list):
            errors.append("Missing or invalid 'features': should be a list")

        if len(geojson.get("features", [])) == 0:
            errors.append("GeoJSON has no features")

        for idx, feature in enumerate(geojson.get("features", [])):
            if feature.get("type") != "Feature":
                errors.append(f"Feature {idx}: invalid type (should be 'Feature')")

            geometry = feature.get("geometry")
            if not geometry or geometry.get("type") != "Polygon":
                errors.append(f"Feature {idx}: missing or invalid geometry (should be Polygon)")

            props = feature.get("properties", {})
            if "severity_level" not in props:
                errors.append(f"Feature {idx}: missing 'severity_level' property")
            elif props["severity_level"] not in [1, 2, 3]:
                errors.append(f"Feature {idx}: severity_level must be 1, 2, or 3 (got {props['severity_level']})")

        return {
            "valid": len(errors) == 0,
            "errors": errors
        }
    return _validate


@pytest.fixture
def validate_risk_levels():
    """Helper to validate risk level values and colorization mapping."""
    def _validate(risk_level: str) -> Dict[str, Any]:
        """Maps risk level to color palette (as frontend would)."""
        color_map = {
            "Low": "#0000FF",          # Blue
            "Moderate": "#FFA500",     # Amber/Orange
            "Critical": "#FF0000"      # Red
        }

        if risk_level not in color_map:
            return {
                "valid": False,
                "error": f"Unknown risk level: {risk_level}. Must be one of {list(color_map.keys())}",
                "color": None
            }

        return {
            "valid": True,
            "risk_level": risk_level,
            "color": color_map[risk_level],
            "palette_index": list(color_map.keys()).index(risk_level)
        }
    return _validate


@pytest.fixture
def validate_historical_data():
    """Helper to validate historical analysis response structure."""
    def _validate(response_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validates all required fields for historical response."""
        errors = []

        required_fields = [
            "years_data",
            "composite_tile_url",
            "avg_flood_probability",
            "peak_year",
            "min_year",
            "trend_heatmap_url",
            "zone_count_by_severity"
        ]

        for field in required_fields:
            if field not in response_data:
                errors.append(f"Missing required field: {field}")

        # Validate years_data
        years_data = response_data.get("years_data", [])
        if not isinstance(years_data, list):
            errors.append("years_data must be a list")
        elif len(years_data) == 0:
            errors.append("years_data cannot be empty")

        for idx, year_entry in enumerate(years_data):
            if "year" not in year_entry or "value" not in year_entry:
                errors.append(f"years_data[{idx}]: missing 'year' or 'value' field")
            if not isinstance(year_entry.get("value"), (int, float)):
                errors.append(f"years_data[{idx}]: 'value' must be numeric")
            if year_entry.get("value") < 0 or year_entry.get("value") > 100:
                errors.append(f"years_data[{idx}]: 'value' must be between 0-100 (got {year_entry['value']})")

        # Validate severity zones
        zones = response_data.get("zone_count_by_severity", [])
        valid_severities = ["Low", "Medium", "High"]
        for zone in zones:
            if zone.get("severity") not in valid_severities:
                errors.append(f"Invalid severity: {zone.get('severity')}. Must be one of {valid_severities}")

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "data": response_data if len(errors) == 0 else None
        }
    return _validate
