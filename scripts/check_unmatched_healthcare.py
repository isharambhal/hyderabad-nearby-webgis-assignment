
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

NEW_FILE = ROOT / "data" / "study_area" / "healthcare_osm.csv"
COMPARISON_FILE = ROOT / "data" / "study_area" / "dataset_comparison.csv"

with open(NEW_FILE, encoding="utf-8-sig", newline="") as f:
    new_records = list(csv.DictReader(f))

with open(COMPARISON_FILE, encoding="utf-8-sig", newline="") as f:
    matches = list(csv.DictReader(f))

matched_ids = {
    row["new_osm_id"]
    for row in matches
}

unmatched = [
    record for record in new_records
    if record["osm_id"] not in matched_ids
]

print("New records without nearby old matches:", len(unmatched))
print("\nUnmatched healthcare facilities:\n")

for record in unmatched:
    print(
        record["name"],
        "|",
        record["category"],
        "| OSM ID:",
        record["osm_id"]
    )
