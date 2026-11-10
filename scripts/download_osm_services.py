
import csv
import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / "hyderabad_services.csv"

# Bounding box derived from your Hyderabad ward GeoJSON.
SOUTH, WEST = 17.2916377, 78.2717512
NORTH, EAST = 17.5608321, 78.6212303

OVERPASS_URL = "https://overpass-api.de/api/interpreter"

query = f"""
[out:json][timeout:120];
(
  nwr["amenity"~"hospital|clinic|doctors|pharmacy|police|atm|school|college|university|kindergarten|fuel|bank|fire_station|post_office|library|place_of_worship"]({SOUTH},{WEST},{NORTH},{EAST});
  nwr["leisure"="park"]({SOUTH},{WEST},{NORTH},{EAST});
);
out center tags;
"""

print("Requesting mapped facilities from OpenStreetMap...")
payload = urllib.parse.urlencode({"data": query}).encode("utf-8")
request = urllib.request.Request(
    OVERPASS_URL,
    data=payload,
    headers={
        "User-Agent": "HyderabadNearbyServicesWebGIS/1.0",
        "Content-Type": "application/x-www-form-urlencoded",
    },
)

# Retry temporary server/network failures.
data = None
for attempt in range(3):
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            data = json.loads(response.read().decode("utf-8"))
        break
    except Exception as exc:
        if attempt == 2:
            raise SystemExit(
                f"OSM download failed: {exc}\n"
                "Try again later if the public Overpass service is busy."
            )
        print(f"Request failed: {exc}. Retrying in 10 seconds...")
        time.sleep(10)

def classify(tags):
    amenity = tags.get("amenity", "")
    if amenity == "hospital":
        return "Hospital"
    if amenity in ("clinic", "doctors"):
        return "Clinic"
    if amenity == "pharmacy":
        return "Pharmacy"
    if amenity == "police":
        return "Police Station"
    if amenity == "atm":
        return "ATM"
    if amenity in ("school", "college", "university", "kindergarten"):
        return "School"
    if amenity == "fuel":
        return "Fuel Station"
    if amenity == "bank":
        return "Bank"
    if amenity == "fire_station":
        return "Fire Station"
    if amenity == "post_office":
        return "Post Office"
    if amenity == "library":
        return "Library"
    if amenity == "place_of_worship":
        return "Place of Worship"
    if tags.get("leisure") == "park":
        return "Park"
    return None

rows = []
seen = set()

for element in data.get("elements", []):
    tags = element.get("tags", {})
    category = classify(tags)
    if not category:
        continue

    # Nodes have their own coordinates; ways/relations use Overpass centers.
    lat = element.get("lat")
    lon = element.get("lon")
    if lat is None or lon is None:
        center = element.get("center", {})
        lat = center.get("lat")
        lon = center.get("lon")

    if lat is None or lon is None:
        continue

    source_id = f"{element.get('type', 'unknown')}/{element.get('id', '')}"
    if source_id in seen:
        continue
    seen.add(source_id)

    address_parts = [
        tags.get("addr:housenumber", ""),
        tags.get("addr:street", ""),
        tags.get("addr:suburb", ""),
        tags.get("addr:city", ""),
    ]
    address = ", ".join(part for part in address_parts if part)

    rows.append({
        "name": tags.get("name") or tags.get("name:en") or f"{category} (unnamed)",
        "category": category,
        "latitude": lat,
        "longitude": lon,
        "subcategory": tags.get("healthcare") or tags.get("school") or tags.get("amenity", ""),
        "address": address,
        "phone": tags.get("phone") or tags.get("contact:phone", ""),
        "opening_hours": tags.get("opening_hours", ""),
        "source": "OpenStreetMap",
        "source_id": source_id,
    })

OUTPUT.parent.mkdir(parents=True, exist_ok=True)
fields = [
    "name", "category", "latitude", "longitude", "subcategory",
    "address", "phone", "opening_hours", "source", "source_id"
]

with OUTPUT.open("w", newline="", encoding="utf-8-sig") as file:
    writer = csv.DictWriter(file, fieldnames=fields)
    writer.writeheader()
    writer.writerows(rows)

print(f"Download complete: {len(rows)} mapped facilities found.")
print(f"CSV saved to: {OUTPUT}")
print("Source: OpenStreetMap contributors; data completeness is not guaranteed.")
