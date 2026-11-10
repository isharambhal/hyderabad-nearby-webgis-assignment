# Hyderabad Nearby Services WebGIS (fresh start)

This project starts from the supplied `data/wards.geojson` only. It does **not** assume that any previous database, service imports, Flask application, or GeoServer workspace exists. The supplied file contains 145 Polygon features, has a `Name` property (for example, `Ward 91 Khairatabad`), and its coordinates are longitude/latitude around Hyderabad. Because the file has no declared CRS, the workflow treats it as standard GeoJSON WGS 84 (`EPSG:4326`); its coordinate range is consistent with Hyderabad. Confirm the source metadata if you know it was exported in another CRS.

## Architecture

- PostgreSQL + PostGIS stores wards and service points.
- Flask provides the search API and serves the frontend.
- Leaflet renders ward polygons, OSM basemap tiles, chosen search location, service markers, and distance-sorted results.
- GeoServer can publish the same PostGIS tables as WMS/WFS layers for reuse in GIS clients. The frontend's search API uses Flask/PostGIS; GeoServer is not required for the search to work.

## Requirements

- Windows 10/11 (steps below use PowerShell), or equivalent shell commands on another OS.
- Python 3.11 recommended.
- PostgreSQL 15 or 16 with PostGIS installed for the same PostgreSQL major version.
- GeoServer 2.26.x or a compatible current stable version (optional for the core app; required if you need published OGC layers).
- Internet connection for Leaflet CDN assets and OpenStreetMap tiles. For production, review the tile provider's usage policy and use a suitable provider.

## 1. Install and create the database

1. Install PostgreSQL from https://www.postgresql.org/download/windows/ and install the matching PostGIS extension using the Stack Builder/PostGIS installer.
2. Open pgAdmin or SQL Shell (`psql`) and create a fresh database:

```sql
CREATE DATABASE hyderabad_webgis;
```

3. Connect to `hyderabad_webgis`, then run `sql/schema.sql`. In pgAdmin, open Query Tool for this database, open the file, and execute it. Alternatively, from PowerShell with `psql` on PATH:

```powershell
psql -U postgres -d hyderabad_webgis -f sql/schema.sql
```

If `CREATE EXTENSION postgis` fails, PostGIS is not installed for that PostgreSQL installation. Install the matching PostGIS package and retry.

## 2. Configure Python

From PowerShell, enter the project folder:

```powershell
cd path\to\hyderabad-nearby-webgis
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
notepad .env
```

Set `DB_PASSWORD` in `.env` to the password for your PostgreSQL user. Keep `.env` private and do not commit it to Git. If your database username, port, or name differs, change those values too.

## 3. Import your ward GeoJSON

The provided file has already been copied to `data/wards.geojson`. The importer reads the feature names and retains all source properties in a JSONB column.

```powershell
python scripts/import_wards.py
```

Expected output should report 145 imported ward polygons, assuming every feature has polygon geometry. The script replaces existing rows in the `wards` table, so only run it when you intend to refresh the ward layer.

Optional database checks:

```sql
SELECT COUNT(*) FROM wards;
SELECT ward_name FROM wards ORDER BY ward_name LIMIT 10;
SELECT ST_SRID(geom), GeometryType(geom), COUNT(*) FROM wards GROUP BY 1,2;
SELECT COUNT(*) FROM wards WHERE NOT ST_IsValid(geom);
```

Expected: 145 rows; SRID 4326; `MULTIPOLYGON`; ideally zero invalid geometries. If invalid geometries are reported, inspect them before applying a repair such as `ST_MakeValid`; do not silently alter source geometry without checking.

## 4. Import service locations

Only the ward GeoJSON was provided for this fresh project. **It does not contain hospitals, pharmacies, schools, police stations, ATMs, fuel stations, parks, or their locations.** You must supply a service CSV before nearby searches can return results.

Use `data/services_template.csv` as the column template. Required columns:

- `name`: facility name
- `category`: e.g. `Hospital`, `Pharmacy`, `Police Station`, `ATM`, `School`, `Fuel Station`, `Park`
- `latitude`, `longitude`: decimal degrees in WGS 84 (EPSG:4326)

Optional columns: `subcategory`, `address`, `phone`, `opening_hours`, `source`, `source_id`. Keep category spellings consistent; filtering uses the stored text. Do not put projected easting/northing values in latitude/longitude columns.

Once your populated CSV is saved, for example as `data/hyderabad_services.csv`, run:

```powershell
python scripts/import_services.py data/hyderabad_services.csv
```

The importer skips rows with missing names/categories, nonnumeric coordinates, or coordinates outside valid latitude/longitude ranges. It prints a count of inserted and skipped rows. It appends records; to replace a full import, first back up the table and then run `TRUNCATE services RESTART IDENTITY;` in the database before importing again.

If your source is GeoJSON rather than CSV, convert it to CSV with the required fields or extend the importer. Confirm whether the source coordinates are longitude/latitude; many GIS exports can use another CRS. Reproject coordinates to EPSG:4326 before importing. If you have coordinates in a projected CRS, use a GIS tool or `pyproj.Transformer` with the correct source EPSG code; do not guess the source CRS.

## 5. Run the application

With PostgreSQL running, the schema installed, and `.env` configured:

```powershell
python backend/app.py
```

Open http://127.0.0.1:5000. The ward boundaries should load even before service data is imported. If no services are in the database, the app explains that service points must be imported. Browser geolocation generally requires HTTPS or `localhost`/loopback; use the map click or coordinate fields if permission is denied.

Useful API endpoints:

- `GET /api/health` — database/PostGIS and row counts
- `GET /api/wards` — GeoJSON ward FeatureCollection
- `GET /api/categories` — categories and subcategories currently in the database
- `GET /api/search?lat=17.385&lon=78.4867&category=Hospital&mode=both&radius=5000&limit=10` — distance-sorted search

Search modes:
- `radius`: return matching services within `radius` metres, capped by `limit`.
- `nearest`: return the nearest `limit` matches at any distance.
- `both`: require the service to be within the radius and return up to `limit` nearest results.

The backend uses `ST_Distance(geom::geography, origin::geography)` and `ST_DWithin` for metre-based ellipsoidal distance calculations. PostGIS GIST indexes support spatial filtering. A search radius is limited to 100,000 metres and nearest-N to 100 results to keep requests manageable.

## 6. GeoServer configuration (publish the PostGIS layers)

GeoServer is optional for the core application but is included in the intended architecture when you need WMS/WFS layers.

1. Install/run GeoServer and open its web administration page, usually `http://localhost:8080/geoserver`.
2. Sign in with your administrator credentials. Use a strong password and do not expose the admin console publicly.
3. Go to **Workspaces → Add new workspace**. Name: `hyderabad`; namespace URI: `https://example.org/hyderabad` (this is an identifier, not a website that needs to exist). Submit.
4. Go to **Stores → Add new Store → PostGIS**. Workspace: `hyderabad`; Data Source Name: `hyderabad_db`; host: `localhost` if GeoServer runs directly on the same machine, port `5432`, database `hyderabad_webgis`, schema `public`, user and password from your PostgreSQL setup. If GeoServer runs in Docker, `localhost` refers to the container itself; use the database service/container hostname instead.
5. Save the store. On the resulting layer list, publish `wards` and `services` if present. The `services` layer will be empty until service CSV data is imported.
6. For each published layer, check the native SRS is `EPSG:4326`. Set the declared SRS to `EPSG:4326`, then use **Compute from data** for the bounding boxes and save. Inspect the preview to confirm it appears in Hyderabad.
7. Test WMS with a GetCapabilities request: `http://localhost:8080/geoserver/hyderabad/wms?service=WMS&request=GetCapabilities`. WFS is available at `http://localhost:8080/geoserver/hyderabad/ows?service=WFS&request=GetCapabilities`.

Layer names should be `hyderabad:wards` and `hyderabad:services`. The current frontend renders the ward layer from Flask's GeoJSON endpoint and service points from the search API, so a GeoServer outage does not prevent those features from working. If you specifically want GeoServer-rendered WMS tiles in Leaflet, replace/add a Leaflet `L.tileLayer.wms(...)` layer using the layer name above and the local GeoServer URL; for a public deployment, configure CORS/proxying and authentication safely.

## 7. End-to-end test checklist

1. Open `/api/health`; it should return `status: ok`, a PostGIS version, ward count 145, and current service count.
2. Open `/api/wards`; it should return a FeatureCollection with 145 features.
3. Load the app; the map should zoom to ward boundaries.
4. Click inside Hyderabad on the map; latitude and longitude fields should update.
5. Try invalid coordinates such as latitude `100`; the UI should show a validation error.
6. Test geolocation and deny permission once; the app should explain how to continue manually.
7. Import a verified service CSV and reload the app; categories should populate dynamically.
8. Search for a category in radius mode; results should be distance-sorted and markers should appear.
9. Click a result card; the map should pan to and open that marker. Click a marker; its popup should show details.
10. Test nearest-N mode, radius mode, and combined mode. Try a category/radius combination with no matches.
11. If using GeoServer, check WMS/WFS GetCapabilities and preview both published layers.

## Troubleshooting

- **`password authentication failed`:** correct `DB_USER`/`DB_PASSWORD` in `.env`; restart Flask after edits.
- **`database does not exist`:** create `hyderabad_webgis` and run `sql/schema.sql` in that database.
- **`PostGIS_Full_Version` / extension error:** install the PostGIS package matching your PostgreSQL version and execute `CREATE EXTENSION postgis;` in the project database.
- **No wards shown:** check `/api/health`, run the ward importer, and inspect Flask's terminal output.
- **No services found:** expected until a real service CSV has been imported. Ward boundaries alone do not provide facility points.
- **Coordinates look wrong:** confirm the source CRS. GeoJSON coordinates should be `[longitude, latitude]` in EPSG:4326. Never swap latitude and longitude.
- **Search returns 400:** use decimal-degree coordinates, radius 1–100000 metres, nearest-N 1–100, and a supported mode.
- **Geolocation denied:** permit location access for localhost or use map click/manual coordinates.
- **Leaflet map is blank:** check internet access, CDN loading, browser console errors, and whether `#map` has a defined height.
- **GeoServer cannot connect to PostGIS:** check host networking, database credentials, PostgreSQL listen/access rules, and firewall. `localhost` inside a container is the container, not the Windows host.
- **GeoServer layer preview is empty:** confirm the table has rows, native/declared SRS is 4326, and bounding boxes were computed.

## Security and deployment notes

This is a local development starter. Before public deployment, disable Flask debug mode, use HTTPS, restrict database privileges, configure allowed origins/reverse proxying, add rate limiting and request logging, and use an approved map-tile provider. Do not expose PostgreSQL or the GeoServer administration interface to the public internet.
