
import json
from pathlib import Path

import networkx as nx
import numpy as np
import pandas as pd
import osmnx as ox

from shapely.geometry import shape, mapping


# --------------------------------------------------
# 1. Project paths
# --------------------------------------------------

ROOT = Path(__file__).resolve().parents[1]

BASE = ROOT / "data" / "raw" / "phase1"
WALK_DIR = BASE / "walking_network"

BUFFER_FILE = BASE / "study_area_buffer_2km.geojson"
OUTPUT_DIR = WALK_DIR / "processed"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

osm_files = list(WALK_DIR.glob("*.osm/*.osm"))

if len(osm_files) != 1:
    raise FileNotFoundError(
        f"Expected one extracted OSM XML file, found {len(osm_files)}"
    )

OSM_FILE = osm_files[0]


# --------------------------------------------------
# 2. Read the study-area buffer
# --------------------------------------------------

print("\nSTEP 1: Reading study area...")

with open(BUFFER_FILE, "r", encoding="utf-8") as f:
    boundary_data = json.load(f)

polygon = shape(boundary_data["features"][0]["geometry"])

print("Buffer geometry:", polygon.geom_type)
print("OSM source:", OSM_FILE.name)


# --------------------------------------------------
# 3. Read OSM XML locally
# --------------------------------------------------

print("\nSTEP 2: Building graph from local OSM XML...")
print("No internet or Overpass request is required.")

G = ox.graph_from_xml(
    filepath=OSM_FILE,
    bidirectional=True,
    simplify=False,
    retain_all=True
)

print("Original nodes:", len(G.nodes))
print("Original edges:", len(G.edges))


# --------------------------------------------------
# 4. Filter for pedestrian-accessible ways
# --------------------------------------------------

print("\nSTEP 3: Filtering walking network...")

excluded_highways = {
    "abandoned",
    "bus_guideway",
    "construction",
    "cycleway",
    "motor",
    "no",
    "planned",
    "platform",
    "proposed",
    "raceway",
    "razed",
    "rest_area",
    "services"
}


def tag_values(value):
    if value is None:
        return []

    if isinstance(value, (list, tuple, set)):
        return [str(v).lower() for v in value]

    return [str(value).lower()]


edges_to_remove = []

for u, v, key, data in G.edges(keys=True, data=True):

    highway = tag_values(data.get("highway"))

    excluded = (
        not highway
        or all(h in excluded_highways for h in highway)
        or "yes" in tag_values(data.get("area"))
        or "private" in tag_values(data.get("access"))
        or "no" in tag_values(data.get("foot"))
        or "private" in tag_values(data.get("service"))
        or "separate" in tag_values(data.get("sidewalk"))
        or "separate" in tag_values(data.get("sidewalk:both"))
        or "separate" in tag_values(data.get("sidewalk:left"))
        or "separate" in tag_values(data.get("sidewalk:right"))
    )

    if excluded:
        edges_to_remove.append((u, v, key))

G.remove_edges_from(edges_to_remove)
G.remove_nodes_from(list(nx.isolates(G)))

print("Filtered out edges:", len(edges_to_remove))
print("Walking nodes:", len(G.nodes))
print("Walking edges:", len(G.edges))

if len(G.edges) == 0:
    raise RuntimeError("No walking edges remain after filtering.")


# --------------------------------------------------
# 5. Clip network to the 2 km buffered polygon
# --------------------------------------------------

print("\nSTEP 4: Clipping network to study area...")

G = ox.truncate.truncate_graph_polygon(
    G,
    polygon,
    truncate_by_edge=True
)

print("Clipped nodes:", len(G.nodes))
print("Clipped edges:", len(G.edges))

if len(G.edges) == 0:
    raise RuntimeError("No edges remain after clipping.")


# --------------------------------------------------
# 6. Simplify network topology
# --------------------------------------------------

print("\nSTEP 5: Simplifying walking network...")

G = ox.simplification.simplify_graph(G)

print("Final nodes:", len(G.nodes))
print("Final edges:", len(G.edges))


# --------------------------------------------------
# 7. Save GraphML
# --------------------------------------------------

print("\nSTEP 6: Saving GraphML...")

graph_file = OUTPUT_DIR / "walking_network.graphml"

ox.io.save_graphml(
    G,
    filepath=graph_file
)


# --------------------------------------------------
# 8. Export nodes and edges as GeoJSON
# --------------------------------------------------

print("\nSTEP 7: Exporting GIS layers...")

nodes_gdf, edges_gdf = ox.convert.graph_to_gdfs(G)


def clean_value(value):

    if value is None:
        return None

    if isinstance(value, (list, tuple, set)):
        return [clean_value(v) for v in value]

    if isinstance(value, np.generic):
        value = value.item()

    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass

    if isinstance(value, (str, int, float, bool)):
        return value

    return str(value)


def save_geojson(gdf, output_path):

    features = []

    for idx, row in gdf.iterrows():

        geom = row.geometry

        if geom is None or geom.is_empty:
            continue

        properties = {
            str(column): clean_value(value)
            for column, value in row.items()
            if column != "geometry"
        }

        if isinstance(idx, tuple):
            properties["u"] = clean_value(idx[0])
            properties["v"] = clean_value(idx[1])
            properties["key"] = clean_value(idx[2])
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


node_file = OUTPUT_DIR / "walking_nodes.geojson"
edge_file = OUTPUT_DIR / "walking_edges.geojson"

node_count = save_geojson(nodes_gdf, node_file)
edge_count = save_geojson(edges_gdf, edge_file)


# --------------------------------------------------
# 9. Save processing summary
# --------------------------------------------------

summary = {
    "source": "BBBike OpenStreetMap XML extract",
    "source_file": OSM_FILE.name,
    "study_area": "Hyderabad - Ward 106 and Ward 109",
    "buffer_distance_metres": 2000,
    "crs": "EPSG:4326",
    "network_type": "Walking",
    "original_nodes": int(len(nodes_gdf)),
    "final_nodes": int(node_count),
    "final_edges": int(edge_count),
    "graphml": str(graph_file.relative_to(ROOT)),
    "nodes_geojson": str(node_file.relative_to(ROOT)),
    "edges_geojson": str(edge_file.relative_to(ROOT))
}

with open(
    OUTPUT_DIR / "walking_network_summary.json",
    "w",
    encoding="utf-8"
) as f:
    json.dump(summary, f, indent=4)


print("\n====================================")
print("WALKING NETWORK PROCESSING COMPLETE")
print("====================================")
print("Nodes:", node_count)
print("Edges:", edge_count)
print("GraphML:", graph_file)
print("Nodes GeoJSON:", node_file)
print("Edges GeoJSON:", edge_file)
print("Summary:", OUTPUT_DIR / "walking_network_summary.json")
