"""Import the bundled WGS84 ward GeoJSON into PostGIS."""
import json, os, sys
from pathlib import Path
import psycopg2
from psycopg2.extras import Json
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / '.env')
GEOJSON = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / 'data' / 'wards.geojson'

def db():
    return psycopg2.connect(host=os.getenv('DB_HOST','localhost'), port=os.getenv('DB_PORT','5432'),
        dbname=os.getenv('DB_NAME','hyderabad_webgis'), user=os.getenv('DB_USER','postgres'),
        password=os.getenv('DB_PASSWORD',''))

with open(GEOJSON, encoding='utf-8') as f:
    fc = json.load(f)
if fc.get('type') != 'FeatureCollection':
    raise SystemExit('Input must be a GeoJSON FeatureCollection.')
features = fc.get('features', [])
if not features:
    raise SystemExit('No features found in GeoJSON.')

with db() as conn, conn.cursor() as cur:
    cur.execute('TRUNCATE TABLE wards RESTART IDENTITY')
    inserted = 0
    for i, feat in enumerate(features, start=1):
        geom = feat.get('geometry')
        if not geom or geom.get('type') not in ('Polygon','MultiPolygon'):
            print(f'Skipping feature {i}: missing or unsupported polygon geometry')
            continue
        props = feat.get('properties') or {}
        name = str(props.get('Name') or props.get('name') or f'Ward {i}').strip()
        source_id = str(props.get('_id') or props.get('ward_id') or '') or None
        cur.execute('''INSERT INTO wards (ward_name, source_id, properties, geom)
          VALUES (%s, %s, %s, ST_Multi(ST_SetSRID(ST_GeomFromGeoJSON(%s),4326)))''',
          (name, source_id, Json(props), json.dumps(geom)))
        inserted += 1
    cur.execute('SELECT COUNT(*), ST_Extent(geom)::text FROM wards')
    print(f'Imported {inserted} ward polygons. Database summary: {cur.fetchone()}')
