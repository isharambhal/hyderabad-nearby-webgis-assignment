CREATE EXTENSION IF NOT EXISTS postgis;

CREATE TABLE IF NOT EXISTS wards (
    ward_id BIGSERIAL PRIMARY KEY,
    ward_name TEXT NOT NULL,
    source_id TEXT,
    properties JSONB NOT NULL DEFAULT '{}'::jsonb,
    geom geometry(MultiPolygon, 4326) NOT NULL
);
CREATE INDEX IF NOT EXISTS wards_geom_gix ON wards USING GIST (geom);
CREATE INDEX IF NOT EXISTS wards_name_idx ON wards (ward_name);

CREATE TABLE IF NOT EXISTS services (
    service_id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    category TEXT NOT NULL,
    subcategory TEXT,
    address TEXT,
    phone TEXT,
    opening_hours TEXT,
    source TEXT,
    source_id TEXT,
    latitude DOUBLE PRECISION NOT NULL CHECK (latitude BETWEEN -90 AND 90),
    longitude DOUBLE PRECISION NOT NULL CHECK (longitude BETWEEN -180 AND 180),
    geom geometry(Point, 4326) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS services_geom_gix ON services USING GIST (geom);
CREATE INDEX IF NOT EXISTS services_category_idx ON services (category);
CREATE INDEX IF NOT EXISTS services_subcategory_idx ON services (subcategory);
CREATE INDEX IF NOT EXISTS services_name_idx ON services (name);

-- Geography distance is calculated in metres on the WGS 84 ellipsoid.
CREATE OR REPLACE VIEW services_public AS
SELECT service_id, name, category, subcategory, address, phone, opening_hours,
       source, source_id, latitude, longitude, geom
FROM services;
