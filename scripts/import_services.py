"""Import service locations from CSV. Required columns: name,category,latitude,longitude.
Optional: subcategory,address,phone,opening_hours,source,source_id.
"""
import csv, os, sys
from pathlib import Path
import psycopg2
from dotenv import load_dotenv
ROOT=Path(__file__).resolve().parents[1]
load_dotenv(ROOT/'.env')
if len(sys.argv)<2: raise SystemExit('Usage: python scripts/import_services.py data/services.csv')
path=Path(sys.argv[1])
conn=psycopg2.connect(host=os.getenv('DB_HOST','localhost'),port=os.getenv('DB_PORT','5432'),dbname=os.getenv('DB_NAME','hyderabad_webgis'),user=os.getenv('DB_USER','postgres'),password=os.getenv('DB_PASSWORD',''))
required={'name','category','latitude','longitude'}
inserted=skipped=0
try:
  with conn, conn.cursor() as cur, path.open(newline='',encoding='utf-8-sig') as f:
    reader=csv.DictReader(f)
    missing=required-set(reader.fieldnames or [])
    if missing: raise SystemExit(f'CSV missing required columns: {", ".join(sorted(missing))}')
    for rownum,row in enumerate(reader,start=2):
      try:
        name=(row.get('name') or '').strip(); category=(row.get('category') or '').strip()
        lat=float(row['latitude']); lon=float(row['longitude'])
        if not name or not category or not (-90<=lat<=90) or not (-180<=lon<=180): raise ValueError('invalid name/category/coordinates')
        cur.execute('''INSERT INTO services(name,category,subcategory,address,phone,opening_hours,source,source_id,latitude,longitude,geom)
          VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,ST_SetSRID(ST_MakePoint(%s,%s),4326))''',
          (name,category,(row.get('subcategory') or '').strip() or None,(row.get('address') or '').strip() or None,
           (row.get('phone') or '').strip() or None,(row.get('opening_hours') or '').strip() or None,
           (row.get('source') or '').strip() or None,(row.get('source_id') or '').strip() or None,lat,lon,lon,lat))
        inserted+=1
      except (ValueError,KeyError) as e:
        print(f'Skipping CSV row {rownum}: {e}'); skipped+=1
  print(f'Import complete: {inserted} inserted, {skipped} skipped.')
finally: conn.close()
