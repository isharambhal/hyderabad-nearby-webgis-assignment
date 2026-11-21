
import os
import json
from pathlib import Path

import ijson
import psycopg2
from psycopg2.extras import execute_values
from dotenv import load_dotenv


# --------------------------------------------------
# 1. Configuration
# --------------------------------------------------

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "data" / "raw" / "phase1"

load_dotenv(dotenv_path=ROOT / ".env")

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": os.getenv("DB_PORT", "5432"),
    "dbname": os.getenv("DB_NAME", "hyderabad_webgis"),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD", "")
}

BATCH_SIZE = 1000

LAYERS = [
    {
        "table": "phase1_healthcare",
        "file": BASE / "healthcare" / "healthcare_expanded.geojson",
    },
    {
        "table": "phase1_buildings",
        "file": BASE / "buildings" / "buildings_expanded.geojson",
    },
    {
        "table": "phase1_walking_nodes",
        "file": BASE / "walking_network" / "processed" / "walking_nodes.geojson",
    },
    {
        "table": "phase1_walking_edges",
        "file": BASE / "walking_network" / "processed" / "walking_edges.geojson",
    }
]


# --------------------------------------------------
# 2. Feature preparation
# --------------------------------------------------

def text_value(value):
    if value is None:
        return None

    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False, default=str)

    return str(value)


def prepare_feature(feature):
    properties = feature.get("properties") or {}
    geometry = feature.get("geometry")

    if not geometry:
        return None

    osm_id = (
        properties.get("osmid")
        or properties.get("@id")
        or properties.get("id")
    )

    name = properties.get("name")

    category = None

    for key in (
        "healthcare", "amenity", "building",
        "highway", "landuse", "natural",
        "leisure", "shop"
    ):
        if properties.get(key) is not None:
            category = properties[key]
            break

    return (
        text_value(osm_id),
        text_value(name),
        text_value(category),
        json.dumps(properties, ensure_ascii=False, default=float),
        json.dumps(geometry, ensure_ascii=False, default=float)
    )


# --------------------------------------------------
# 3. SQL statements
# --------------------------------------------------

INSERT_SQL = """
INSERT INTO {table}
    (osm_id, name, category, properties, geom)
VALUES (
    %s,
    %s,
    %s,
    %s::jsonb,
    ST_Force2D(
        ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326)
    )
)
"""

BATCH_TEMPLATE = """
(
    %s,
    %s,
    %s,
    %s::jsonb,
    ST_Force2D(
        ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326)
    )
)
"""


# --------------------------------------------------
# 4. Batch insertion with individual-row fallback
# --------------------------------------------------

def insert_batch(cur, table, batch):

    query = INSERT_SQL.format(table=table)

    cur.execute("SAVEPOINT batch_sp")

    try:
        execute_values(
            cur,
            f"""
            INSERT INTO {table}
                (osm_id, name, category, properties, geom)
            VALUES %s
            """,
            batch,
            template=BATCH_TEMPLATE,
            page_size=BATCH_SIZE
        )

        cur.execute("RELEASE SAVEPOINT batch_sp")
        return len(batch), 0

    except Exception as batch_error:

        cur.execute("ROLLBACK TO SAVEPOINT batch_sp")

        print("Batch issue; checking rows individually:")
        print(str(batch_error)[:250])

        inserted = 0
        skipped = 0

        for record in batch:

            cur.execute("SAVEPOINT row_sp")

            try:
                cur.execute(query, record)
                cur.execute("RELEASE SAVEPOINT row_sp")
                inserted += 1

            except Exception as row_error:

                cur.execute("ROLLBACK TO SAVEPOINT row_sp")
                cur.execute("RELEASE SAVEPOINT row_sp")

                skipped += 1

                if skipped <= 5:
                    print("Skipped invalid feature:", str(row_error)[:200])

        cur.execute("RELEASE SAVEPOINT batch_sp")

        return inserted, skipped


# --------------------------------------------------
# 5. Main import procedure
# --------------------------------------------------

def main():

    print("\nConnecting to PostgreSQL...")

    for layer in LAYERS:
        if not layer["file"].exists():
            raise FileNotFoundError(
                f"Missing input file: {layer['file']}"
            )

    conn = psycopg2.connect(**DB_CONFIG)
    conn.autocommit = False

    try:
        cur = conn.cursor()

        cur.execute("CREATE EXTENSION IF NOT EXISTS postgis;")

        print("Database:", DB_CONFIG["dbname"])
        print("PostGIS connection successful.")

        # Recreate only our four Phase 1 tables.
        for layer in LAYERS:
            table = layer["table"]

            print("Preparing table:", table)

            cur.execute(f"DROP TABLE IF EXISTS {table} CASCADE;")

            cur.execute(f"""
                CREATE TABLE {table} (
                    feature_id BIGSERIAL PRIMARY KEY,
                    osm_id TEXT,
                    name TEXT,
                    category TEXT,
                    properties JSONB NOT NULL DEFAULT '{{}}'::jsonb,
                    geom geometry(Geometry, 4326) NOT NULL
                );
            """)

        # Import each GeoJSON file.
        for layer in LAYERS:

            table = layer["table"]
            file_path = layer["file"]

            print("\n===================================")
            print("IMPORTING:", table)
            print("File:", file_path.name)
            print("===================================")

            batch = []
            processed = 0
            inserted = 0
            skipped = 0

            with open(file_path, "rb") as f:

                for feature in ijson.items(f, "features.item"):

                    record = prepare_feature(feature)
                    processed += 1

                    if record is None:
                        skipped += 1
                        continue

                    batch.append(record)

                    if len(batch) >= BATCH_SIZE:

                        added, rejected = insert_batch(
                            cur, table, batch
                        )

                        inserted += added
                        skipped += rejected
                        batch.clear()

                    if processed % 5000 == 0:
                        print(
                            f"Read: {processed:,} | "
                            f"Inserted: {inserted:,} | "
                            f"Skipped: {skipped:,}"
                        )

            if batch:
                added, rejected = insert_batch(
                    cur, table, batch
                )

                inserted += added
                skipped += rejected

            print("\nLayer import result:")
            print("Features read:", f"{processed:,}")
            print("Rows inserted:", f"{inserted:,}")
            print("Rows skipped:", f"{skipped:,}")

            # Add spatial and category indexes.
            print("Creating GiST spatial index...")

            cur.execute(f"""
                CREATE INDEX {table}_geom_gix
                ON {table}
                USING GIST (geom);
            """)

            cur.execute(f"""
                CREATE INDEX {table}_category_idx
                ON {table} (category);
            """)

            cur.execute(f"ANALYZE {table};")

        # Commit all four Phase 1 layers.
        conn.commit()

        print("\n===================================")
        print("ALL PHASE 1 LAYERS IMPORTED")
        print("===================================")

        for layer in LAYERS:

            table = layer["table"]

            cur.execute(f"""
                SELECT
                    COUNT(*),
                    COUNT(*) FILTER (
                        WHERE ST_SRID(geom) = 4326
                    ),
                    ST_Extent(geom)
                FROM {table};
            """)

            count, srid_count, extent = cur.fetchone()

            print(f"\nTable: {table}")
            print("Features:", count)
            print("EPSG:4326 geometries:", srid_count)
            print("Extent:", extent)

        cur.close()

        print("\nDATABASE IMPORT COMPLETED SUCCESSFULLY")

    except Exception:
        conn.rollback()
        print("\nIMPORT FAILED. Database transaction rolled back.")
        raise

    finally:
        conn.close()


if __name__ == "__main__":
    main()
