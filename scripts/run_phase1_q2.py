
import os
import csv
from pathlib import Path

import psycopg2
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(dotenv_path=ROOT / ".env")

DB = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": os.getenv("DB_PORT", "5432"),
    "dbname": os.getenv("DB_NAME", "hyderabad_webgis"),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD", "")
}

OUT = ROOT / "outputs" / "phase1"
OUT.mkdir(parents=True, exist_ok=True)

REPORT = OUT / "Q2_UTM_results.txt"
CSV = OUT / "Q2_UTM_building_counts_500m.csv"

UTM = 32644
SAMPLE_ID = 1
report = []


def log(value=""):
    value = str(value)
    print(value)
    report.append(value)


def explain(cur, title, sql, params):
    log("\n" + "=" * 65)
    log(title)
    log("=" * 65)

    cur.execute(
        "EXPLAIN (ANALYZE, BUFFERS, VERBOSE) " + sql,
        params
    )

    for row in cur.fetchall():
        log(row[0])


def main():
    conn = psycopg2.connect(**DB)

    try:
        cur = conn.cursor()

        log("Q2: UTM GEOMETRY SPATIAL INDEX EXPERIMENT")
        log("CRS: EPSG:32644")
        log("Distance threshold: 500 metres")

        cur.execute("SELECT COUNT(*) FROM phase1_healthcare")
        log(f"Healthcare features: {cur.fetchone()[0]:,}")

        cur.execute("SELECT COUNT(*) FROM phase1_buildings")
        log(f"Building features: {cur.fetchone()[0]:,}")

        # Service geometries may include polygons.
        # PointOnSurface provides a representative service point.
        dwithin_sql = f"""
            WITH service AS (
                SELECT ST_Transform(
                    ST_PointOnSurface(geom), {UTM}
                ) AS geom
                FROM phase1_healthcare
                WHERE feature_id = %s
            )
            SELECT COUNT(*)
            FROM phase1_buildings b
            CROSS JOIN service s
            WHERE ST_DWithin(
                ST_Transform(b.geom, {UTM}),
                s.geom,
                500
            );
        """

        distance_sql = f"""
            WITH service AS (
                SELECT ST_Transform(
                    ST_PointOnSurface(geom), {UTM}
                ) AS geom
                FROM phase1_healthcare
                WHERE feature_id = %s
            )
            SELECT COUNT(*)
            FROM phase1_buildings b
            CROSS JOIN service s
            WHERE ST_Distance(
                ST_Transform(b.geom, {UTM}),
                s.geom
            ) < 500;
        """

        # Remove prior geography expression index and any previous
        # UTM expression index so the first plan is the baseline.
        cur.execute("""
            DROP INDEX IF EXISTS phase1_buildings_geog_gix;
            DROP INDEX IF EXISTS phase1_buildings_utm44n_gix;
        """)

        cur.execute("ANALYZE phase1_buildings")

        explain(
            cur,
            "A. ST_DWithin BEFORE UTM GiST index",
            dwithin_sql,
            (SAMPLE_ID,)
        )

        log("\nCreating UTM functional GiST index...")

        cur.execute(f"""
            CREATE INDEX phase1_buildings_utm44n_gix
            ON phase1_buildings
            USING GIST (ST_Transform(geom, {UTM}));
        """)

        cur.execute("ANALYZE phase1_buildings")

        explain(
            cur,
            "B. ST_DWithin AFTER UTM GiST index",
            dwithin_sql,
            (SAMPLE_ID,)
        )

        explain(
            cur,
            "C. ST_Distance < 500 WITH UTM GiST index present",
            distance_sql,
            (SAMPLE_ID,)
        )

        cur.execute(dwithin_sql, (SAMPLE_ID,))
        dwithin_count = cur.fetchone()[0]

        cur.execute(distance_sql, (SAMPLE_ID,))
        distance_count = cur.fetchone()[0]

        log("\nSAMPLE FEATURE COMPARISON")
        log(f"Healthcare feature_id: {SAMPLE_ID}")
        log(f"ST_DWithin count: {dwithin_count:,}")
        log(f"ST_Distance count: {distance_count:,}")
        log(f"Counts agree: {dwithin_count == distance_count}")

        # Official all-service count using UTM geometry.
        log("\nCalculating building counts for every healthcare feature...")

        cur.execute("DROP TABLE IF EXISTS phase1_healthcare_building_counts_500m")

        cur.execute(f"""
            CREATE TABLE phase1_healthcare_building_counts_500m AS
            SELECT
                h.feature_id AS healthcare_feature_id,
                h.name AS service_name,
                h.category,
                COUNT(b.feature_id)::BIGINT AS buildings_within_500m,
                ST_PointOnSurface(h.geom) AS geom
            FROM phase1_healthcare h
            LEFT JOIN phase1_buildings b
                ON ST_DWithin(
                    ST_Transform(b.geom, {UTM}),
                    ST_Transform(ST_PointOnSurface(h.geom), {UTM}),
                    500
                )
            GROUP BY h.feature_id, h.name, h.category, h.geom;
        """)

        cur.execute("""
            CREATE INDEX phase1_hc_building_counts_geom_gix
            ON phase1_healthcare_building_counts_500m
            USING GIST (geom);
        """)

        cur.execute("ANALYZE phase1_healthcare_building_counts_500m")

        cur.execute("""
            SELECT healthcare_feature_id, service_name,
                   category, buildings_within_500m
            FROM phase1_healthcare_building_counts_500m
            ORDER BY healthcare_feature_id;
        """)

        rows = cur.fetchall()

        with open(CSV, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow([
                "healthcare_feature_id",
                "service_name",
                "category",
                "buildings_within_500m"
            ])
            writer.writerows(rows)

        cur.execute("""
            SELECT COUNT(*),
                   MIN(buildings_within_500m),
                   MAX(buildings_within_500m),
                   ROUND(AVG(buildings_within_500m), 2),
                   SUM(buildings_within_500m)
            FROM phase1_healthcare_building_counts_500m;
        """)

        total, minimum, maximum, average, summed = cur.fetchone()

        log("\nALL-SERVICE SUMMARY")
        log(f"Healthcare features analysed: {total:,}")
        log(f"Minimum buildings: {minimum:,}")
        log(f"Maximum buildings: {maximum:,}")
        log(f"Average buildings: {average}")
        log(f"Sum of per-service counts: {summed:,}")

        conn.commit()

        log("\nQ2 UTM ANALYSIS COMPLETED")
        log(f"Report: {REPORT}")
        log(f"CSV: {CSV}")

        cur.close()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()
        REPORT.write_text("\n".join(report), encoding="utf-8")


if __name__ == "__main__":
    main()
