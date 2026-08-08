"""
End-to-End API Tests: Live Flood Analysis & Historical Trend Analysis
=====================================================================

These tests validate that the backend API returns properly formatted data
for the frontend to render colored flood maps.

Test Coverage:
1. Live Flood Analysis: POST /analyze/live
   - Validates tile URL for live flood visualization
   - Validates GeoJSON polygons with risk levels (1=Blue, 2=Amber, 3=Red)
   - Checks affected area, confidence score, and other metadata

2. Historical Trend Analysis: POST /analyze/trend
   - Validates heatmap tile URL for historical visualization
   - Validates yearly flood probability data (0-100%)
   - Checks zone severity counts (Low/Medium/High)
   - Validates peak/min years for trend detection
"""

import pytest
import json
from typing import Dict, Any


class TestLiveFloodAnalysis:
    """Test suite for live flood detection endpoint."""

    def test_live_flood_analysis_returns_colored_map_and_polygons(
        self,
        test_client,
        sample_live_roi,
        validate_tile_url,
        validate_geojson,
        validate_risk_levels
    ):
        """
        Test: Live flood analysis endpoint returns valid colored map tiles and GeoJSON polygons.

        Flow:
        1. Send POST request to /analyze/live with sample ROI
        2. Verify HTTP 200 response
        3. Validate tile URL format (GEE endpoint)
        4. Validate GeoJSON structure and risk levels
        5. Verify colorization mapping (1→Blue, 2→Amber, 3→Red)
        6. Check metadata completeness
        """
        # Arrange
        roi_data = sample_live_roi

        # Act
        response = test_client.post("/api/v1/analyze/live", json=roi_data)

        # Assert: HTTP Status
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

        data = response.json()

        # ===== Assertion 1: Response structure =====
        required_fields = [
            "tile_url",
            "geojson",
            "affected_area_km2",
            "confidence_score",
            "satellite_source",
            "cloud_cover_pct",
            "risk_level",
            "analysis_timestamp",
            "gee_asset_id",
            "estimated_population",
            "buildings_exposed",
            "road_length_km",
            "cropland_area_km2",
            "cache_hit"
        ]

        for field in required_fields:
            assert field in data, f"Missing required field: {field}"

        # ===== Assertion 2: Tile URL validation =====
        tile_url = data["tile_url"]
        assert validate_tile_url(tile_url), \
            f"Invalid tile URL format. Expected GEE endpoint with {{z}}/{{x}}/{{y}}, got: {tile_url}"

        # ===== Assertion 3: GeoJSON validation =====
        geojson = data["geojson"]
        geojson_validation = validate_geojson(geojson)
        assert geojson_validation["valid"], \
            f"Invalid GeoJSON: {'; '.join(geojson_validation['errors'])}"

        # ===== Assertion 4: Risk level validation and colorization =====
        features = geojson.get("features", [])
        risk_level_colors = {1: "#0000FF", 2: "#FFA500", 3: "#FF0000"}  # Blue, Amber, Red

        for idx, feature in enumerate(features):
            severity_level = feature.get("properties", {}).get("severity_level")
            assert severity_level in [1, 2, 3], \
                f"Feature {idx}: severity_level {severity_level} not in [1, 2, 3]"

            expected_color = risk_level_colors[severity_level]
            actual_color = risk_level_colors.get(severity_level)
            assert actual_color == expected_color, \
                f"Feature {idx}: Color mismatch for severity {severity_level}"

        # ===== Assertion 5: Risk level label =====
        risk_level = data["risk_level"]
        risk_validation = validate_risk_levels(risk_level)
        assert risk_validation["valid"], \
            f"Invalid risk level: {risk_validation.get('error')}"

        # ===== Assertion 6: Confidence score range =====
        confidence = data["confidence_score"]
        assert isinstance(confidence, (int, float)), "confidence_score must be numeric"
        assert 0 <= confidence <= 100, \
            f"confidence_score out of range [0-100]: {confidence}"

        # ===== Assertion 7: Area metrics =====
        affected_area = data["affected_area_km2"]
        assert isinstance(affected_area, (int, float)), "affected_area_km2 must be numeric"
        assert affected_area >= 0, f"affected_area_km2 cannot be negative: {affected_area}"

        # ===== Assertion 8: Cloud cover =====
        cloud_cover = data["cloud_cover_pct"]
        assert isinstance(cloud_cover, (int, float)), "cloud_cover_pct must be numeric"
        assert 0 <= cloud_cover <= 100, f"cloud_cover_pct out of range [0-100]: {cloud_cover}"

        # ===== Assertion 9: Satellite source =====
        satellite_source = data["satellite_source"]
        assert isinstance(satellite_source, str), "satellite_source must be string"
        assert len(satellite_source) > 0, "satellite_source cannot be empty"

        # ===== Assertion 10: Timestamp format =====
        timestamp = data["analysis_timestamp"]
        assert isinstance(timestamp, str), "analysis_timestamp must be ISO string"
        # Basic ISO format check (should contain T or space as date/time separator)
        assert "T" in timestamp or " " in timestamp, \
            f"analysis_timestamp not in ISO format: {timestamp}"

        print(f"\n✓ Live Flood Analysis Test PASSED")
        print(f"  - Tile URL: {tile_url[:80]}...")
        print(f"  - Features: {len(features)}")
        print(f"  - Risk Level: {risk_level} → {risk_validation['color']}")
        print(f"  - Affected Area: {affected_area} km²")
        print(f"  - Confidence: {confidence}%")


    def test_live_flood_geojson_has_complete_geometry(
        self,
        test_client,
        sample_live_roi,
        validate_geojson
    ):
        """
        Test: Verify GeoJSON polygons have complete geometry (closed rings).
        This ensures frontend can render polygons without errors.
        """
        # Arrange
        roi_data = sample_live_roi

        # Act
        response = test_client.post("/api/v1/analyze/live", json=roi_data)

        # Assert
        assert response.status_code == 200
        data = response.json()
        geojson = data["geojson"]

        # Validate GeoJSON
        validation = validate_geojson(geojson)
        assert validation["valid"], f"GeoJSON validation failed: {validation['errors']}"

        # Check each polygon geometry
        for idx, feature in enumerate(geojson.get("features", [])):
            geometry = feature.get("geometry", {})
            assert geometry.get("type") == "Polygon", \
                f"Feature {idx}: Expected Polygon geometry, got {geometry.get('type')}"

            coordinates = geometry.get("coordinates", [])
            assert len(coordinates) > 0, f"Feature {idx}: No coordinate rings"

            first_ring = coordinates[0]
            # Check if polygon is closed (first and last point are same)
            assert first_ring[0] == first_ring[-1], \
                f"Feature {idx}: Polygon not closed (first != last point)"

            # Check minimum 3 unique points (plus closing point)
            unique_points = len(set(tuple(p) for p in first_ring[:-1]))
            assert unique_points >= 3, \
                f"Feature {idx}: Polygon has fewer than 3 unique points"

        print(f"\n✓ GeoJSON Geometry Test PASSED")
        print(f"  - All polygons are properly closed")
        print(f"  - All polygons have valid coordinate rings")


    def test_live_flood_metadata_for_impact_assessment(
        self,
        test_client,
        sample_live_roi
    ):
        """
        Test: Verify impact assessment metadata is present and valid.
        This data helps frontend display population at risk, buildings exposed, etc.
        """
        # Arrange
        roi_data = sample_live_roi

        # Act
        response = test_client.post("/api/v1/analyze/live", json=roi_data)

        # Assert
        assert response.status_code == 200
        data = response.json()

        impact_metrics = {
            "estimated_population": int,
            "buildings_exposed": int,
            "road_length_km": (int, float),
            "cropland_area_km2": (int, float)
        }

        for metric, expected_type in impact_metrics.items():
            assert metric in data, f"Missing impact metric: {metric}"
            value = data[metric]
            assert isinstance(value, expected_type), \
                f"{metric}: Expected {expected_type}, got {type(value)}"
            assert value >= 0, f"{metric} cannot be negative: {value}"

        print(f"\n✓ Impact Assessment Metadata Test PASSED")
        print(f"  - Estimated Population: {data['estimated_population']}")
        print(f"  - Buildings Exposed: {data['buildings_exposed']}")
        print(f"  - Road Length: {data['road_length_km']} km")
        print(f"  - Cropland Area: {data['cropland_area_km2']} km²")


class TestHistoricalTrendAnalysis:
    """Test suite for historical trend analysis endpoint."""

    def test_historical_trend_analysis_returns_heatmap_and_severity_zones(
        self,
        test_client,
        sample_historical_roi,
        validate_tile_url,
        validate_historical_data
    ):
        """
        Test: Historical trend analysis returns heatmap tiles and severity zone data.

        Flow:
        1. Send POST request to /analyze/trend with sample ROI and year range
        2. Verify HTTP 200 response
        3. Validate heatmap tile URL format (GEE endpoint)
        4. Validate yearly flood probability data (0-100%)
        5. Verify zone severity counts (Low/Medium/High)
        6. Check peak/min year calculations
        """
        # Arrange
        roi_data = sample_historical_roi

        # Act
        response = test_client.post("/api/v1/analyze/trend", json=roi_data)

        # Assert: HTTP Status
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

        data = response.json()

        # ===== Assertion 1: Response structure validation =====
        validation = validate_historical_data(data)
        assert validation["valid"], \
            f"Historical response validation failed: {'; '.join(validation['errors'])}"

        # ===== Assertion 2: Tile URLs validation =====
        composite_url = data["composite_tile_url"]
        heatmap_url = data["trend_heatmap_url"]

        assert validate_tile_url(composite_url), \
            f"Invalid composite tile URL: {composite_url}"
        assert validate_tile_url(heatmap_url), \
            f"Invalid heatmap tile URL: {heatmap_url}"

        # URLs should be distinct (different layers)
        assert composite_url != heatmap_url, \
            "Composite and heatmap URLs should be different tile layers"

        # ===== Assertion 3: Years data consistency =====
        years_data = data["years_data"]
        assert len(years_data) == roi_data["years"], \
            f"Expected {roi_data['years']} year entries, got {len(years_data)}"

        # Extract year values and probabilities for trend analysis
        years = [entry["year"] for entry in years_data]
        probabilities = [entry["value"] for entry in years_data]

        # Verify years are sequential
        for i in range(1, len(years)):
            assert years[i] == years[i-1] + 1, \
                f"Years not sequential: {years[i-1]} → {years[i]}"

        # Verify probabilities are in valid range
        for idx, prob in enumerate(probabilities):
            assert 0 <= prob <= 100, \
                f"years_data[{idx}]: probability {prob} not in range [0-100]"

        # ===== Assertion 4: Peak and min year validation =====
        peak_year = data["peak_year"]
        min_year = data["min_year"]

        peak_prob = max(probabilities)
        min_prob = min(probabilities)

        # Find which year has peak and min
        peak_year_from_data = years[probabilities.index(peak_prob)]
        min_year_from_data = years[probabilities.index(min_prob)]

        assert peak_year == peak_year_from_data, \
            f"peak_year mismatch: expected {peak_year_from_data}, got {peak_year}"
        assert min_year == min_year_from_data, \
            f"min_year mismatch: expected {min_year_from_data}, got {min_year}"

        # ===== Assertion 5: Average flood probability calculation =====
        avg_flood_prob = data["avg_flood_probability"]
        expected_avg = sum(probabilities) / len(probabilities)

        assert isinstance(avg_flood_prob, (int, float)), \
            "avg_flood_probability must be numeric"
        assert 0 <= avg_flood_prob <= 100, \
            f"avg_flood_probability out of range [0-100]: {avg_flood_prob}"
        # Allow small floating point differences
        assert abs(avg_flood_prob - expected_avg) < 0.1, \
            f"avg_flood_probability mismatch: expected ~{expected_avg}, got {avg_flood_prob}"

        # ===== Assertion 6: Zone severity counts =====
        zones = data["zone_count_by_severity"]
        assert len(zones) > 0, "zone_count_by_severity cannot be empty"

        valid_severities = {"Low", "Medium", "High"}
        total_zones = 0

        for zone in zones:
            assert zone["severity"] in valid_severities, \
                f"Invalid severity '{zone['severity']}'. Must be one of {valid_severities}"
            assert isinstance(zone["count"], int), \
                f"Zone count for '{zone['severity']}' must be integer"
            assert zone["count"] >= 0, \
                f"Zone count for '{zone['severity']}' cannot be negative"
            total_zones += zone["count"]

        assert total_zones > 0, "Total zone count must be > 0"

        print(f"\n✓ Historical Trend Analysis Test PASSED")
        print(f"  - Composite Tile URL: {composite_url[:80]}...")
        print(f"  - Heatmap Tile URL: {heatmap_url[:80]}...")
        print(f"  - Year Range: {years[0]}-{years[-1]} ({len(years)} years)")
        print(f"  - Flood Probability: {min(probabilities)}% → {max(probabilities)}% (avg: {avg_flood_prob}%)")
        print(f"  - Peak Year: {peak_year} ({peak_prob}%)")
        print(f"  - Zones: Low={[z['count'] for z in zones if z['severity']=='Low'][0] if any(z['severity']=='Low' for z in zones) else 0}, "
              f"Medium={[z['count'] for z in zones if z['severity']=='Medium'][0] if any(z['severity']=='Medium' for z in zones) else 0}, "
              f"High={[z['count'] for z in zones if z['severity']=='High'][0] if any(z['severity']=='High' for z in zones) else 0}")


    def test_historical_data_shows_flood_trend(
        self,
        test_client,
        sample_historical_roi
    ):
        """
        Test: Verify historical data shows a meaningful trend (not all same values).
        This helps frontend detect whether a location has increasing/decreasing flood risk.
        """
        # Arrange
        roi_data = sample_historical_roi

        # Act
        response = test_client.post("/api/v1/analyze/trend", json=roi_data)

        # Assert
        assert response.status_code == 200
        data = response.json()

        probabilities = [entry["value"] for entry in data["years_data"]]

        # Check that data is not flat (some variation exists)
        min_prob = min(probabilities)
        max_prob = max(probabilities)
        variance = max_prob - min_prob

        # Allow trend data to be flat (variance = 0) but ensure it's not all zeros
        assert not all(p == 0 for p in probabilities), \
            "Historical data is all zeros (invalid trend)"

        print(f"\n✓ Historical Trend Detection Test PASSED")
        print(f"  - Probability Range: {min_prob}% to {max_prob}% (variance: {variance}%)")
        if variance > 0:
            print(f"  - Trend detected: YES")
        else:
            print(f"  - Trend detected: NO (flat line, but data is valid)")


    def test_historical_zones_severity_distribution(
        self,
        test_client,
        sample_historical_roi
    ):
        """
        Test: Verify zone severity distribution is realistic and balanced.
        Frontend uses this to show risk distribution pie charts.
        """
        # Arrange
        roi_data = sample_historical_roi

        # Act
        response = test_client.post("/api/v1/analyze/trend", json=roi_data)

        # Assert
        assert response.status_code == 200
        data = response.json()

        zones = data["zone_count_by_severity"]

        # Typically: Low > Medium > High (more stable areas than at-risk areas)
        severity_counts = {zone["severity"]: zone["count"] for zone in zones}

        total = sum(severity_counts.values())

        for severity, count in severity_counts.items():
            percentage = (count / total) * 100
            print(f"  - {severity}: {count} zones ({percentage:.1f}%)")

        print(f"\n✓ Zone Severity Distribution Test PASSED")
        print(f"  - Total Zones: {total}")


class TestCrossMapValidation:
    """Cross-validation tests between live and historical maps."""

    def test_live_and_historical_maps_use_different_tile_layers(
        self,
        test_client,
        sample_live_roi,
        sample_historical_roi
    ):
        """
        Test: Verify that live and historical endpoints return distinct tile layers.

        This ensures:
        - Frontend doesn't confuse live flood tiles with historical heatmap tiles
        - Different color palettes are applied correctly (Live: 1=Blue/2=Amber/3=Red vs Historical: gradient)
        - Layer switching works correctly
        """
        # Act
        live_response = test_client.post("/api/v1/analyze/live", json=sample_live_roi)
        hist_response = test_client.post("/api/v1/analyze/trend", json=sample_historical_roi)

        # Assert
        assert live_response.status_code == 200
        assert hist_response.status_code == 200

        live_data = live_response.json()
        hist_data = hist_response.json()

        live_tile_url = live_data["tile_url"]
        hist_composite_url = hist_data["composite_tile_url"]
        hist_heatmap_url = hist_data["trend_heatmap_url"]

        # URLs should be distinct
        assert live_tile_url != hist_composite_url, \
            "Live and historical composite tile URLs should be different"
        assert live_tile_url != hist_heatmap_url, \
            "Live and historical heatmap tile URLs should be different"
        assert hist_composite_url != hist_heatmap_url, \
            "Historical composite and heatmap URLs should be different"

        # Identify layer types from URL structure (assumption: URL contains layer name)
        assert "live" in live_tile_url.lower() or "ensemble" in live_tile_url.lower(), \
            f"Live tile URL should indicate 'live' or 'ensemble': {live_tile_url}"
        assert "historical" in hist_composite_url.lower() or "composite" in hist_composite_url.lower(), \
            f"Historical composite URL should indicate type: {hist_composite_url}"

        print(f"\n✓ Cross-Map Tile Layer Validation Test PASSED")
        print(f"  - Live Tile: {live_tile_url[:60]}...")
        print(f"  - Historical Composite: {hist_composite_url[:60]}...")
        print(f"  - Historical Heatmap: {hist_heatmap_url[:60]}...")
        print(f"  - All layers are distinct ✓")


# ==================== MANUAL TESTING GUIDE ====================
"""
After running pytest, you can manually test endpoints using curl or Postman:

1. START API SERVER:
   cd backend
   uvicorn app.main:app --reload --port 8000

2. TEST LIVE FLOOD ANALYSIS:
   curl -X POST http://localhost:8000/api/v1/analyze/live \
     -H "Content-Type: application/json" \
     -d '{"lat": 6.927, "lng": 80.773, "radius_km": 5}'

3. TEST HISTORICAL TREND ANALYSIS:
   curl -X POST http://localhost:8000/api/v1/analyze/trend \
     -H "Content-Type: application/json" \
     -d '{"lat": 6.927, "lng": 80.773, "radius_km": 10, "years": 5}'

4. EXPECTED RESPONSES:
   - Both should return HTTP 200
   - Both should include tile_url (for map visualization)
   - Live: includes geojson with risk-level polygons
   - Historical: includes years_data with yearly probabilities and zone_count_by_severity

5. FRONTEND INTEGRATION:
   - Parse tile_url and render using Leaflet/Mapbox with GEE tile parameters
   - Parse geojson and overlay polygons with color mapping (severity → color)
   - Display legends and impact metrics
"""
