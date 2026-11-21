import json
import networkx as nx
import math
from pathlib import Path

import osmnx as ox
import pandas as pd
from shapely.geometry import shape, mapping

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "data" / "raw" / "phase1"
BUFFER_FILE = BASE / "study_area_buffer_2km.geojson"
OUT = BASE / "walking_network"

OUT.mkdir(parents=True, exist_ok=True)

print("Reading the existing 2 km buffered study area...")
with open(BUFFER_FILE, "r", encoding="utf-8") as f:
    data = json.load(f)

polygon = shape(data["features"][0]["geometry"])

# Use an alternative public Overpass endpoint.
ox.settings.overpass_url = "https://maps.mail.ru/osm/tools/overpass/api"
ox.settings.overpass_rate_limit = False
ox.settings.requests_timeout = 300
ox.settings.use_cache = True
ox.settings.log_console = True
ox.settings.http_user_agent = "HyderabadNearbyWebGISAssignment/1.0"

print("Downloading walking network in 3 x 3 sections...")

minx, miny, maxx, maxy = polygon.bounds

rows = 3
cols = 3
dx = (maxx - minx) / cols
dy = (maxy - miny) / rows

graphs = []

for r in range(rows):
    for c in range(cols):
        west = minx + c * dx - 0.001
        east = minx + (c + 1) * dx + 0.001
        south = miny + r * dy - 0.001
        north = miny + (r + 1) * dy + 0.001

        print(f"\nDownloading section {r * cols + c + 1} of 9...")

        tile_graph = ox.graph_from_bbox(
            bbox=(west, south, east, north),
            network_type="walk",
            simplify=False,
            retain_all=True,
            truncate_by_edge=True
        )

        graphs.append(tile_graph)

        print(
            "Section nodes:", len(tile_graph.nodes),
            "| edges:", len(tile_graph.edges)
        )

print("\nCombining network sections...")

G = nx.compose_all(graphs)

print("Clipping network to the buffered study area...")

G = ox.truncate.truncate_graph_polygon(
    G,
    polygon,
    retain_all=True,
    truncate_by_edge=True
)

print("Simplifying the combined walking network...")

G = ox.simplification.simplify_graph(G)

print("Combined nodes:", len(G.nodes))
print("Combined edges:", len(G.edges))

print("Converting network into GIS layers...")
nodes, edges = ox.graph_to_gdfs(G)

def clean_value(value):
    if value is None:
        return None

    if isinstance(value, (list, tuple)):
        return [clean_value(v) for v in value]

    if isinstance(value, dict):
        return {str(k): clean_value(v) for k, v in value.items()}

    if hasattr(value, "item"):
        try:
            value = value.item()
        except (ValueError, AttributeError):
            pass

    if isinstance(value, float) and math.isnan(value):
        return None

    if isinstance(value, (str, int, float, bool)):
        return value

    try:
        missing = pd.isna(value)
        if isinstance(missing, bool) and missing:
            return None
    except (TypeError, ValueError):
        pass

    return str(value)

def save_geojson(gdf, output_path, include_index=False):
    features = []

    for idx, row in gdf.iterrows():
        geom = row.geometry

        if geom is None or geom.is_empty:
            continue

        properties = {
            str(k): clean_value(v)
            for k, v in row.items()
            if k != "geometry"
        }

        if include_index:
            if isinstance(idx, tuple):
                properties.update({
                    "u": clean_value(idx[0]),
                    "v": clean_value(idx[1]),
                    "key": clean_value(idx[2])
                })
            else:
                properties["osmid"] = clean_value(idx)

        features.append({
            "type": "Feature",
            "properties": properties,
            "geometry": mapping(geom)
        })

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({
            "type": "FeatureCollection",
            "features": features
        }, f, ensure_ascii=False)

    return len(features)

node_file = OUT / "walking_nodes.geojson"
edge_file = OUT / "walking_edges.geojson"
graph_file = OUT / "walking_network.graphml"

node_count = save_geojson(nodes, node_file, include_index=True)
edge_count = save_geojson(edges, edge_file, include_index=True)

ox.save_graphml(G, filepath=graph_file)

summary = {
    "source": "OpenStreetMap via Overpass API",
    "overpass_endpoint": ox.settings.overpass_url,
    "network_type": "walk",
    "buffer": "2 km",
    "nodes": node_count,
    "edges": edge_count,
    "crs": "EPSG:4326",
    "files": [
        str(node_file.relative_to(ROOT)),
        str(edge_file.relative_to(ROOT)),
        str(graph_file.relative_to(ROOT))
    ]
}

with open(OUT / "walking_network_summary.json", "w", encoding="utf-8") as f:
    json.dump(summary, f, indent=4)

print("\nWALKING NETWORK DOWNLOAD COMPLETE")
print("Nodes:", node_count)
print("Edges:", edge_count)
print("Saved:", OUT)
print("GraphML:", graph_file)
