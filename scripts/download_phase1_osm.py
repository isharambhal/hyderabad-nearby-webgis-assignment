
import json
import time
from pathlib import Path

import osmnx as ox
import networkx as nx
from shapely.geometry import mapping, LineString

ROOT = Path(__file__).resolve().parents[1]
BUFFER_FILE = ROOT / "data/raw/phase1/study_area_buffer_2km.geojson"

OUT = ROOT / "data/raw/phase1"
HEALTH_DIR = OUT / "healthcare"
BUILD_DIR = OUT / "buildings"
NETWORK_DIR = OUT / "walking_network"

for folder in [HEALTH_DIR, BUILD_DIR, NETWORK_DIR]:
    folder.mkdir(parents=True, exist_ok=True)

ox.settings.use_cache = True
ox.settings.log_console = True
ox.settings.timeout = 300
ox.settings.requests_timeout = 300
ox.settings.overpass_rate_limit = True

def save_geojson(path, features):
    collection = {
        "type": "FeatureCollection",
        "features": features
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(collection, f, indent=2, default=str)

def convert_gdf(gdf):
    output = []

    for _, row in gdf.iterrows():
        geom = row.geometry

        if geom is None or geom.is_empty:
            continue

        properties = row.drop(labels=["geometry"]).to_dict()

        output.append({
            "type": "Feature",
            "geometry": mapping(geom),
            "properties": properties
        })

    return output

# Read the expanded study-area polygon without GeoPandas.
print("\n1. Reading expanded study area...")

with open(BUFFER_FILE, encoding="utf-8") as f:
    boundary = json.load(f)

from shapely.geometry import shape

polygon = shape(boundary["features"][0]["geometry"])

print("Boundary loaded.")
print("OSMnx version:", ox.__version__)

# 2. Healthcare features
print("\n2. Downloading healthcare features...")

health_tags = {
    "healthcare": True,
    "amenity": [
        "hospital", "clinic", "doctors",
        "pharmacy", "dentist"
    ]
}

health = ox.features_from_polygon(polygon, health_tags)

health_features = convert_gdf(health)

save_geojson(
    HEALTH_DIR / "healthcare_expanded.geojson",
    health_features
)

print("Healthcare OSM features:", len(health_features))

# 3. Building footprints
print("\n3. Downloading building footprints...")

buildings = ox.features_from_polygon(
    polygon,
    {"building": True}
)

building_features = convert_gdf(buildings)

save_geojson(
    BUILD_DIR / "buildings_expanded.geojson",
    building_features
)

print("Building features:", len(building_features))

# 4. Walking network
print("\n4. Downloading walking network...")

graph = ox.graph_from_polygon(
    polygon,
    network_type="walk",
    simplify=True,
    retain_all=True
)

nodes, edges = ox.graph_to_gdfs(
    graph,
    nodes=True,
    edges=True,
    fill_edge_geometry=True
)

node_features = convert_gdf(nodes)
edge_features = convert_gdf(edges)

save_geojson(
    NETWORK_DIR / "walking_nodes.geojson",
    node_features
)

save_geojson(
    NETWORK_DIR / "walking_edges.geojson",
    edge_features
)

print("Walking network nodes:", len(node_features))
print("Walking network edges:", len(edge_features))

# 5. Save download summary
summary = {
    "source": "OpenStreetMap",
    "study_area": "Two selected Hyderabad wards plus 2 km buffer",
    "buffer_file": str(BUFFER_FILE),
    "healthcare_features": len(health_features),
    "building_features": len(building_features),
    "walking_nodes": len(node_features),
    "walking_edges": len(edge_features),
    "network_type": "walk",
    "crs": "EPSG:4326"
}

with open(OUT / "download_summary.json", "w", encoding="utf-8") as f:
    json.dump(summary, f, indent=2)

print("\nDOWNLOAD SUMMARY")
print(json.dumps(summary, indent=2))
print("\nPhase 1 OSM download completed.")
