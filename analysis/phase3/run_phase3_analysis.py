
import os
import json
import csv
import math
import random
from pathlib import Path

import h3
import networkx as nx
import numpy as np
import osmnx as ox
import psycopg2

from dotenv import load_dotenv
from psycopg2.extras import execute_values
from pyproj import Transformer
from shapely.geometry import (
    shape, mapping, Point, Polygon, MultiPoint, LineString
)
from shapely.ops import transform as geom_transform, unary_union
from shapely import wkb
from shapely.strtree import STRtree


# ============================================================
# 1. PATHS, SETTINGS, AND DATABASE
# ============================================================

ROOT = Path(__file__).resolve().parents[2]

STUDY_FILE = ROOT / "analysis" / "study_area" / "study_area.geojson"
WARDS_FILE = ROOT / "analysis" / "study_area" / "selected_wards.geojson"
GRAPH_FILE = (
    ROOT / "data" / "raw" / "phase1" / "walking_network"
    / "processed" / "walking_network.graphml"
)

OUTPUT = ROOT / "analysis" / "phase3"
OUTPUT.mkdir(parents=True, exist_ok=True)

load_dotenv(ROOT / ".env")

DB = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": os.getenv("DB_PORT", "5432"),
    "dbname": os.getenv("DB_NAME", "hyderabad_webgis"),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD", "")
}

UTM_EPSG = 32644
BASE_SPEED = 4.8
SLOW_SPEED = 3.6
BASE_THRESHOLD = 1200.0
SLOW_THRESHOLD = 900.0
SAMPLE_SIZE = 30
RANDOM_SEED = 20261119

TO_UTM = Transformer.from_crs(
    "EPSG:4326", f"EPSG:{UTM_EPSG}", always_xy=True
)
TO_WGS = Transformer.from_crs(
    f"EPSG:{UTM_EPSG}", "EPSG:4326", always_xy=True
)


# ============================================================
# 2. HELPERS
# ============================================================

def read_geojson_geometry(path):
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if data["type"] == "FeatureCollection":
        geoms = [
            shape(feature["geometry"])
            for feature in data["features"]
            if feature.get("geometry")
        ]
        return unary_union(geoms)

    if data["type"] == "Feature":
        return shape(data["geometry"])

    return shape(data)


def read_geojson_features(path):
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if data["type"] == "FeatureCollection":
        return data["features"]

    if data["type"] == "Feature":
        return [data]

    return []


def to_utm(geom):
    return geom_transform(TO_UTM.transform, geom)


def to_wgs(geom):
    return geom_transform(TO_WGS.transform, geom)


def safe_number(value):
    if value is None:
        return None
    value = float(value)
    if not math.isfinite(value):
        return None
    return round(value, 3)


def write_geojson(path, features):
    collection = {
        "type": "FeatureCollection",
        "features": features
    }

    with open(path, "w", encoding="utf-8") as f:
        json.dump(collection, f, ensure_ascii=False, allow_nan=False)


def make_feature(geom, properties):
    if geom is None or geom.is_empty:
        return None

    return {
        "type": "Feature",
        "properties": properties,
        "geometry": mapping(geom)
    }


def h3_cells_for_polygon(polygon, resolution):
    cells = set()

    polygons = (
        list(polygon.geoms)
        if polygon.geom_type == "MultiPolygon"
        else [polygon]
    )

    for part in polygons:
        if part.geom_type == "Polygon":
            cells.update(
                h3.geo_to_cells(mapping(part), resolution)
            )

    return sorted(cells)


def nearest_index(x, y, node_x, node_y):
    distances_squared = (
        (node_x - x) ** 2 + (node_y - y) ** 2
    )
    idx = int(np.argmin(distances_squared))
    distance = float(math.sqrt(distances_squared[idx]))
    return idx, distance


def make_isochrone(reached_nodes, node_utm, source_point, area_utm):
    coords = [
        node_utm[node]
        for node in reached_nodes
        if node in node_utm
    ]

    if len(coords) == 0:
        hull = source_point.buffer(20)

    elif len(coords) == 1:
        hull = Point(coords[0]).buffer(20)

    else:
        hull = MultiPoint(coords).convex_hull

        if hull.geom_type in ("Point", "LineString"):
            hull = hull.buffer(20)

    clipped = hull.intersection(area_utm)

    if clipped.is_empty:
        clipped = source_point.buffer(20).intersection(area_utm)

    return clipped


def save_csv(path, header, rows):
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(rows)


def pct(numerator, denominator):
    return (
        100.0 * numerator / denominator
        if denominator > 0 else 0.0
    )


# ============================================================
# 3. STUDY AREA AND WARDS
# ============================================================

print("\nPHASE 3: ACCESSIBILITY ANALYSIS")
print("================================")

for path in [STUDY_FILE, WARDS_FILE, GRAPH_FILE]:
    if not path.exists():
        raise FileNotFoundError(path)

study_geom = read_geojson_geometry(STUDY_FILE)
study_utm = to_utm(study_geom)

print("Study geometry:", study_geom.geom_type)
print("Study area (UTM km2):", round(study_utm.area / 1e6, 4))

wards = []

for i, feature in enumerate(read_geojson_features(WARDS_FILE)):
    props = feature.get("properties") or {}
    geom = shape(feature["geometry"])

    name = (
        props.get("ward_name")
        or props.get("name")
        or props.get("WARD_NAME")
        or props.get("ward")
        or f"Ward_{i + 1}"
    )

    wards.append({
        "name": str(name),
        "geom": to_utm(geom)
    })

print("Ward features:", len(wards))


# ============================================================
# 4. LOAD HEALTHCARE SERVICE POINTS FROM POSTGIS
# ============================================================

print("\nLoading healthcare service points from PostGIS...")

conn = psycopg2.connect(**DB)
cur = conn.cursor()

area_wkt = study_geom.wkt

cur.execute("""
    SELECT
        feature_id,
        name,
        category,
        ST_X(ST_Transform(ST_PointOnSurface(geom), 32644)),
        ST_Y(ST_Transform(ST_PointOnSurface(geom), 32644))
    FROM phase1_healthcare
    WHERE ST_Covers(
        ST_GeomFromText(%s, 4326),
        ST_PointOnSurface(geom)
    )
    ORDER BY feature_id;
""", (area_wkt,))

services = []

for row in cur.fetchall():
    services.append({
        "id": int(row[0]),
        "name": row[1] or "Unnamed healthcare facility",
        "category": row[2] or "Unclassified",
        "x": float(row[3]),
        "y": float(row[4])
    })

if len(services) < 15:
    raise RuntimeError(
        f"Only {len(services)} services lie inside the study area. "
        "Verify the study-area boundary and source records."
    )

service_x = np.array([s["x"] for s in services], dtype=float)
service_y = np.array([s["y"] for s in services], dtype=float)

print("Healthcare features inside study area:", len(services))


# ============================================================
# 5. LOAD AND PREPARE THE WALKING GRAPH
# ============================================================

print("\nLoading the local OSMnx GraphML file...")

G = ox.load_graphml(filepath=GRAPH_FILE)

print("Original graph nodes:", len(G.nodes))
print("Original graph edges:", len(G.edges))

# Convert to a simple undirected walking graph.
# Parallel road segments are reduced to their shortest edge.
UG = nx.Graph()

for node, data in G.nodes(data=True):
    UG.add_node(
        node,
        x=float(data["x"]),
        y=float(data["y"])
    )

if G.is_multigraph():
    edge_iter = G.edges(keys=True, data=True)
    for u, v, key, data in edge_iter:
        length = float(data.get("length", 0.0))

        if not math.isfinite(length) or length <= 0:
            x1, y1 = float(G.nodes[u]["x"]), float(G.nodes[u]["y"])
            x2, y2 = float(G.nodes[v]["x"]), float(G.nodes[v]["y"])
            xx1, yy1 = TO_UTM.transform(x1, y1)
            xx2, yy2 = TO_UTM.transform(x2, y2)
            length = math.hypot(xx2 - xx1, yy2 - yy1)

        if not UG.has_edge(u, v) or length < UG[u][v]["length"]:
            UG.add_edge(u, v, length=length)

else:
    for u, v, data in G.edges(data=True):
        length = float(data.get("length", 0.0))

        if not math.isfinite(length) or length <= 0:
            x1, y1 = float(G.nodes[u]["x"]), float(G.nodes[u]["y"])
            x2, y2 = float(G.nodes[v]["x"]), float(G.nodes[v]["y"])
            xx1, yy1 = TO_UTM.transform(x1, y1)
            xx2, yy2 = TO_UTM.transform(x2, y2)
            length = math.hypot(xx2 - xx1, yy2 - yy1)

        UG.add_edge(u, v, length=length)

# Remove isolated nodes.
UG.remove_nodes_from(list(nx.isolates(UG)))

node_ids = list(UG.nodes)

node_lon = np.array(
    [float(UG.nodes[n]["x"]) for n in node_ids],
    dtype=float
)
node_lat = np.array(
    [float(UG.nodes[n]["y"]) for n in node_ids],
    dtype=float
)

node_x, node_y = TO_UTM.transform(node_lon, node_lat)

node_x = np.asarray(node_x)
node_y = np.asarray(node_y)

node_utm = {
    node_ids[i]: (float(node_x[i]), float(node_y[i]))
    for i in range(len(node_ids))
}

def snap_to_graph(x, y):
    idx, distance = nearest_index(x, y, node_x, node_y)
    return node_ids[idx], distance


print("Undirected walking graph nodes:", len(UG.nodes))
print("Undirected walking graph edges:", len(UG.edges))


# ============================================================
# 6. SNAP SERVICES TO THE WALKING NETWORK
# ============================================================

print("\nSnapping healthcare facilities to walking network...")

service_nodes = {}
service_connectors = {}

for service in services:
    node, connector = snap_to_graph(service["x"], service["y"])
    service_nodes[service["id"]] = node
    service_connectors[service["id"]] = connector

connector_values = list(service_connectors.values())

print(
    "Mean service-to-network connector distance (m):",
    round(float(np.mean(connector_values)), 2)
)


# ============================================================
# 7. MULTI-SOURCE SHORTEST PATH TO NEAREST SERVICE
# ============================================================

print("\nComputing nearest-service network distances...")

AUG = UG.copy()

SUPER = ("phase3", "super_source")
AUG.add_node(SUPER)

virtual_to_service = {}

for service in services:
    service_id = service["id"]
    virtual = ("phase3_service", service_id)

    virtual_to_service[virtual] = service_id

    AUG.add_edge(SUPER, virtual, length=0.0)
    AUG.add_edge(
        virtual,
        service_nodes[service_id],
        length=service_connectors[service_id]
    )

network_distances, network_paths = nx.single_source_dijkstra(
    AUG,
    SUPER,
    weight="length"
)

print(
    "Graph nodes reachable from healthcare services:",
    len(network_distances)
)


def nearest_network_service(node, access_distance):
    path = network_paths.get(node)

    if path is None or len(path) < 3:
        return None, None

    virtual = path[1]
    service_id = virtual_to_service.get(virtual)

    if service_id is None:
        return None, None

    total = network_distances[node] + access_distance
    return service_id, float(total)


# ============================================================
# 8. Q6: 30 RANDOM POINTS
# ============================================================

print("\nQ6: Comparing straight-line and walking-network nearest service...")

rng = random.Random(RANDOM_SEED)

minx, miny, maxx, maxy = study_utm.bounds
random_points = []

while len(random_points) < SAMPLE_SIZE:
    x = rng.uniform(minx, maxx)
    y = rng.uniform(miny, maxy)

    if study_utm.contains(Point(x, y)):
        random_points.append((x, y))

q6_rows = []
q6_features = []
ratios = []
different_count = 0

for sample_no, (x, y) in enumerate(random_points, start=1):

    direct_distances = np.hypot(
        service_x - x,
        service_y - y
    )

    direct_idx = int(np.argmin(direct_distances))
    direct_service = services[direct_idx]
    direct_distance = float(direct_distances[direct_idx])

    snap_node, access_distance = snap_to_graph(x, y)

    network_service_id, network_distance = nearest_network_service(
        snap_node,
        access_distance
    )

    if network_service_id is None or direct_distance <= 0:
        ratio = None
        network_service = None
    else:
        network_service = next(
            s for s in services if s["id"] == network_service_id
        )
        ratio = network_distance / direct_distance
        ratios.append(ratio)

        if network_service_id != direct_service["id"]:
            different_count += 1

    q6_rows.append([
        sample_no,
        round(x, 3),
        round(y, 3),
        direct_service["id"],
        direct_service["name"],
        round(direct_distance, 2),
        network_service_id,
        network_service["name"] if network_service else None,
        safe_number(network_distance),
        safe_number(ratio),
        network_service_id != direct_service["id"]
        if network_service_id is not None else None
    ])

    point_wgs = to_wgs(Point(x, y))

    q6_features.append(make_feature(
        point_wgs,
        {
            "sample_no": sample_no,
            "nearest_straight_service_id": direct_service["id"],
            "nearest_network_service_id": network_service_id,
            "straight_distance_m": round(direct_distance, 2),
            "network_distance_m": safe_number(network_distance),
            "distance_ratio": safe_number(ratio)
        }
    ))

save_csv(
    OUTPUT / "Q6_random_point_comparison.csv",
    [
        "sample_no", "x_utm", "y_utm",
        "straight_service_id", "straight_service_name",
        "straight_distance_m", "network_service_id",
        "network_service_name", "network_distance_m",
        "network_to_straight_ratio", "nearest_service_different"
    ],
    q6_rows
)

write_geojson(
    OUTPUT / "Q6_random_points.geojson",
    [f for f in q6_features if f]
)

valid_ratios = [r for r in ratios if math.isfinite(r)]

median_ratio = (
    float(np.median(valid_ratios))
    if valid_ratios else None
)
max_ratio = max(valid_ratios) if valid_ratios else None

print("Random points:", SAMPLE_SIZE)
print("Nearest service differs:", different_count)
print("Median network / straight-line ratio:", safe_number(median_ratio))
print("Maximum network / straight-line ratio:", safe_number(max_ratio))


# ============================================================
# 9. Q6 WORST-CASE MAP GEOMETRY
# ============================================================

worst_case = None

if q6_rows:
    candidates = [r for r in q6_rows if r[9] is not None]

    if candidates:
        worst_case = max(candidates, key=lambda r: r[9])

if worst_case:
    sample_no = worst_case[0]
    sx, sy = random_points[sample_no - 1]

    service_id = worst_case[6]
    target_node = service_nodes[service_id]
    sample_node, _ = snap_to_graph(sx, sy)

    route_nodes = nx.shortest_path(
        UG,
        source=sample_node,
        target=target_node,
        weight="length"
    )

    route_coords = [
        node_utm[n] for n in route_nodes
    ]

    route_utm = (
        LineString(route_coords)
        if len(route_coords) >= 2
        else Point(route_coords[0])
    )

    route_wgs = to_wgs(route_utm)

    service = next(s for s in services if s["id"] == service_id)

    sample_point_wgs = to_wgs(Point(sx, sy))
    service_point_wgs = to_wgs(Point(service["x"], service["y"]))

    straight_line_wgs = LineString([
        (sample_point_wgs.x, sample_point_wgs.y),
        (service_point_wgs.x, service_point_wgs.y)
    ])

    worst_features = [
        make_feature(
            sample_point_wgs,
            {"kind": "sample_point", "sample_no": sample_no}
        ),
        make_feature(
            service_point_wgs,
            {
                "kind": "nearest_network_service",
                "service_id": service_id,
                "name": service["name"]
            }
        ),
        make_feature(
            straight_line_wgs,
            {"kind": "straight_line_connection"}
        ),
        make_feature(
            route_wgs,
            {
                "kind": "network_route_node_path_approximation",
                "network_distance_m": worst_case[8]
            }
        )
    ]

    write_geojson(
        OUTPUT / "Q6_worst_case.geojson",
        [f for f in worst_features if f]
    )


# ============================================================
# 10. Q3/PHASE 3: ISOCHRONES AND STRAIGHT-LINE BUFFERS
# ============================================================

print("\nGenerating service isochrone approximations...")

iso_48_features = []
iso_36_features = []
buffer_48_features = []
buffer_36_features = []

iso_db_rows = []

for index, service in enumerate(services, start=1):

    sid = service["id"]
    source_node = service_nodes[sid]
    connector = service_connectors[sid]

    cutoff = max(0.0, BASE_THRESHOLD - connector)

    reachable = nx.single_source_dijkstra_path_length(
        UG,
        source_node,
        cutoff=cutoff,
        weight="length"
    )

    reachable_48 = [
        node for node, distance in reachable.items()
        if distance + connector <= BASE_THRESHOLD
    ]

    reachable_36 = [
        node for node, distance in reachable.items()
        if distance + connector <= SLOW_THRESHOLD
    ]

    source_point = Point(service["x"], service["y"])

    iso48 = make_isochrone(
        reachable_48, node_utm, source_point, study_utm
    )
    iso36 = make_isochrone(
        reachable_36, node_utm, source_point, study_utm
    )

    iso48_wgs = to_wgs(iso48)
    iso36_wgs = to_wgs(iso36)

    common_props = {
        "service_id": sid,
        "name": service["name"],
        "category": service["category"],
        "duration_minutes": 15,
        "geometry_method": "Convex hull of reachable road nodes"
    }

    iso_48_features.append(make_feature(
        iso48_wgs,
        {
            **common_props,
            "walking_speed_kmh": BASE_SPEED,
            "threshold_m": int(BASE_THRESHOLD),
            "reachable_nodes": len(reachable_48)
        }
    ))

    iso_36_features.append(make_feature(
        iso36_wgs,
        {
            **common_props,
            "walking_speed_kmh": SLOW_SPEED,
            "threshold_m": int(SLOW_THRESHOLD),
            "reachable_nodes": len(reachable_36)
        }
    ))

    buffer48 = source_point.buffer(BASE_THRESHOLD).intersection(study_utm)
    buffer36 = source_point.buffer(SLOW_THRESHOLD).intersection(study_utm)

    buffer_48_features.append(make_feature(
        to_wgs(buffer48),
        {
            "service_id": sid,
            "name": service["name"],
            "walking_speed_kmh": BASE_SPEED,
            "threshold_m": int(BASE_THRESHOLD)
        }
    ))

    buffer_36_features.append(make_feature(
        to_wgs(buffer36),
        {
            "service_id": sid,
            "name": service["name"],
            "walking_speed_kmh": SLOW_SPEED,
            "threshold_m": int(SLOW_THRESHOLD)
        }
    ))

    iso_db_rows.append((
        sid, service["name"], service["category"],
        BASE_SPEED, int(BASE_THRESHOLD),
        json.dumps(mapping(iso48_wgs), ensure_ascii=False)
    ))

    iso_db_rows.append((
        sid, service["name"], service["category"],
        SLOW_SPEED, int(SLOW_THRESHOLD),
        json.dumps(mapping(iso36_wgs), ensure_ascii=False)
    ))

    if index % 25 == 0:
        print(f"Isochrones processed: {index}/{len(services)}")

write_geojson(
    OUTPUT / "isochrones_4_8_kmh_15min.geojson",
    [f for f in iso_48_features if f]
)

write_geojson(
    OUTPUT / "isochrones_3_6_kmh_15min.geojson",
    [f for f in iso_36_features if f]
)

write_geojson(
    OUTPUT / "straight_buffers_1200m.geojson",
    [f for f in buffer_48_features if f]
)

write_geojson(
    OUTPUT / "straight_buffers_900m.geojson",
    [f for f in buffer_36_features if f]
)

print("Isochrones generated for:", len(services), "services")


# ============================================================
# 11. LOAD BUILDING FOOTPRINTS FOR H3 PROXY WEIGHTING
# ============================================================

print("\nLoading building footprints intersecting the study area...")

cur.execute("""
    SELECT
        ST_AsBinary(
            ST_CollectionExtract(
                ST_MakeValid(
                    ST_Transform(geom, 32644)
                ),
                3
            )
        )
    FROM phase1_buildings
    WHERE geom && ST_GeomFromText(%s, 4326)
      AND ST_Intersects(
          geom,
          ST_GeomFromText(%s, 4326)
      );
""", (area_wkt, area_wkt))

building_geometries = []

for (binary_geom,) in cur.fetchall():
    if binary_geom is None:
        continue

    geom = wkb.loads(bytes(binary_geom))

    if not geom.is_empty and geom.area > 0:
        building_geometries.append(geom)

if not building_geometries:
    raise RuntimeError(
        "No building footprint polygons were returned inside the area."
    )

building_tree = STRtree(building_geometries)

print("Building footprints intersecting area:", len(building_geometries))


def building_area_for_cell(cell_utm):
    indexes = building_tree.query(
        cell_utm,
        predicate="intersects"
    )

    total_area = 0.0

    for idx in indexes:
        intersection = building_geometries[int(idx)].intersection(cell_utm)
        if not intersection.is_empty:
            total_area += intersection.area

    return float(total_area)


# ============================================================
# 12. H3 RESOLUTIONS 8 AND 9
# ============================================================

print("\nGenerating H3 access cells at resolutions 8 and 9...")

h3_rows = []
h3_geojson_features = []
ward_summary_rows = []
h3_summary_rows = []

for resolution in (8, 9):

    print(f"\nH3 resolution {resolution}")

    cells = h3_cells_for_polygon(study_geom, resolution)
    print("H3 cells generated:", len(cells))

    resolution_records = []

    for counter, cell_id in enumerate(cells, start=1):

        boundary = h3.cell_to_boundary(cell_id)

        # H3 returns (latitude, longitude).
        cell_polygon = Polygon([
            (lng, lat) for lat, lng in boundary
        ])

        cell_utm = to_utm(cell_polygon).intersection(study_utm)

        if cell_utm.is_empty:
            continue

        center_lat, center_lon = h3.cell_to_latlng(cell_id)
        center_x, center_y = TO_UTM.transform(
            center_lon, center_lat
        )

        snap_node, access_distance = snap_to_graph(
            center_x, center_y
        )

        network_service_id, network_distance = nearest_network_service(
            snap_node, access_distance
        )

        direct_distances = np.hypot(
            service_x - center_x,
            service_y - center_y
        )

        direct_idx = int(np.argmin(direct_distances))
        straight_distance = float(direct_distances[direct_idx])

        footprint_area = building_area_for_cell(cell_utm)

        point_utm = Point(center_x, center_y)

        ward_name = "Unassigned"

        for ward in wards:
            if ward["geom"].covers(point_utm):
                ward_name = ward["name"]
                break

        record = {
            "resolution": resolution,
            "h3_index": cell_id,
            "center_lon": float(center_lon),
            "center_lat": float(center_lat),
            "nearest_service_id_network": network_service_id,
            "network_distance_m": network_distance,
            "straight_distance_m": straight_distance,
            "network_covered_4_8": (
                network_distance is not None
                and network_distance <= BASE_THRESHOLD
            ),
            "network_covered_3_6": (
                network_distance is not None
                and network_distance <= SLOW_THRESHOLD
            ),
            "buffer_covered_4_8": (
                straight_distance <= BASE_THRESHOLD
            ),
            "footprint_area_m2": footprint_area,
            "ward_name": ward_name,
            "geometry": to_wgs(cell_utm)
        }

        resolution_records.append(record)

        geom_json = json.dumps(
            mapping(record["geometry"]),
            ensure_ascii=False
        )

        h3_rows.append((
            resolution,
            cell_id,
            network_service_id,
            safe_number(network_distance),
            safe_number(straight_distance),
            footprint_area,
            record["network_covered_4_8"],
            record["network_covered_3_6"],
            record["buffer_covered_4_8"],
            ward_name,
            geom_json
        ))

        h3_geojson_features.append(make_feature(
            record["geometry"],
            {
                "resolution": resolution,
                "h3_index": cell_id,
                "nearest_service_id": network_service_id,
                "network_distance_m": safe_number(network_distance),
                "straight_distance_m": round(straight_distance, 2),
                "network_covered_4_8": record["network_covered_4_8"],
                "network_covered_3_6": record["network_covered_3_6"],
                "buffer_covered_4_8": record["buffer_covered_4_8"],
                "building_footprint_area_m2": round(footprint_area, 2),
                "population_proxy": "Building footprint area",
                "ward_name": ward_name
            }
        ))

        if counter % 50 == 0:
            print(f"Processed: {counter}/{len(cells)}")

    # Resolution-level weighted summary.
    total_weight = sum(
        r["footprint_area_m2"] for r in resolution_records
    )

    network_weight_48 = sum(
        r["footprint_area_m2"]
        for r in resolution_records
        if r["network_covered_4_8"]
    )

    network_weight_36 = sum(
        r["footprint_area_m2"]
        for r in resolution_records
        if r["network_covered_3_6"]
    )

    buffer_weight_48 = sum(
        r["footprint_area_m2"]
        for r in resolution_records
        if r["buffer_covered_4_8"]
    )

    network_cov_48 = pct(network_weight_48, total_weight)
    network_cov_36 = pct(network_weight_36, total_weight)
    buffer_cov_48 = pct(buffer_weight_48, total_weight)

    h3_summary_rows.append([
        resolution,
        len(resolution_records),
        round(total_weight, 2),
        round(network_cov_48, 2),
        round(100 - network_cov_48, 2),
        round(buffer_cov_48, 2),
        round(100 - buffer_cov_48, 2),
        round(network_cov_36, 2),
        round(100 - network_cov_36, 2),
        round(network_cov_48 - network_cov_36, 2)
    ])

    # Ward aggregation using H3 cell-centre assignment.
    for ward_name in sorted(
        set(r["ward_name"] for r in resolution_records)
    ):
        subset = [
            r for r in resolution_records
            if r["ward_name"] == ward_name
        ]

        weight = sum(r["footprint_area_m2"] for r in subset)

        w48 = sum(
            r["footprint_area_m2"]
            for r in subset if r["network_covered_4_8"]
        )

        w36 = sum(
            r["footprint_area_m2"]
            for r in subset if r["network_covered_3_6"]
        )

        wb = sum(
            r["footprint_area_m2"]
            for r in subset if r["buffer_covered_4_8"]
        )

        ward_summary_rows.append([
            resolution,
            ward_name,
            len(subset),
            round(weight, 2),
            round(pct(w48, weight), 2),
            round(pct(wb, weight), 2),
            round(pct(w36, weight), 2),
            round(pct(w48, weight) - pct(w36, weight), 2)
        ])

    print(
        "4.8 km/h network coverage (% footprint proxy):",
        round(network_cov_48, 2)
    )
    print(
        "4.8 km/h straight buffer coverage (% footprint proxy):",
        round(buffer_cov_48, 2)
    )
    print(
        "3.6 km/h network coverage (% footprint proxy):",
        round(network_cov_36, 2)
    )
    print(
        "Coverage loss, percentage points:",
        round(network_cov_48 - network_cov_36, 2)
    )


# ============================================================
# 13. H3 WORST-SERVED POPULATED CELL
# ============================================================

res9_populated = [
    r for r in h3_rows
    if r[0] == 9 and r[5] > 0 and r[3] is not None
]

worst_h3 = (
    max(res9_populated, key=lambda r: r[3])
    if res9_populated else None
)


# ============================================================
# 14. SAVE H3 AND Q7/Q8 FILES
# ============================================================

write_geojson(
    OUTPUT / "phase3_h3_access_res8_res9.geojson",
    [f for f in h3_geojson_features if f]
)

save_csv(
    OUTPUT / "Q7_H3_coverage_summary.csv",
    [
        "resolution", "cell_count", "total_building_area_m2",
        "network_covered_4_8_pct",
        "network_beyond_1200m_pct",
        "buffer_covered_4_8_pct",
        "buffer_beyond_1200m_pct",
        "network_covered_3_6_pct",
        "network_beyond_900m_pct",
        "coverage_loss_percentage_points"
    ],
    h3_summary_rows
)

save_csv(
    OUTPUT / "Q7_ward_coverage.csv",
    [
        "resolution", "ward_name", "cell_count",
        "building_footprint_area_m2",
        "network_covered_4_8_pct",
        "buffer_covered_4_8_pct",
        "network_covered_3_6_pct",
        "coverage_loss_percentage_points"
    ],
    ward_summary_rows
)


# ============================================================
# 15. WRITE H3 AND ISOCHRONE RESULTS BACK TO POSTGIS
# ============================================================

print("\nWriting Phase 3 results into PostGIS...")

cur.execute("DROP TABLE IF EXISTS phase3_h3_access CASCADE;")

cur.execute("""
    CREATE TABLE phase3_h3_access (
        resolution INTEGER NOT NULL,
        h3_index TEXT NOT NULL,
        nearest_service_id BIGINT,
        network_distance_m DOUBLE PRECISION,
        straight_distance_m DOUBLE PRECISION,
        building_footprint_area_m2 DOUBLE PRECISION,
        network_covered_4_8 BOOLEAN,
        network_covered_3_6 BOOLEAN,
        buffer_covered_4_8 BOOLEAN,
        ward_name TEXT,
        geom geometry(Geometry, 4326),
        PRIMARY KEY (resolution, h3_index)
    );
""")

if h3_rows:
    execute_values(
        cur,
        """
        INSERT INTO phase3_h3_access (
            resolution, h3_index, nearest_service_id,
            network_distance_m, straight_distance_m,
            building_footprint_area_m2,
            network_covered_4_8, network_covered_3_6,
            buffer_covered_4_8, ward_name, geom
        )
        VALUES %s
        """,
        h3_rows,
        template="""
        (
            %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s,
            ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326)
        )
        """,
        page_size=500
    )

cur.execute("""
    CREATE INDEX phase3_h3_access_geom_gix
    ON phase3_h3_access USING GIST (geom);
""")

cur.execute("""
    CREATE INDEX phase3_h3_access_resolution_idx
    ON phase3_h3_access (resolution);
""")

cur.execute("ANALYZE phase3_h3_access;")


cur.execute("DROP TABLE IF EXISTS phase3_service_isochrones CASCADE;")

cur.execute("""
    CREATE TABLE phase3_service_isochrones (
        service_id BIGINT,
        service_name TEXT,
        category TEXT,
        walking_speed_kmh DOUBLE PRECISION,
        threshold_m INTEGER,
        geom geometry(Geometry, 4326)
    );
""")

iso_db_rows = []

# Use the stored isochrone files to load polygons.
for filename, speed, threshold in [
    ("isochrones_4_8_kmh_15min.geojson", BASE_SPEED, int(BASE_THRESHOLD)),
    ("isochrones_3_6_kmh_15min.geojson", SLOW_SPEED, int(SLOW_THRESHOLD))
]:
    path = OUTPUT / filename
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    for feature in data["features"]:
        props = feature["properties"]

        iso_db_rows.append((
            props["service_id"],
            props["name"],
            props["category"],
            speed,
            threshold,
            json.dumps(feature["geometry"], ensure_ascii=False)
        ))

if iso_db_rows:
    execute_values(
        cur,
        """
        INSERT INTO phase3_service_isochrones (
            service_id, service_name, category,
            walking_speed_kmh, threshold_m, geom
        )
        VALUES %s
        """,
        iso_db_rows,
        template="""
        (
            %s, %s, %s, %s, %s,
            ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326)
        )
        """,
        page_size=500
    )

cur.execute("""
    CREATE INDEX phase3_service_isochrones_geom_gix
    ON phase3_service_isochrones USING GIST (geom);
""")

cur.execute("ANALYZE phase3_service_isochrones;")

cur.execute("SELECT COUNT(*) FROM phase3_h3_access;")
h3_db_count = cur.fetchone()[0]

cur.execute("SELECT COUNT(*) FROM phase3_service_isochrones;")
iso_db_count = cur.fetchone()[0]

conn.commit()

print("H3 records in PostGIS:", h3_db_count)
print("Isochrone records in PostGIS:", iso_db_count)


# ============================================================
# 16. FINAL SUMMARY
# ============================================================

summary_lines = [
    "PHASE 3 ACCESSIBILITY ANALYSIS",
    "================================",
    f"Study area: Hyderabad Ward 106 and Ward 109",
    f"UTM CRS: EPSG:{UTM_EPSG}",
    f"Healthcare services inside study area: {len(services)}",
    f"Walking graph nodes: {len(UG.nodes)}",
    f"Walking graph edges: {len(UG.edges)}",
    "",
    "Q6 - RANDOM POINT COMPARISON",
    f"Random points: {SAMPLE_SIZE}",
    f"Different nearest service count: {different_count}",
    f"Median network/straight-line ratio: {safe_number(median_ratio)}",
    f"Maximum network/straight-line ratio: {safe_number(max_ratio)}",
    "",
    "POPULATION PROXY",
    "WorldPop raster was not available in the project data folder.",
    "Building footprint area (m2) is used as a proxy, not population.",
    "",
    "Q7/Q8 - H3 COVERAGE SUMMARIES"
]

for row in h3_summary_rows:
    summary_lines.append(
        f"Resolution {row[0]}: cells={row[1]}, "
        f"network coverage 4.8 km/h={row[3]}%, "
        f"straight buffer coverage={row[5]}%, "
        f"network coverage 3.6 km/h={row[7]}%, "
        f"coverage loss={row[9]} percentage points"
    )

if worst_h3:
    summary_lines.extend([
        "",
        "Worst-served populated H3 resolution-9 cell:",
        f"H3 index: {worst_h3[1]}",
        f"Network distance (m): {worst_h3[3]}",
        f"Building footprint area (m2): {round(worst_h3[5], 2)}"
    ])

summary_lines.extend([
    "",
    "METHOD LIMITATIONS",
    "- Isochrones are convex hulls of reachable OSM road nodes.",
    "- They are approximate polygons, not exact travel-time surfaces.",
    "- H3 cell-centre distances represent each cell.",
    "- Building footprint area is a population proxy, not census population.",
    "- Ward assignment uses the H3 cell centre.",
    "- Walking graph is treated as undirected."
])

(OUTPUT / "PHASE3_summary.txt").write_text(
    "\n".join(summary_lines),
    encoding="utf-8"
)

for line in summary_lines:
    print(line)

cur.close()
conn.close()

print("\nPHASE 3 COMPLETED")
print("Outputs:", OUTPUT)
