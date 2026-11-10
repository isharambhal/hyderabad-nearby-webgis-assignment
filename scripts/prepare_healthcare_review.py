
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

INPUT_FILE = ROOT / "data" / "study_area" / "healthcare_osm.csv"
OUTPUT_FILE = ROOT / "data" / "study_area" / "healthcare_osm_review.csv"

# Records requiring manual review
review_notes = {
    "8763316074": (
        "Possible co-located listing with Srikara Hospital. "
        "Same mapped building; verify institution identity."
    ),
    "741855446": (
        "Possible co-located listing with Udbhava Hospital. "
        "Same mapped building; verify institution identity."
    ),
    "7007970916": (
        "OSM tags indicate hospital with ophthalmology specialty. "
        "Verify service classification."
    )
}

print("Step 1: Reading original healthcare dataset...")

with open(INPUT_FILE, "r", encoding="utf-8-sig", newline="") as file:
    records = list(csv.DictReader(file))

print("Original records:", len(records))

print("\nStep 2: Adding data-quality review flags...")

for record in records:
    osm_id = record["osm_id"]

    if osm_id in review_notes:
        record["review_flag"] = "Yes"
        record["review_note"] = review_notes[osm_id]
    else:
        record["review_flag"] = "No"
        record["review_note"] = "No specific review issue identified."

print("\nStep 3: Saving review dataset...")

fieldnames = list(records[0].keys())

with open(OUTPUT_FILE, "w", encoding="utf-8", newline="") as file:
    writer = csv.DictWriter(file, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(records)

flagged = sum(
    1 for record in records
    if record["review_flag"] == "Yes"
)

print("\n========== REVIEW SUMMARY ==========")
print("Total records:", len(records))
print("Records flagged for review:", flagged)
print("Records without specific flags:", len(records) - flagged)
print("Records deleted:", 0)
print("Output:", OUTPUT_FILE)
print("====================================")
