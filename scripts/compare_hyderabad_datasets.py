
import csv
import json
import math
from pathlib import Path

from shapely.geometry import shape, Point
from shapely.ops import unary_union

ROOT = Path(__file__).resolve().parents[1]

OLD_FILE = ROOT / "data" / "hyderabad_services.csv"
NEW_FILE = ROOT / "data" / "study_area" / "healthcare_osm.csv"
WARD_FILE = ROOT / "analysis" / "study_area" / "selected_wards.geojson"

OUTPUT_DIR = ROOT / "data" / "study_area"
OUTPUT_FILE = OUTPUT_DIR / "dataset_comparison.csv"

HEALTHCARE_CATEGORIES = {
    "hospital", "clinic", "pharmacy"
}

MATCH_DISTANCE = 25


def distance_metres(lat1, lon1, lat2, lon2):
    radius = 6371000

    lat1, lon1, lat2, lon2 = map(
        math.radians, [lat1, lon1, lat2, lon2]
    )

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2)
        * math.sin(dlon / 2) ** 2
    )

    return radius * 2 * math.atan2(
        math.sqrt(a), math.sqrt(1 - a)
    )


print("Step 1: Loading ward boundaries...")

with open(WARD_FILE, encoding="utf-8") as f:
    ward_data = json.load(f)

polygons = [
    shape(feature["geometry"])
    for feature in ward_data["features"]
]

boundary = unary_union(polygons)

print("Selected ward polygons:", len(polygons))


print("\nStep 2: Reading original Hyderabad dataset...")

with open(OLD_FILE, encoding="utf-8-sig", newline="") as f:
    old_records = list(csv.DictReader(f))

old_healthcare = [
    r for r in old_records
    if r.get("category", "").strip().lower()
    in HEALTHCARE_CATEGORIES
]

old_inside = []

for r in old_healthcare:
    try:
        point = Point(
            float(r["longitude"]),
            float(r["latitude"])
        )

        if boundary.covers(point):
            old_inside.append(r)

    except (ValueError, KeyError, TypeError):
        continue

print("Original citywide records:", len(old_records))
print("Original healthcare records:", len(old_healthcare))
print("Original healthcare records inside selected wards:", len(old_inside))


print("\nStep 3: Reading new study-area dataset...")

with open(NEW_FILE, encoding="utf-8-sig", newline="") as f:
    new_records = list(csv.DictReader(f))

print("New study-area records:", len(new_records))


print("\nStep 4: Comparing locations within 25 metres...")

comparison = []
matched_old = set()
matched_new = set()

for i, old in enumerate(old_inside):
    try:
        old_lat = float(old["latitude"])
        old_lon = float(old["longitude"])
    except (ValueError, KeyError):
        continue

    for j, new in enumerate(new_records):
        try:
            new_lat = float(new["latitude"])
            new_lon = float(new["longitude"])
        except (ValueError, KeyError):
            continue

        distance = distance_metres(
            old_lat, old_lon, new_lat, new_lon
        )

        if distance <= MATCH_DISTANCE:
            matched_old.add(i)
            matched_new.add(j)

            comparison.append({
                "old_name": old.get("name", ""),
                "old_category": old.get("category", ""),
                "new_name": new.get("name", ""),
                "new_category": new.get("category", ""),
                "distance_metres": round(distance, 2),
                "old_source_id": old.get("source_id", ""),
                "new_osm_id": new.get("osm_id", "")
            })


print("\nStep 5: Saving comparison report...")

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

fields = [
    "old_name", "old_category",
    "new_name", "new_category",
    "distance_metres",
    "old_source_id", "new_osm_id"
]

with open(OUTPUT_FILE, "w", encoding="utf-8", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=fields)
    writer.writeheader()
    writer.writerows(comparison)


print("\n========== DATASET COMPARISON ==========")
print("Original healthcare records inside wards:", len(old_inside))
print("New healthcare records:", len(new_records))
print("Old records with a nearby new record:", len(matched_old))
print("New records with a nearby old record:", len(matched_new))
print("Nearby record pairs:", len(comparison))
print("Old records without a nearby match:", len(old_inside) - len(matched_old))
print("New records without a nearby match:", len(new_records) - len(matched_new))
print("Matching threshold:", MATCH_DISTANCE, "metres")
print("Comparison saved to:", OUTPUT_FILE)
print("========================================")

print("\nNote: Nearby matches are not proof of identical facilities.")