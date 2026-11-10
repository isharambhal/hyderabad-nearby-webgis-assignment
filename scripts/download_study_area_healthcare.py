
import csv
import json
import time
import urllib.parse
import urllib.request
from pathlib import Path
from collections import Counter

from shapely.geometry import shape, Point, mapping
from shapely.ops import unary_union


# ==========================================
# 1. PROJECT PATHS
# ==========================================

ROOT = Path(__file__).resolve().parents[1]

WARD_FILE = ROOT / "analysis" / "study_area" / "selected_wards.geojson"

OUTPUT_DIR = ROOT / "data" / "study_area"

GEOJSON_OUTPUT = OUTPUT_DIR / "healthcare_osm.geojson"
CSV_OUTPUT = OUTPUT_DIR / "healthcare_osm.csv"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# ==========================================
# 2. READ SELECTED WARD BOUNDARIES
# ==========================================

print("Step 1: Reading selected ward boundaries...")

if not WARD_FILE.exists():
    raise SystemExit(f"File not found: {WARD_FILE}")

with WARD_FILE.open("r", encoding="utf-8") as file:
    ward_data = json.load(file)

ward_geometries = [
    shape(feature["geometry"])
    for feature in ward_data["features"]
    if feature.get("geometry")
]

if not ward_geometries:
    raise SystemExit("No ward geometries found.")

study_boundary = unary_union(ward_geometries)

if not study_boundary.is_valid:
    study_boundary = study_boundary.buffer(0)

print(f"Selected polygons: {len(ward_geometries)}")
print("Study boundary successfully loaded.")


# ==========================================
# 3. CALCULATE BOUNDING BOX
# ==========================================

WEST, SOUTH, EAST, NORTH = study_boundary.bounds

print("\nStep 2: Study-area bounding box calculated.")
print(f"South: {SOUTH}")
print(f"West: {WEST}")
print(f"North: {NORTH}")
print(f"East: {EAST}")


# ==========================================
# 4. PREPARE OVERPASS QUERY
# ==========================================

OVERPASS_URL = "https://overpass-api.de/api/interpreter"

query = f"""
[out:json][timeout:120];
(
  nwr["amenity"~"^(hospital|clinic|doctors|pharmacy|dentist|physiotherapist|veterinary)$"]({SOUTH},{WEST},{NORTH},{EAST});
  nwr["healthcare"]({SOUTH},{WEST},{NORTH},{EAST});
);
out center tags;
"""


# ==========================================
# 5. DOWNLOAD OPENSTREETMAP DATA
# ==========================================

print("\nStep 3: Requesting healthcare data from OSM...")

payload = urllib.parse.urlencode(
    {"data": query}
).encode("utf-8")

request = urllib.request.Request(
    OVERPASS_URL,
    data=payload,
    headers={
        "User-Agent": "HyderabadNearbyServicesWebGIS/1.0",
        "Content-Type": "application/x-www-form-urlencoded"
    }
)

data = None

for attempt in range(3):
    try:
        print(f"Download attempt {attempt + 1}...")

        with urllib.request.urlopen(
            request,
            timeout=180
        ) as response:

            data = json.loads(
                response.read().decode("utf-8")
            )

        break

    except Exception as error:

        if attempt == 2:
            raise SystemExit(
                f"OSM download failed: {error}"
            )

        print(f"Error: {error}")
        print("Retrying in 10 seconds...")
        time.sleep(10)

elements = data.get("elements", [])

print(f"OSM elements downloaded: {len(elements)}")


# ==========================================
# 6. CLASSIFY HEALTHCARE FEATURES
# ==========================================

def classify_category(tags):
    amenity = tags.get("amenity", "").lower()
    healthcare = tags.get("healthcare", "").lower()

    if amenity == "hospital":
        return "Hospital"
    elif amenity == "pharmacy":
        return "Pharmacy"
    elif amenity == "doctors":
        return "Doctor"
    elif amenity == "dentist":
        return "Dental Clinic"
    elif amenity == "clinic":
        return "Clinic"
    elif healthcare == "yes":
        return "Healthcare Centre"
    elif healthcare:
        return healthcare.replace("_", " ").title()

    return amenity.title() if amenity else "Other"


# ==========================================
# 7. FILTER FEATURES WITHIN WARDS
# ==========================================

print("\nStep 4: Filtering healthcare features...")

features = []
seen = set()

for element in elements:

    tags = element.get("tags", {})
    category = classify(tags)

    if not category:
        continue

    source_id = (
        f"{element.get('type')}/{element.get('id')}"
    )

    if source_id in seen:
        continue

    lat = element.get("lat")
    lon = element.get("lon")

    if lat is None or lon is None:
        center = element.get("center", {})
        lat = center.get("lat")
        lon = center.get("lon")

    if lat is None or lon is None:
        continue

    lat = float(lat)
    lon = float(lon)

    point = Point(lon, lat)

    # Keep only points inside Ward 106 and Ward 109.

    if not study_boundary.covers(point):
        continue

    seen.add(source_id)

    address_parts = [
        tags.get("addr:housenumber", ""),
        tags.get("addr:street", ""),
        tags.get("addr:suburb", ""),
        tags.get("addr:city", "")
    ]

    address = ", ".join(
        part for part in address_parts if part
    )

    properties = {
        "name": (
            tags.get("name")
            or tags.get("name:en")
            or f"{category} (unnamed)"
        ),
        "category": category,
        "subcategory": tags.get("healthcare")
            or tags.get("amenity", ""),
        "latitude": lat,
        "longitude": lon,
        "address": address,
        "phone": tags.get("phone")
            or tags.get("contact:phone", ""),
        "opening_hours": tags.get("opening_hours", ""),
        "osm_type": element.get("type", ""),
        "osm_id": element.get("id", ""),
        "source_id": source_id,
        "source": "OpenStreetMap"
    }

    features.append({
        "type": "Feature",
        "geometry": mapping(point),
        "properties": properties
    })


# ==========================================
# 8. SAVE GEOJSON
# ==========================================

print("\nStep 5: Saving GeoJSON...")

geojson_data = {
    "type": "FeatureCollection",
    "features": features
}

with GEOJSON_OUTPUT.open(
    "w",
    encoding="utf-8"
) as file:

    json.dump(
        geojson_data,
        file,
        indent=2,
        ensure_ascii=False
    )


# ==========================================
# 9. SAVE CSV
# ==========================================

print("Step 6: Saving CSV...")

fields = [
    "name",
    "category",
    "subcategory",
    "latitude",
    "longitude",
    "address",
    "phone",
    "opening_hours",
    "osm_type",
    "osm_id",
    "source_id",
    "source"
]

with CSV_OUTPUT.open(
    "w",
    newline="",
    encoding="utf-8-sig"
) as file:

    writer = csv.DictWriter(
        file,
        fieldnames=fields
    )

    writer.writeheader()

    for feature in features:
        writer.writerow(feature["properties"])


# ==========================================
# 10. PRINT FINAL SUMMARY
# ==========================================

counts = Counter(
    feature["properties"]["category"]
    for feature in features
)

print("\n" + "=" * 45)
print("HEALTHCARE DATA DOWNLOAD SUMMARY")
print("=" * 45)

print(f"OSM elements downloaded: {len(elements)}")
print(f"Healthcare features inside wards: {len(features)}")
print(f"Unique OSM records: {len(seen)}")

print("\nCategory-wise counts:")

for category, count in sorted(counts.items()):
    print(f"{category}: {count}")

print("\nFiles saved:")

print(GEOJSON_OUTPUT)
print(CSV_OUTPUT)

print("\nDownload completed successfully.")
print("Source: OpenStreetMap contributors.")
print("=" * 45)
