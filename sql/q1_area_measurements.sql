-- Q1: One Area, Four Areas
-- Area comparison using EPSG:4326, Geography, UTM 44N and Web Mercator.
-- Selected wards: 36 and 38.

WITH selected_area AS (
    SELECT
        ST_UnaryUnion(ST_Collect(geom)) AS geom
    FROM public.wards
    WHERE ward_id IN (36, 38)
),
measurements AS (
    SELECT
        geom,
        ST_Y(ST_Centroid(geom)) AS centre_latitude,
        ST_Area(geom) AS area_4326,
        ST_Area(geom::geography) / 1000000.0
            AS area_geography_km2,
        ST_Area(ST_Transform(geom, 32644)) / 1000000.0
            AS area_utm_km2,
        ST_Area(ST_Transform(geom, 3857)) / 1000000.0
            AS area_3857_km2
    FROM selected_area
)
SELECT
    ROUND(area_4326::numeric, 8)
        AS area_4326_square_degrees,
    ROUND(area_geography_km2::numeric, 6)
        AS area_geography_km2,
    ROUND(area_utm_km2::numeric, 6)
        AS area_utm_km2,
    ROUND(area_3857_km2::numeric, 6)
        AS area_3857_km2,
    ROUND((area_3857_km2 / area_utm_km2)::numeric, 6)
        AS mercator_utm_ratio,
    ROUND(
        (1 / POWER(COS(RADIANS(centre_latitude)), 2))::numeric,
        6
    ) AS theoretical_ratio,
    ROUND(centre_latitude::numeric, 6)
        AS centre_latitude
FROM measurements;
