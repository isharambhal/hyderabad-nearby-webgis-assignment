
import csv
import math
from pathlib import Path

# Project folder
ROOT = Path(__file__).resolve().parents[1]

# Input and output files
INPUT_FILE = ROOT / "data" / "study_area" / "healthcare_osm.csv"
OUTPUT_FILE = ROOT / "data" / "study_area" / "duplicate_pairs.csv"

DISTANCE_THRESHOLD = 25  # metres


def calculate_distance(lat1, lon1, lat2, lon2):
    """Calculate distance between two coordinates in metres."""

    earth_radius = 6371000

    lat1 = math.radians(lat1)
    lat2 = math.radians(lat2)
    lon1 = math.radians(lon1)
    lon2 = math.radians(lon2)

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1)
        * math.cos(lat2)
        * math.sin(dlon / 2) ** 2
    )

    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return earth_radius * c


# Step 1: Read healthcare CSV
print("Step 1: Reading healthcare dataset...")

with open(INPUT_FILE, "r", encoding="utf-8-sig", newline="") as file:
    records = list(csv.DictReader(file))

print("Total healthcare records:", len(records))


# Step 2: Compare every pair of facilities
print("\nStep 2: Checking facilities within 25 metres...")

duplicate_pairs = []

for i in range(len(records)):
    for j in range(i + 1, len(records)):

        first = records[i]
        second = records[j]

        try:
            lat1 = float(first["latitude"])
            lon1 = float(first["longitude"])
            lat2 = float(second["latitude"])
            lon2 = float(second["longitude"])
        except (ValueError, TypeError, KeyError):
            continue

        distance = calculate_distance(lat1, lon1, lat2, lon2)

        if distance <= DISTANCE_THRESHOLD:

            duplicate_pairs.append({
                "name_1": first.get("name", ""),
                "category_1": first.get("category", ""),
                "osm_id_1": first.get("osm_id", ""),
                "name_2": second.get("name", ""),
                "category_2": second.get("category", ""),
                "osm_id_2": second.get("osm_id", ""),
                "distance_metres": round(distance, 2)
            })


# Step 3: Save results
print("\nStep 3: Saving duplicate-check results...")

OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

fieldnames = [
    "name_1",
    "category_1",
    "osm_id_1",
    "name_2",
    "category_2",
    "osm_id_2",
    "distance_metres"
]

with open(OUTPUT_FILE, "w", encoding="utf-8", newline="") as file:
    writer = csv.DictWriter(file, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(duplicate_pairs)


# Step 4: Display summary
print("\n====================================")
print("DUPLICATE FACILITY CHECK SUMMARY")
print("====================================")

print("Total healthcare records:", len(records))
print("Distance threshold:", DISTANCE_THRESHOLD, "metres")
print("Nearby pairs identified:", len(duplicate_pairs))

if duplicate_pairs:
    print("\nPotential duplicate pairs:")

    for pair in duplicate_pairs:
        print(
            f"{pair['name_1']} <-> {pair['name_2']} "
            f"({pair['distance_metres']} metres)"
        )
else:
    print("\nNo pairs found within 25 metres.")

print("\nResults saved to:")
print(OUTPUT_FILE)

print("\nNote: Nearby pairs are candidates for manual review.")
print("They are not automatically deleted.")
print("====================================")
