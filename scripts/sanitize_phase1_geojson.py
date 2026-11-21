
import os
from pathlib import Path
import ijson

ROOT = Path(__file__).resolve().parents[1]

FILES = [
    ROOT / "data/raw/phase1/healthcare/healthcare_expanded.geojson",
    ROOT / "data/raw/phase1/buildings/buildings_expanded.geojson",
    ROOT / "data/raw/phase1/walking_network/processed/walking_nodes.geojson",
    ROOT / "data/raw/phase1/walking_network/processed/walking_edges.geojson",
]

TOKENS = ("-Infinity", "Infinity", "NaN")
CHUNK_SIZE = 1024 * 1024
KEEP_LAST = 16


def is_boundary(char):
    return not (char.isalnum() or char == "_")


def sanitize_file(path):
    if not path.exists():
        raise FileNotFoundError(path)

    temp_path = path.with_name(path.name + ".tmp")

    inside_string = False
    escaped = False
    previous_char = ""
    replacements = 0
    carry = ""

    print(f"\nRepairing: {path.name}")

    try:
        with open(path, "r", encoding="utf-8", newline="") as src, \
             open(temp_path, "w", encoding="utf-8", newline="") as dst:

            while True:
                chunk = src.read(CHUNK_SIZE)
                eof = not chunk

                data = carry + chunk

                limit = len(data) if eof else max(
                    0, len(data) - KEEP_LAST
                )

                output = []
                i = 0

                while i < limit:
                    char = data[i]

                    # Preserve JSON strings exactly.
                    if inside_string:
                        output.append(char)

                        if escaped:
                            escaped = False
                        elif char == "\\":
                            escaped = True
                        elif char == '"':
                            inside_string = False

                        previous_char = char
                        i += 1
                        continue

                    if char == '"':
                        inside_string = True
                        output.append(char)
                        previous_char = char
                        i += 1
                        continue

                    # Replace invalid JSON constants outside strings.
                    matched = False

                    for token in TOKENS:
                        if not data.startswith(token, i):
                            continue

                        end = i + len(token)

                        next_ok = (
                            end == len(data)
                            or is_boundary(data[end])
                        )

                        if (
                            is_boundary(previous_char)
                            and next_ok
                        ):
                            output.append("null")
                            previous_char = "l"
                            replacements += 1
                            i = end
                            matched = True
                            break

                    if not matched:
                        output.append(char)
                        previous_char = char
                        i += 1

                dst.write("".join(output))

                carry = data[i:]

                if eof:
                    break

        os.replace(temp_path, path)

        # Validate the complete GeoJSON using streaming parsing.
        feature_count = 0

        with open(path, "rb") as f:
            for _ in ijson.items(f, "features.item"):
                feature_count += 1

        print("Invalid constants replaced:", replacements)
        print("Valid GeoJSON features:", f"{feature_count:,}")
        print("File size:", f"{path.stat().st_size / 1024 / 1024:.2f} MB")
        print("Validation: PASSED")

    except Exception:
        if temp_path.exists():
            temp_path.unlink()
        raise


def main():
    print("PHASE 1 GEOJSON REPAIR")
    print("======================")

    for path in FILES:
        sanitize_file(path)

    print("\nALL FOUR GEOJSON FILES REPAIRED AND VALIDATED.")


if __name__ == "__main__":
    main()
