# Hyderabad Nearby Services WebGIS

**Live site:** https://isharambhal.github.io/hyderabad-nearby-webgis-assignment/

A WebGIS project assessing healthcare accessibility in Serilingampally and Hafeezpet, Hyderabad, using OpenStreetMap, Python, PostGIS, pedestrian network analysis, H3, OGC services, MapLibre GL JS, Docker and Kubernetes.

## Study Area
- Wards: 106 (Serilingampally) and 109 (Hafeezpet)
- Study area: 15.515 sq. km
- Expanded area with 2 km margin: 72.642 sq. km
- Healthcare facilities: 70
- Buildings in expanded area: 44,786
- Walking threshold: 15 minutes (1.2 km) at 4.8 km/h
- Metric analysis CRS: EPSG:32644

## Technology Stack
Python, GeoPandas, OSMnx, H3, PostgreSQL, PostGIS, GeoServer, pg_tileserv, pg_featureserv, SQL, WMS, WFS, MapLibre GL JS, Docker, Kubernetes, Tippecanoe, PMTiles, GitHub Actions and GitHub Pages.

## Project Phases

### Phase 1 - Data Preparation and PostGIS
Prepared OSM healthcare, building and pedestrian network data; created PostGIS tables; compared spatial measurements; tested GiST indexing; and examined healthcare facility records.

### Phase 2 - OGC Services
Compared WMS 1.1.1 and 1.3.0 axis order and WFS 2.0 GeoJSON and GML 3.2.1 outputs.

**Limitation:** DEM GeoTIFF acquisition and the DEM GeoServer coverage-store/WMS/WCS workflow remain incomplete.

### Phase 3 - Healthcare Accessibility
Generated pedestrian-network service areas, compared network access with straight-line buffers, aggregated results using H3 resolutions 8 and 9, and tested walking speeds of 4.8 and 3.6 km/h.

Building footprint area was used as a population proxy, not as a direct population estimate.

### Phase 4 - WebGIS and Performance
Developed a MapLibre GL JS dashboard integrating healthcare services, buildings and H3 accessibility data. Examined WMS, WFS and vector-tile performance.

Some WMS request counts and response times were not separately verified. See ANSWERS.md for recorded measurements and limitations.

### Phase 5 - Deployment
Built a multi-stage Docker image, deployed the static site using GitHub Pages and GitHub Actions, created Kubernetes configurations for the client and PostGIS, tested persistent storage and pod recovery, and published a PMTiles archive with an HTTP Range request test.

The public GitHub Pages site does not host the local PostGIS or OGC backend services. Local service overlays require the corresponding backend services to be running.

## Repository Structure
- `analysis/` - Analysis scripts and outputs
- `client/` - MapLibre WebGIS application
- `data/` - Project data
- `evidence/` - Screenshots and experiment evidence
- `k8s/` - Kubernetes manifests
- `sql/` - PostGIS SQL scripts
- `study/` - Four study notes and lab evidence
- `.github/workflows/` - GitHub Pages deployment workflow
- `ANSWERS.md` - Assignment answers Q1-Q12

## Running Locally
Clone the repository:

    git clone https://github.com/isharambhal/hyderabad-nearby-webgis-assignment.git
    cd hyderabad-nearby-webgis-assignment

Start configured Docker Compose services:

    docker compose up -d

The Kubernetes client dashboard was tested using port forwarding at `http://localhost:8087`.

## Data Sources
- OpenStreetMap: healthcare facilities, buildings and pedestrian roads.
- H3: hexagonal spatial indexing.
- WorldPop was considered; reported accessibility calculations use building footprint area as a proxy.

## Evidence
See `ANSWERS.md`, `evidence/`, `study/`, `sql/` and `k8s/` for assignment answers, screenshots, study notes, SQL scripts and deployment configurations.

## Known Limitations
- DEM coverage and DEM WMS/WCS configuration are incomplete.
- Building footprint area is a proxy, not measured population.
- Some performance measurements were not separately captured.
- The requested full-base single-stage versus slim/Alpine multi-stage image comparison was not fully reproduced.
- Public GitHub Pages does not provide the local backend services.

## Author
Isha Rambhal
M.Sc. Data Science and Spatial Analytics

## Debugging Log

### 1. PMTiles HTTP 404 Error

**Problem:** The PMTiles archive initially returned HTTP 404 on GitHub Pages.

**Observed output:**
    HTTP_STATUS=404
    DOWNLOADED=9379

**Cause:** GitHub Actions publishes the client directory as the website root. Including /client/ in the public URL produced an incorrect path.

**Fix:** Changed the URL from /client/tiles/h3_access.pmtiles to /tiles/h3_access.pmtiles.

**Verification:**
    HTTP_STATUS=206
    DOWNLOADED=16384
    Content-Range: bytes 0-16383/81219
    Accept-Ranges: bytes

### 2. PostgreSQL SQL Encoding Error

**Problem:** PostgreSQL initially failed to execute the Q1 SQL script.

**Observed error:** syntax error at or near "ï»¿"

**Cause:** The SQL file contained a UTF-8 Byte Order Mark (BOM).

**Fix:** Re-saved the SQL file using UTF-8 without BOM.

**Verification:** The SQL script executed successfully and reproduced all seven documented Q1 measurements.
