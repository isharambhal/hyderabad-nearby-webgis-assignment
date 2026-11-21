
import os
from pathlib import Path

import psycopg2
from psycopg2 import sql
from psycopg2.extras import Json, execute_values
from dotenv import load_dotenv, dotenv_values


ROOT = Path(__file__).resolve().parents[1]

load_dotenv(ROOT / ".env")
compose_env = dotenv_values(ROOT / ".env.compose")

SOURCE = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": os.getenv("DB_PORT", "5432"),
    "dbname": os.getenv("DB_NAME", "hyderabad_webgis"),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD", "")
}

TARGET = {
    "host": "localhost",
    "port": "5433",
    "dbname": compose_env["POSTGRES_DB"],
    "user": compose_env["POSTGRES_USER"],
    "password": compose_env["POSTGRES_PASSWORD"]
}

TABLES = [
    "wards",
    "services",
    "services_public",
    "phase1_healthcare",
    "phase1_buildings",
    "phase1_walking_nodes",
    "phase1_walking_edges",
    "phase1_healthcare_building_counts_500m",
    "phase3_h3_access",
    "phase3_service_isochrones"
]

BATCH_SIZE = 500

TYPE_MAP = {
    "bigint": "BIGINT",
    "integer": "INTEGER",
    "text": "TEXT",
    "double precision": "DOUBLE PRECISION",
    "boolean": "BOOLEAN",
    "jsonb": "JSONB",
    "json": "JSON",
    "timestamp with time zone": "TIMESTAMPTZ",
    "timestamp without time zone": "TIMESTAMP"
}


def get_source_schema(cur, table):
    cur.execute("""
        SELECT column_name, data_type, udt_name
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = %s
        ORDER BY ordinal_position;
    """, (table,))

    columns = cur.fetchall()

    if not columns:
        raise RuntimeError(f"Source table not found: {table}")

    geom_columns = [
        col[0] for col in columns
        if col[2] == "geometry"
    ]

    if len(geom_columns) != 1:
        raise RuntimeError(
            f"Expected exactly one geometry column in {table}; "
            f"found {geom_columns}"
        )

    return columns, geom_columns[0]


def create_target_table(cur, table, columns, geometry_column):
    definitions = []

    for name, data_type, udt in columns:
        if name == geometry_column:
            definitions.append(
                sql.SQL("{} geometry(Geometry,4326)").format(
                    sql.Identifier(name)
                )
            )
        else:
            mapped_type = TYPE_MAP.get(data_type)

            if not mapped_type:
                raise RuntimeError(
                    f"Unsupported column type {data_type} "
                    f"for {table}.{name}"
                )

            definitions.append(
                sql.SQL("{} {}").format(
                    sql.Identifier(name),
                    sql.SQL(mapped_type)
                )
            )

    statement = sql.SQL(
        "CREATE TABLE {} ({})"
    ).format(
        sql.Identifier(table),
        sql.SQL(", ").join(definitions)
    )

    cur.execute(statement)


def transfer_table(src_cur, dst_cur, table):
    print("\n" + "=" * 60)
    print("TRANSFERRING:", table)
    print("=" * 60)

    columns, geom_col = get_source_schema(src_cur, table)

    col_names = [c[0] for c in columns]
    json_columns = {
        c[0] for c in columns
        if c[1] in ("json", "jsonb")
    }

    ordinary_columns = [
        name for name in col_names
        if name != geom_col
    ]

    # Confirm source geometry SRID and extent.
    src_cur.execute(sql.SQL("""
        SELECT
            COUNT(*),
            COUNT(DISTINCT ST_SRID({geom})),
            MIN(ST_SRID({geom})),
            ST_Extent({geom})
        FROM public.{table}
    """).format(
        geom=sql.Identifier(geom_col),
        table=sql.Identifier(table)
    ))

    source_geom_info = src_cur.fetchone()

    print("Source rows:", f"{source_geom_info[0]:,}")
    print("Source geometry SRIDs:", source_geom_info[1:])

    # Recreate only the corresponding table in the Docker database.
    dst_cur.execute(
        sql.SQL("DROP TABLE IF EXISTS public.{} CASCADE").format(
            sql.Identifier(table)
        )
    )

    create_target_table(
        dst_cur, table, columns, geom_col
    )

    # Select EWKB, preserving geometry SRID metadata.
    select_parts = []

    for col in col_names:
        if col == geom_col:
            select_parts.append(
                sql.SQL("ST_AsEWKB({}) AS {}").format(
                    sql.Identifier(col),
                    sql.Identifier(col)
                )
            )
        else:
            select_parts.append(sql.Identifier(col))

    select_query = sql.SQL(
        "SELECT {} FROM public.{}"
    ).format(
        sql.SQL(", ").join(select_parts),
        sql.Identifier(table)
    )

    src_cur.execute(select_query)

    # Prepare insert with a geometry constructor.
    value_templates = []

    for col in col_names:
        if col == geom_col:
            if table == "phase1_healthcare_building_counts_500m":
                # The source summary-table geometries have SRID 0.
                value_templates.append(
                    "ST_SetSRID(ST_GeomFromEWKB(%s),4326)"
                )
            else:
                value_templates.append(
                    "ST_GeomFromEWKB(%s)"
                )
        else:
            value_templates.append("%s")

    insert_template = "(" + ", ".join(value_templates) + ")"

    insert_query = sql.SQL(
        "INSERT INTO public.{} ({}) VALUES %s"
    ).format(
        sql.Identifier(table),
        sql.SQL(", ").join(
            sql.Identifier(c) for c in col_names
        )
    ).as_string(dst_cur.connection)

    inserted = 0

    while True:
        batch = src_cur.fetchmany(BATCH_SIZE)

        if not batch:
            break

        cleaned_batch = []

        for row in batch:
            values = list(row)

            for i, col in enumerate(col_names):

                if col == geom_col:
                    values[i] = (
                        bytes(values[i]) if values[i] is not None
                        else None
                    )

                elif col in json_columns and values[i] is not None:
                    values[i] = Json(values[i], dumps=lambda x: __import__(
                        "json"
                    ).dumps(x, ensure_ascii=False, default=str))

            cleaned_batch.append(tuple(values))

        execute_values(
            dst_cur,
            insert_query,
            cleaned_batch,
            template=insert_template,
            page_size=BATCH_SIZE
        )

        inserted += len(cleaned_batch)

        if inserted % 5000 == 0 or table in (
            "wards", "phase1_healthcare"
        ):
            print("Rows transferred:", f"{inserted:,}")

    # Spatial index.
    dst_cur.execute(sql.SQL("""
        CREATE INDEX {} ON public.{} USING GIST ({});
    """).format(
        sql.Identifier(table + "_geom_gix"),
        sql.Identifier(table),
        sql.Identifier(geom_col)
    ))

    # Useful attribute indexes.
    for candidate in (
        "feature_id", "service_id", "ward_id",
        "resolution", "h3_index", "category"
    ):
        if candidate in col_names:
            index_name = table + "_" + candidate + "_idx"

            dst_cur.execute(sql.SQL("""
                CREATE INDEX {} ON public.{} ({});
            """).format(
                sql.Identifier(index_name),
                sql.Identifier(table),
                sql.Identifier(candidate)
            ))

    dst_cur.execute(
        sql.SQL("ANALYZE public.{}").format(
            sql.Identifier(table)
        )
    )

    # Validate count, geometry SRID and extent in destination.
    dst_cur.execute(sql.SQL("""
        SELECT
            COUNT(*),
            COUNT(*) FILTER (
                WHERE ST_SRID({geom}) = 4326
            ),
            ST_Extent({geom})
        FROM public.{table}
    """).format(
        geom=sql.Identifier(geom_col),
        table=sql.Identifier(table)
    ))

    result = dst_cur.fetchone()

    print("Destination rows:", f"{result[0]:,}")
    print("EPSG:4326 geometries:", f"{result[1]:,}")
    print("Destination extent:", result[2])

    if result[0] != inserted:
        raise RuntimeError(
            f"Count mismatch for {table}: "
            f"inserted {inserted}, found {result[0]}"
        )

    if result[1] != result[0]:
        raise RuntimeError(
            f"Not all geometries in {table} have SRID 4326"
        )

    print("TRANSFER VERIFIED:", table)


def main():
    print("SOURCE:", SOURCE["dbname"], "port", SOURCE["port"])
    print("TARGET:", TARGET["dbname"], "port", TARGET["port"])

    src = psycopg2.connect(**SOURCE)
    dst = psycopg2.connect(**TARGET)

    try:
        src_cur = src.cursor()
        dst_cur = dst.cursor()

        dst_cur.execute("CREATE EXTENSION IF NOT EXISTS postgis;")
        dst.commit()

        try:
            for table in TABLES:
                transfer_table(src_cur, dst_cur, table)

            dst.commit()

        except Exception:
            dst.rollback()
            raise

        print("\n" + "=" * 60)
        print("ALL TABLES TRANSFERRED AND VERIFIED")
        print("=" * 60)

        dst_cur.close()
        src_cur.close()

    finally:
        src.close()
        dst.close()


if __name__ == "__main__":
    main()
