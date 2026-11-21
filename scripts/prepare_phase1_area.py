
import json
from pathlib import Path

from shapely.geometry import shape, mapping
from shapely.ops import unary_union, transform
from pyproj import Transformer


# --------------------------------------------------
# 1. PROJECT PATHS
# --------------------------------------------------

ROOT = Path(__file__).resolve().parents[1]

INPUT_FILE = (
    ROOT / "analysis" / "study_area" / "selected_wards.geojson"
)

OUTPUT_DIR = ROOT / "data" / "raw" / "phase1"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

OUTPUT_GEOJSON = OUTPUT_DIR / "study_area_buffer_2km.geojson"
OUTPUT_WKT = OUTPUT_DIR / "study_area_buffer_2km_utm44n.wkt"
OUTPUT_SUMMARY = OUTPUT_DIR / "study_area_buffer_summary.txt"

SOURCE_CRS = "EPSG:4326"
UTM_CRS = "EPSG:32644"

BUFFER_DISTANCE = 2000  # metres


# --------------------------------------------------
# 2. READ SELECTED WARD BOUNDARIES
# --------------------------------------------------

print("Step 1: Reading selected ward boundaries...")

if not INPUT_FILE.exists():
    raise FileNotFoundError(f"File not found: {INPUT_FILE}")

with INPUT_FILE.open("r", encoding="utf-8") as file:
    data = json.load(file)

features = data.get("features", [])

if not features:
    raise ValueError("No features found in selected wards GeoJSON.")

geometries = [
    shape(feature["geometry"])
    for feature in features
    if feature.get("geometry")
]

if not geometries:
    raise ValueError("No valid geometries found.")

print("Selected ward features:", len(geometries))
print("Source CRS assumed:", SOURCE_CRS)


# --------------------------------------------------
# 3. COMBINE WARD GEOMETRIES
# --------------------------------------------------

print("\nStep 2: Combining ward geometries...")

study_area = unary_union(geometries)

if not study_area.is_valid:
    study_area = study_area.buffer(0)

if study_area.is_empty:
    raise ValueError("Combined study area is empty.")


# --------------------------------------------------
# 4. CREATE CRS TRANSFORMERS
# --------------------------------------------------

print("\nStep 3: Creating CRS transformations...")

to_utm = Transformer.from_crs(
    SOURCE_CRS,
    UTM_CRS,
    always_xy=True
)

to_wgs84 = Transformer.from_crs(
    UTM_CRS,
    SOURCE_CRS,
    always_xy=True
)

study_area_utm = transform(to_utm.transform, study_area)


# --------------------------------------------------
# 5. CALCULATE ORIGINAL AREA
# --------------------------------------------------

original_area_km2 = study_area_utm.area / 1_000_000


# --------------------------------------------------
# 6. CREATE 2 KM BUFFER
# --------------------------------------------------

print("\nStep 4: Creating 2 km buffer...")

buffer_utm = study_area_utm.buffer(BUFFER_DISTANCE)

if buffer_utm.is_empty or not buffer_utm.is_valid:
    raise ValueError("Buffer geometry is empty or invalid.")

buffer_area_km2 = buffer_utm.area / 1_000_000

print("Original area:", round(original_area_km2, 6), "km2")
print("Buffered area:", round(buffer_area_km2, 6), "km2")


# --------------------------------------------------
# 7. SAVE BUFFER AS WGS84 GEOJSON
# --------------------------------------------------

print("\nStep 5: Saving WGS84 GeoJSON...")

buffer_wgs84 = transform(
    to_wgs84.transform,
    buffer_utm
)

output_data = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "properties": {
                "area_name": "Hyderabad Phase 1 Study Area",
                "buffer_m": BUFFER_DISTANCE,
                "source_crs": SOURCE_CRS,
                "projected_crs": UTM_CRS
            },
            "geometry": mapping(buffer_wgs84)
        }
    ]
}

with OUTPUT_GEOJSON.open("w", encoding="utf-8") as file:
    json.dump(output_data, file, indent=2)


# --------------------------------------------------
# 8. SAVE PROJECTED GEOMETRY AS WKT
# --------------------------------------------------

print("\nStep 6: Saving UTM geometry as WKT...")

with OUTPUT_WKT.open("w", encoding="utf-8") as file:
    file.write(buffer_utm.wkt)


# --------------------------------------------------
# 9. SAVE SUMMARY
# --------------------------------------------------

summary = [
    "PHASE 1 STUDY AREA BUFFER SUMMARY",
    "=" * 45,
    f"Input file: {INPUT_FILE}",
    f"Selected ward features: {len(geometries)}",
    f"Source CRS: {SOURCE_CRS}",
    f"Projected CRS: {UTM_CRS}",
    f"Buffer distance: {BUFFER_DISTANCE} metres",
    f"Original study area: {original_area_km2:.6f} km2",
    f"Buffered area: {buffer_area_km2:.6f} km2",
    "",
    f"WGS84 GeoJSON: {OUTPUT_GEOJSON}",
    f"UTM WKT: {OUTPUT_WKT}"
]

OUTPUT_SUMMARY.write_text(
    "\n".join(summary),
    encoding="utf-8"
)

print("\n" + "=" * 45)
print("\n".join(summary))
print("\nBuffer preparation completed successfully!")
