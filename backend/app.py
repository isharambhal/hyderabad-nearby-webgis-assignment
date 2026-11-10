
import os
import json
import math
import urllib.parse
import urllib.request
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv


# =========================================================
# PATHS AND FLASK CONFIGURATION
# =========================================================

ROOT = Path(__file__).resolve().parents[1]
FRONTEND_DIR = ROOT / "frontend"

load_dotenv(ROOT / ".env")

app = Flask(__name__)

# Explicitly serve the existing frontend files.
# This avoids relying on Flask's default static directory.
@app.get("/")
def index():
    return send_from_directory(str(FRONTEND_DIR), "index.html")


@app.get("/style.css")
def serve_css():
    return send_from_directory(str(FRONTEND_DIR), "style.css")


@app.get("/app.js")
def serve_js():
    return send_from_directory(str(FRONTEND_DIR), "app.js")


# =========================================================
# DATABASE CONNECTION
# =========================================================

def connect():
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", "5432"),
        dbname=os.getenv("DB_NAME", "hyderabad_webgis"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", ""),
    )


# =========================================================
# HEALTH CHECK
# =========================================================

@app.get("/api/health")
def health():
    try:
        with connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT
                        PostGIS_Full_Version(),
                        (SELECT COUNT(*) FROM wards),
                        (SELECT COUNT(*) FROM services)
                """)
                version, wards_count, services_count = cursor.fetchone()

        return jsonify(
            status="ok",
            postgis=version,
            wards=wards_count,
            services=services_count,
        )

    except Exception as exc:
        app.logger.exception("Database health check failed")
        return jsonify(
            status="error",
            message="Cannot connect to PostGIS. Check .env and database setup.",
            detail=str(exc),
        ), 503


# =========================================================
# WARD DATA
# =========================================================

@app.get("/api/wards")
def wards():
    try:
        with connect() as connection:
            with connection.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("""
                    SELECT
                        ward_id,
                        ward_name,
                        ST_AsGeoJSON(geom)::json AS geometry
                    FROM wards
                    ORDER BY ward_name
                """)
                rows = cursor.fetchall()

        features = []

        for row in rows:
            features.append({
                "type": "Feature",
                "id": row["ward_id"],
                "properties": {
                    "ward_id": row["ward_id"],
                    "Name": row["ward_name"],
                },
                "geometry": row["geometry"],
            })

        return jsonify(
            type="FeatureCollection",
            features=features,
        )

    except Exception as exc:
        app.logger.exception("Ward layer request failed")
        return jsonify(
            error="Ward layer unavailable",
            detail=str(exc),
        ), 503


# =========================================================
# SERVICE CATEGORIES
# =========================================================

@app.get("/api/categories")
def categories():
    try:
        with connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT DISTINCT category
                    FROM services
                    ORDER BY category
                """)
                category_list = [row[0] for row in cursor.fetchall()]

                cursor.execute("""
                    SELECT DISTINCT category, subcategory
                    FROM services
                    WHERE subcategory IS NOT NULL
                      AND subcategory <> ''
                    ORDER BY category, subcategory
                """)
                subcategory_list = [
                    {
                        "category": row[0],
                        "subcategory": row[1],
                    }
                    for row in cursor.fetchall()
                ]

        return jsonify(
            categories=category_list,
            subcategories=subcategory_list,
        )

    except Exception as exc:
        app.logger.exception("Category request failed")
        return jsonify(
            error="Could not load categories",
            detail=str(exc),
        ), 503


# =========================================================
# OPENSTREETMAP LIVE SEARCH CONFIGURATION
# =========================================================

OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
]

OSM_FILTERS = {
    "Hospital": [("amenity", "hospital")],
    "Clinic": [
        ("amenity", "clinic"),
        ("amenity", "doctors"),
    ],
    "Pharmacy": [("amenity", "pharmacy")],
    "Police Station": [("amenity", "police")],
    "ATM": [("amenity", "atm")],
    "Bank": [("amenity", "bank")],
    "School": [
        ("amenity", "school"),
        ("amenity", "college"),
        ("amenity", "university"),
        ("amenity", "kindergarten"),
    ],
    "Fuel Station": [("amenity", "fuel")],
    "Park": [("leisure", "park")],
    "Library": [("amenity", "library")],
    "Post Office": [("amenity", "post_office")],
    "Fire Station": [("amenity", "fire_station")],
    "Place of Worship": [("amenity", "place_of_worship")],
}


# =========================================================
# DISTANCE CALCULATION
# =========================================================

def haversine_m(lat1, lon1, lat2, lon2):
    """Calculate distance in metres between WGS84 coordinates."""
    earth_radius = 6371000

    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(p1)
        * math.cos(p2)
        * math.sin(delta_lon / 2) ** 2
    )

    return 2 * earth_radius * math.asin(
        min(1, math.sqrt(a))
    )


# =========================================================
# FETCH NEARBY SERVICES FROM OPENSTREETMAP
# =========================================================

def fetch_osm_services(lat, lon, radius, category):
    """Fetch mapped facilities around a supplied coordinate."""

    if category:
        filters = OSM_FILTERS.get(category, [])
    else:
        filters = [
            item
            for category_filters in OSM_FILTERS.values()
            for item in category_filters
        ]

    statements = []

    for key, value in filters:
        safe_key = key.replace('"', "")
        safe_value = value.replace('"', "")

        statements.append(
            f'nwr(around:{int(radius)},{lat},{lon})'
            f'["{safe_key}"="{safe_value}"];'
        )

    query = (
        "[out:json][timeout:40];("
        + "".join(statements)
        + ");out center tags;"
    )

    payload = None
    errors = []

    for endpoint in OVERPASS_URLS:
        req = urllib.request.Request(
            endpoint,
            data=urllib.parse.urlencode({
                "data": query
            }).encode("utf-8"),
            headers={
                "User-Agent": "HyderabadNearbyServicesWebGIS/1.0",
                "Content-Type": "application/x-www-form-urlencoded",
            },
        )

        try:
            with urllib.request.urlopen(req, timeout=50) as response:
                payload = json.loads(
                    response.read().decode("utf-8")
                )
            break

        except Exception as exc:
            errors.append(f"{endpoint}: {exc}")

    if payload is None:
        raise RuntimeError(
            "All OpenStreetMap search endpoints failed. "
            + " | ".join(errors)
        )

    results = []
    seen = set()

    for element in payload.get("elements", []):
        tags = element.get("tags", {})
        point = element.get("center", {})

        item_lat = element.get("lat", point.get("lat"))
        item_lon = element.get("lon", point.get("lon"))

        if item_lat is None or item_lon is None:
            continue

        source_id = f"{element.get('type')}/{element.get('id')}"

        if source_id in seen:
            continue

        seen.add(source_id)

        item_category = next(
            (
                name
                for name, options in OSM_FILTERS.items()
                if any(tags.get(key) == value for key, value in options)
            ),
            "Other",
        )

        address_parts = [
            tags.get("addr:housenumber"),
            tags.get("addr:street"),
            tags.get("addr:suburb"),
            tags.get("addr:city"),
        ]

        address = ", ".join(
            part for part in address_parts if part
        )

        results.append({
            "service_id": source_id,
            "name": tags.get("name") or f"{item_category} (unnamed)",
            "category": item_category,
            "subcategory": (
                tags.get("healthcare")
                or tags.get("school")
                or tags.get("amenity", "")
            ),
            "address": address,
            "phone": tags.get("phone") or tags.get("contact:phone", ""),
            "opening_hours": tags.get("opening_hours", ""),
            "latitude": float(item_lat),
            "longitude": float(item_lon),
            "distance_m": round(
                haversine_m(
                    lat,
                    lon,
                    float(item_lat),
                    float(item_lon),
                ),
                1,
            ),
            "source": "OpenStreetMap",
        })

    return results


# =========================================================
# NEARBY SEARCH API
# =========================================================


@app.get("/api/search")
def search():
    # Read and validate the user's location.
    try:
        lat = float(request.args.get("lat", ""))
        lon = float(request.args.get("lon", ""))

        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            raise ValueError

    except (TypeError, ValueError):
        return jsonify(
            error="Enter valid latitude and longitude."
        ), 400

    # Read search filters.
    category = request.args.get("category", "").strip()
    subcategory = request.args.get("subcategory", "").strip()
    mode = request.args.get("mode", "both").strip().lower()

    try:
        radius = float(request.args.get("radius", "5000"))
        limit = int(request.args.get("limit", "10"))

        if not 1 <= radius <= 100000:
            return jsonify(
                error="Radius must be between 1 and 100000 metres."
            ), 400

        if not 1 <= limit <= 100:
            return jsonify(
                error="Limit must be between 1 and 100."
            ), 400

        if mode not in ("radius", "nearest", "both"):
            return jsonify(error="Invalid search mode."), 400

    except (TypeError, ValueError):
        return jsonify(
            error="Radius and limit must be numeric."
        ), 400

    try:
        # Build safe SQL filters.
        conditions = []
        params = []

        if category:
            conditions.append("LOWER(category) = LOWER(%s)")
            params.append(category)

        if subcategory:
            conditions.append("LOWER(subcategory) = LOWER(%s)")
            params.append(subcategory)

        # Radius and both modes use the chosen radius.
        # Nearest mode searches within 100 km and returns
        # the closest matching records.
        if mode in ("radius", "both"):
            search_distance = radius
        else:
            search_distance = 100000

        conditions.append("""
            ST_DWithin(
                geom::geography,
                ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography,
                %s
            )
        """)
        params.extend([lon, lat, search_distance])

        where_sql = " AND ".join(conditions)

        # Radius mode returns all matching records up to a
        # safety cap. Other modes return the nearest N.
        result_limit = 500 if mode == "radius" else limit

        sql = f"""
            SELECT
                service_id,
                name,
                category,
                subcategory,
                address,
                phone,
                opening_hours,
                latitude,
                longitude,
                ROUND(
                    ST_Distance(
                        geom::geography,
                        ST_SetSRID(
                            ST_MakePoint(%s, %s), 4326
                        )::geography
                    )::numeric,
                    1
                ) AS distance_m
            FROM services
            WHERE {where_sql}
            ORDER BY distance_m ASC
            LIMIT %s
        """

        # The SELECT distance parameters appear before WHERE
        # parameters in the SQL statement.
        query_params = [lon, lat] + params + [result_limit]

        with connect() as conn:
            with conn.cursor(
                cursor_factory=RealDictCursor
            ) as cursor:
                cursor.execute(sql, query_params)
                rows = cursor.fetchall()

        results = []

        for row in rows:
            item = dict(row)
            item["distance_m"] = float(item["distance_m"])
            item["source"] = "PostGIS"
            results.append(item)

        return jsonify(
            count=len(results),
            results=results,
            mode=mode,
            radius_m=radius,
            nearest_n=limit,
            source="PostGIS",
            message=(
                None if results else
                "No mapped services found in this search area. "
                "Try a larger radius or another category."
            ),
        )

    except Exception as exc:
        app.logger.exception("PostGIS nearby search failed")
        return jsonify(
            error="Could not retrieve nearby services from the database.",
            detail=str(exc),
        ), 500


# =========================================================
# GEOSERVER INFORMATION
# =========================================================

@app.get("/api/geoserver-info")
def geoserver_info():
    return jsonify(
        workspace="hyderabad",
        store="hyderabad_db",
        ward_layer="hyderabad:wards",
        service_layer="hyderabad:services",
        note=(
            "Configure these resources in GeoServer "
            "using the README instructions."
        ),
    )


# =========================================================
# RUN THE APPLICATION
# =========================================================

if __name__ == "__main__":
    app.run(
        host=os.getenv("FLASK_HOST", "127.0.0.1"),
        port=int(os.getenv("FLASK_PORT", "5002")),
        debug=False,
        use_reloader=False,
    )
