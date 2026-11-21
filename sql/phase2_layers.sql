
-- Phase 2: Prepare GeoServer publication layers
-- Study area: Ward 109 Hafeezpet and Ward 106 Serilingampally
-- Source CRS: EPSG:4326

BEGIN;

-- 1. Selected ward boundaries
DROP TABLE IF EXISTS phase2_study_area CASCADE;

CREATE TABLE phase2_study_area AS
SELECT
    ward_id,
    ward_name,
    geom::geometry(MultiPolygon, 4326) AS geom
FROM wards
WHERE ward_id IN (36, 38);

ALTER TABLE phase2_study_area
ADD PRIMARY KEY (ward_id);

CREATE INDEX phase2_study_area_geom_gix
ON phase2_study_area USING GIST (geom);


-- 2. Dissolved study area for spatial filtering
DROP TABLE IF EXISTS phase2_services CASCADE;

CREATE TABLE phase2_services AS
WITH study AS (
    SELECT ST_UnaryUnion(ST_Collect(geom)) AS geom
    FROM phase2_study_area
)
SELECT
    h.feature_id,
    h.osm_id,
    h.name,
    h.category,
    h.properties,
    ST_SetSRID(
        ST_PointOnSurface(h.geom), 4326
    )::geometry(Point, 4326) AS geom
FROM phase1_healthcare h
CROSS JOIN study s
WHERE ST_Covers(
    s.geom,
    ST_PointOnSurface(h.geom)
);

ALTER TABLE phase2_services
ADD PRIMARY KEY (feature_id);

CREATE INDEX phase2_services_geom_gix
ON phase2_services USING GIST (geom);

CREATE INDEX phase2_services_category_idx
ON phase2_services (category);


-- 3. Clip building footprints to the study boundary
DROP TABLE IF EXISTS phase2_buildings CASCADE;

CREATE TABLE phase2_buildings (
    feature_id BIGINT PRIMARY KEY,
    osm_id TEXT,
    name TEXT,
    category TEXT,
    properties JSONB,
    geom geometry(MultiPolygon, 4326) NOT NULL
);

WITH study AS (
    SELECT ST_UnaryUnion(ST_Collect(geom)) AS geom
    FROM phase2_study_area
),
clipped AS (
    SELECT
        b.feature_id,
        b.osm_id,
        b.name,
        b.category,
        b.properties,
        ST_Multi(
            ST_CollectionExtract(
                ST_MakeValid(
                    ST_Intersection(
                        ST_MakeValid(b.geom),
                        ST_MakeValid(s.geom)
                    )
                ),
                3
            )
        )::geometry(MultiPolygon, 4326) AS geom
    FROM phase1_buildings b
    CROSS JOIN study s
    WHERE ST_Dimension(b.geom) = 2
      AND ST_Intersects(b.geom, s.geom)
)
INSERT INTO phase2_buildings (
    feature_id, osm_id, name, category, properties, geom
)
SELECT
    feature_id, osm_id, name, category, properties, geom
FROM clipped
WHERE geom IS NOT NULL
  AND NOT ST_IsEmpty(geom);


CREATE INDEX phase2_buildings_geom_gix
ON phase2_buildings USING GIST (geom);


-- Update statistics
ANALYZE phase2_study_area;
ANALYZE phase2_services;
ANALYZE phase2_buildings;


-- 4. Verify actual publication layer counts
SELECT 'phase2_study_area' AS layer, COUNT(*) AS features
FROM phase2_study_area
UNION ALL
SELECT 'phase2_services', COUNT(*)
FROM phase2_services
UNION ALL
SELECT 'phase2_buildings', COUNT(*)
FROM phase2_buildings;

COMMIT;
