# WebGIS Assignment – Day 1 Documentation

## Study Area and Data Collection

### 1. Study Area

- **Study area:** Serilingampally and Hafeezpet, Hyderabad
- **Ward 106:** Serilingampally
- **Ward 109:** Hafeezpet
- **Area type:** Urban
- **Service theme:** Healthcare accessibility
- **Coordinate reference system for projected analysis:** WGS 84 / UTM Zone 44N (EPSG:32644)
- **Walking speed:** 4.8 km/h
- **Urban accessibility threshold:** 15 minutes / 1.2 km

The study area was selected from the existing Hyderabad Nearby Services WebGIS project. Two adjacent wards were selected to provide a manageable area for detailed healthcare accessibility analysis.

### 2. OpenStreetMap Data Collection

Healthcare features were downloaded from OpenStreetMap using the Overpass API.

**Collection results:**

| Metric | Result |
|---|---:|
| OSM elements downloaded | 108 |
| Healthcare features inside study area | 70 |
| Unique OSM records | 70 |
| Minimum required features | 15 |
| Requirement | Satisfied |

**Category-wise distribution:**

| Category | Count |
|---|---:|
| Hospital | 28 |
| Pharmacy | 25 |
| Doctor | 4 |
| Dental Clinic | 3 |
| Clinic | 1 |
| Centre | 1 |
| Generic healthcare (`healthcare=yes`) | 8 |
| **Total** | **70** |

The generic healthcare records represent facilities such as urban health centres, sub-centres and Basthi Dawakhanas.

### 3. Data Quality and Proximity Analysis

A proximity analysis was performed using a 25-metre distance threshold.

| Metric | Result |
|---|---:|
| Total records | 70 |
| Nearby pairs identified | 17 |
| Confirmed duplicate records | 0 |
| Records deleted | 0 |

Nearby pairs were retained for manual review because different healthcare facilities can operate within the same building or campus.

A separate review dataset was created with three records flagged for further inspection:
- Udbhava Hospital
- Srikara Robotics and Super Speciality Hospital
- Titan Eye Plus

The original dataset was preserved.

### 4. Unnamed Healthcare Features

Three records had blank or placeholder names.

\[
\text{Unnamed percentage} = \frac{3}{70}\times100 = 4.29\%
\]

| Metric | Result |
|---|---:|
| Total features | 70 |
| Unnamed or placeholder-name features | 3 |
| Unnamed percentage | 4.29% |

### 5. Comparison with Existing Hyderabad Dataset

The new study-area dataset was compared with the original Hyderabad Nearby Services dataset.

| Metric | Result |
|---|---:|
| Original citywide records | 7,363 |
| Original citywide healthcare records | 1,783 |
| Original healthcare records inside selected wards | 54 |
| New study-area healthcare records | 70 |
| Original records with a nearby new record | 54 |
| New records with a nearby old record | 57 |
| Nearby record pairs | 85 |
| New records without a nearby old match | 13 |

A 25-metre threshold was used to identify nearby records.

These results represent spatial proximity, not confirmed record identity. Multiple records may match the same nearby facility.

### 6. Independent Facility Verification

Five healthcare records were checked against sources other than the original OSM extraction.

| Facility | Verification result |
|---|---|
| Udbhava Super Speciality Hospital | Verified |
| Srikara Robotics and Super Speciality Hospital | Verified |
| Titan Eye Plus | Category mismatch |
| True White Dental | Verified |
| Kindle Clinics | Verified |

Titan Eye Plus requires further category review because its OSM hospital classification may not accurately describe its service type.

Udbhava and Srikara are mapped at nearly the same location. Their relationship requires further investigation; neither record was deleted.

### 7. Output Files

The following files were generated:

- `analysis/study_area/selected_wards.geojson`
- `analysis/study_area/study_area.geojson`
- `data/study_area/healthcare_osm.csv`
- `data/study_area/healthcare_osm.geojson`
- `data/study_area/duplicate_pairs.csv`
- `data/study_area/healthcare_osm_review.csv`
- `data/study_area/dataset_comparison.csv`
- `data/study_area/independent_verification.csv`

### 8. Day 1 Conclusion

The selected study area contains 70 healthcare features collected from OpenStreetMap, exceeding the assignment's minimum requirement of 15 features.

Initial data-quality assessment identified 17 nearby pairs, three records with blank or placeholder names, and three records requiring manual review.

Comparison with the existing Hyderabad dataset identified 13 new records without a nearby match.

The original Hyderabad dataset and the downloaded raw study-area dataset have been preserved. No records were automatically deleted.

Further work will include spatial accessibility analysis, network-based service areas, H3 aggregation and deployment of the WebGIS application.

## Q1 – One Area, Four Areas

### 1.1 SQL Query

The combined study area was formed using Ward 106 (ward_id = 38) and Ward 109 (ward_id = 36) from the existing PostGIS wards table.

```sql
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
```

### 1.2 Results

| Measurement | Result |
|---|---:|
| EPSG:4326 geometry | 0.00131827 square degrees |
| Geography | 15.496621 km² |
| UTM Zone 44N (EPSG:32644) | 15.514772 km² |
| Web Mercator (EPSG:3857) | 17.126429 km² |
| Centre latitude | 17.474126° |
| Measured Mercator/UTM ratio | 1.103879 |
| Theoretical ratio | 1.099101 |

### 1.3 Interpretation

EPSG:4326 geometry returns an area in square degrees because it uses geographic coordinates. Geography calculates area using the Earth's spheroid.

UTM Zone 44N (EPSG:32644) provides a projected area measurement suitable for local metric analysis. The calculated area is 15.514772 km².

Web Mercator produces a larger area of 17.126429 km² because of projection-related area distortion.

The measured ratio between Web Mercator and UTM area is 1.103879, while the theoretical approximation using the study area's centre latitude is 1.099101. The values are close but not identical, with a relative difference of approximately 0.435%.

UTM Zone 44N is therefore the preferred CRS for metric area and distance calculations in this local study area.

**Earlier project distance CRS:** The original Hyderabad Nearby Services WebGIS used EPSG:4326 coordinates cast to the PostGIS `geography` type for both `ST_DWithin()` filtering and `ST_Distance()` calculations. Therefore, its nearby-service distances were calculated geodetically in metres rather than using projected UTM geometry.

### 1.4 Evidence

- SQL query: `sql/q1_area_measurements.sql`
- Output screenshot: `evidence/phase1/Q1_area_measurements.png`

### 1.5 Observation


## Q2 – Spatial Indexing and Query Performance

### 2.1 Objective

Evaluate the performance of spatial queries for finding buildings within 500 metres of healthcare facilities. Compare query execution before and after creating a GiST spatial index, and examine the performance difference between ST_DWithin() and ST_Distance().

### 2.2 Methodology

1. The healthcare and building geometries were transformed to WGS 84 / UTM Zone 44N (EPSG:32644) for metric distance calculations.
2. A spatial query using ST_DWithin() was executed to identify buildings within 500 metres of healthcare facilities before creating the spatial index.
3. A functional GiST index was created on the transformed building geometry.
4. The same ST_DWithin() query was executed again after creating the index.
5. A comparison query using ST_Distance() < 500 was also executed.
6. EXPLAIN ANALYZE was used to examine the query execution plans and execution times.

### 2.3 Results

The spatial queries returned 576 matching building records.

| Query | Execution time | Execution plan |
|---|---:|---|
| ST_DWithin() before index | 801.336 ms | Parallel Seq Scan |
| ST_DWithin() after index | 22.990 ms | Index Scan |
| ST_Distance() < 500 | 490.924 ms | Parallel Seq Scan |

The functional GiST index used was `phase1_buildings_utm44n_gix`.

### 2.4 Performance Comparison

The ST_DWithin() query execution time decreased from 801.336 ms to 22.990 ms after creating the GiST index.

Speedup = 801.336 / 22.990 = approximately 34.85 times.

The ST_Distance() comparison query took 490.924 ms and used a Parallel Sequential Scan.

### 2.5 Evidence

- Query results: `outputs/phase1/Q2_UTM_results.txt`
- Building counts: `outputs/phase1/Q2_UTM_building_counts_500m.csv`

## Q3 – Healthcare Data Quality and Comparison with Earlier Dataset

### 3.1 Objective

Assess the completeness and spatial quality of the newly collected healthcare dataset and compare it with the healthcare data used in the earlier Hyderabad Nearby Services project.

### 3.2 Name Completeness

The selected study area contained 70 healthcare features. Three records had blank or placeholder names.

| Metric | Result |
|---|---:|
| Total healthcare features | 70 |
| Unnamed or placeholder-name features | 3 |
| Named or usable-name features | 67 |
| Unnamed percentage | 4.29% |

Unnamed percentage = (3 / 70) × 100 = 4.29%.

### 3.3 Proximity and Duplicate Analysis

A 25-metre proximity threshold was used to identify potentially overlapping healthcare records.

| Metric | Result |
|---|---:|
| Total healthcare records | 70 |
| Nearby pairs identified | 17 |
| Confirmed duplicate records | 0 |
| Records automatically deleted | 0 |

Nearby pairs were treated as candidates for manual inspection rather than confirmed duplicates. Different healthcare facilities may operate within the same building or campus.

### 3.4 Comparison with Earlier Dataset

The newly collected healthcare dataset was compared spatially with the earlier Hyderabad Nearby Services dataset.

| Metric | Result |
|---|---:|
| Earlier citywide records | 7,363 |
| Earlier citywide healthcare records | 1,783 |
| Earlier healthcare records inside selected wards | 54 |
| New healthcare records inside selected wards | 70 |
| Earlier records with a nearby new record | 54 |
| New records with a nearby earlier record | 57 |
| Nearby candidate pairs | 85 |
| New records without a nearby earlier match | 13 |

The 25-metre matching threshold identified spatially nearby records. These matches do not establish that two records represent the same facility because multiple records can match one location.

### 3.5 Independent Facility Verification

Five healthcare facilities were checked against sources other than the original OSM extraction.

| Facility | Recorded verification |
|---|---|
| Udbhava Super Speciality Hospital | Verified |
| Srikara Robotics and Super Speciality Hospital | Verified |
| Titan Eye Plus | Category mismatch |
| True White Dental | Verified |
| Kindle Clinics | Verified |

Four facilities were verified, while Titan Eye Plus required category review. No confirmed closure or positional error was recorded in these checks.

### 3.6 Interpretation

The new dataset contains 70 healthcare features, compared with 54 healthcare records from the earlier project inside the same selected wards. The proximity analysis identified 17 nearby pairs, but none was confirmed as a duplicate. The comparison identified 13 new records without a nearby match in the earlier dataset, indicating that the newer extraction contains additional spatial records that require separate interpretation.

### 3.7 Evidence

- Healthcare dataset: `data/study_area/healthcare_osm.csv`
- Healthcare GeoJSON: `data/study_area/healthcare_osm.geojson`
- Proximity pairs: `data/study_area/duplicate_pairs.csv`
- Dataset comparison: `data/study_area/dataset_comparison.csv`
- Independent verification: `data/study_area/independent_verification.csv`

## Q4 – WMS 1.1.1 and 1.3.0 Axis-Order Difference

### 4.1 Objective

Demonstrate how the EPSG:4326 axis order differs between WMS 1.1.1 and WMS 1.3.0 when requesting the same map extent.

### 4.2 BoundingBox from GetCapabilities

The EPSG:4326 BoundingBox for `hyderabad:phase2_services` in the WMS 1.3.0 GetCapabilities response was:

| Parameter | Value |
|---|---:|
| minx | 17.440954208374023 |
| miny | 78.31365203857422 |
| maxx | 17.49517822265625 |
| maxy | 78.36315155029297 |

The values are in latitude-longitude order for EPSG:4326 in WMS 1.3.0.

### 4.3 Requests

**WMS 1.1.1 (EPSG:4326 – Longitude, Latitude order):**

`http://localhost:8085/geoserver/hyderabad/ows?service=WMS&version=1.1.1&request=GetMap&layers=hyderabad:phase2_services&styles=&srs=EPSG:4326&bbox=78.31365203857422,17.440954208374023,78.36315155029297,17.49517822265625&width=800&height=600&format=image/png`

**WMS 1.3.0 (EPSG:4326 – Latitude, Longitude order):**

`http://localhost:8085/geoserver/hyderabad/ows?service=WMS&version=1.3.0&request=GetMap&layers=hyderabad:phase2_services&styles=&crs=EPSG:4326&bbox=17.440954208374023,78.31365203857422,17.49517822265625,78.36315155029297&width=800&height=600&format=image/png`

Both requests represent the same geographic extent, but the BBOX coordinate order differs according to the WMS version.

### 4.4 Interpretation

WMS 1.1.1 uses longitude-latitude order for EPSG:4326 coordinates in the BBOX parameter. WMS 1.3.0 follows the EPSG:4326 axis definition, which is latitude-longitude.

Therefore, the same four BBOX values can be interpreted differently by the two WMS versions. This axis-order difference can result in an incorrect map extent if the coordinate order is not handled properly.

### 4.5 Evidence

- WMS 1.1.1 GetMap screenshot: `evidence/phase2/Q4_WMS_111.png`
- WMS 1.3.0 GetMap screenshot: `evidence/phase2/Q4_WMS_130.png`
- Capabilities response: WMS 1.3.0 GetCapabilities for `hyderabad:phase2_services`

---

## Q5 – WFS 2.0 Filter and Output Formats

### 5.1 Objective

Retrieve only named healthcare services within the study area using WFS 2.0 and compare the GeoJSON and GML 3.2 output formats.

### 5.2 Filter

The WFS request used the following filter:

`name IS NOT NULL AND name <> ''`

This excludes features with missing or empty names.

### 5.3 Request

WFS 2.0 GeoJSON:

`http://localhost:8085/geoserver/hyderabad/ows?service=WFS&version=2.0.0&request=GetFeature&typeNames=hyderabad:phase2_services&outputFormat=application/json&CQL_FILTER=name%20IS%20NOT%20NULL%20AND%20name%20%3C%3E%20%27%27`

For GML 3.2, the same filtered request was retrieved using the GML 3.2 output format supported by GeoServer.

### 5.4 Results

| Measurement | Result |
|---|---:|
| Total services in published layer | 70 |
| Named services returned | 67 |
| Unnamed services excluded | 3 |
| GeoJSON file size | 128,517 bytes (approximately 125.5 KB) |
| GML 3.2 file size | 132,477 bytes (approximately 129.4 KB) |

The WFS response reported `numberMatched = 67` and `numberReturned = 67`.

### 5.5 Coordinate Order

The first GeoJSON point had coordinates:

`[78.332069, 17.493487]`

GeoJSON uses longitude-latitude order.

The first GML 3.2 coordinate in the saved XML is `17.493487 78.332069` with srsName `urn:ogc:def:crs:EPSG::4326`. This is latitude-longitude order under the EPSG:4326 axis definition and represents the same location as the first GeoJSON coordinate `[78.332069, 17.493487]`, which uses longitude-latitude order.

### 5.6 Interpretation

Both formats returned the same 67 named healthcare services. GeoJSON was approximately 125.5 KB, while GML 3.2 was approximately 129.4 KB. GeoJSON is convenient for web mapping applications, while GML 3.2 is an XML-based format commonly used in OGC workflows.

### 5.7 Evidence

- GeoJSON: `evidence/phase2/named_services.geojson`
- GML 3.2: `evidence/phase2/named_services_gml32.xml`
- WFS screenshots and request output: `evidence/phase2/`

## Supplementary Phase 2 - Rule-Based SLD Styling Verification

GeoServer was configured with the `healthcare_services` style for the published layer `hyderabad:phase2_services`.

The WMS GetCapabilities response returned HTTP 200 and listed the `healthcare_services` style with the title **Named and Unnamed Healthcare Services**.

A WMS GetMap request was then executed using:
- Workspace: `hyderabad`
- Layer: `hyderabad:phase2_services`
- Style: `healthcare_services`
- WMS version: 1.1.1
- Output format: PNG
- Image dimensions: 1000 ? 800 pixels

The request returned HTTP 200 with content type `image/png`. The resulting valid PNG file was 24,820 bytes.

The rendered image visually shows blue markers for named healthcare services and orange markers for unnamed healthcare services, demonstrating the rule-based styling.

**Evidence:** `evidence/phase2/Q5_healthcare_services_SLD_GetMap.png`

## Q6 – Straight-Line Distance vs Walking Network

### 6.1 Objective

Compare the nearest healthcare service identified using straight-line distance with the nearest service identified using the walking network.

### 6.2 Methodology

1. Generate 30 random points inside the study area using a fixed random seed of 20261119.
2. Identify the nearest healthcare service for each point using straight-line distance.
3. Identify the nearest healthcare service using the walking network.
4. Compare the selected nearest services and calculate the ratio of network distance to straight-line distance.

### 6.3 Results

| Metric | Result |
|---|---:|
| Random points tested | 30 |
| Cases where nearest service differed | 14 |
| Percentage of differing cases | 46.67% |
| Median network-to-straight-line distance ratio | 1.896 |
| Maximum distance ratio | 6.777 |

### 6.4 Interpretation

The nearest healthcare service identified by straight-line distance differed from the network-based nearest service in 14 out of 30 cases. The median network-to-straight-line distance ratio was 1.896, indicating that walking-network distances were generally longer than straight-line distances.

The maximum ratio of 6.777 demonstrates that straight-line distance can substantially underestimate actual walking distance where road connectivity and barriers affect access.

The worst-case point was exported as a GeoJSON feature for mapping. The specific physical barrier responsible for the worst-case difference should be identified through inspection of the exported map rather than assumed.

### 6.5 Evidence

- `analysis/phase3/Q6_random_point_comparison.csv`
- `analysis/phase3/Q6_random_points.geojson`
- `analysis/phase3/Q6_worst_case.geojson`

---

## Q7 – Healthcare Coverage and the Modifiable Areal Unit Problem (MAUP)

### 7.1 Objective

Compare healthcare accessibility coverage using network-based walking distances and straight-line buffers. Examine how the coverage results vary across H3 resolutions 8 and 9.

### 7.2 Methodology

1. Use a walking speed of 4.8 km/h and a 15-minute urban walking threshold.
2. Calculate the corresponding walking distance of 1,200 metres.
3. Generate network-based accessibility results and straight-line buffers.
4. Create H3 grids at resolutions 8 and 9.
5. Use building footprint area as a proxy for population because the WorldPop raster was unavailable.
6. Calculate the percentage of building-footprint-area proxy covered by each accessibility scenario.

### 7.3 Results

| Metric | H3 Resolution 8 | H3 Resolution 9 |
|---|---:|---:|
| Number of H3 cells | 18 | 145 |
| Network coverage at 4.8 km/h | 65.34% | 75.12% |
| Straight-line buffer coverage | 92.61% | 92.76% |
| Network area-proxy coverage outside threshold | 34.66% | 24.88% |
| Straight-line area-proxy coverage outside threshold | 7.39% | 7.24% |

### 7.4 Ward and H3 Aggregation

The network coverage results were also aggregated by ward and H3 resolution. The ward-level output is available in:

`analysis/phase3/Q7_ward_coverage.csv`

The H3 coverage summary is available in:

`analysis/phase3/Q7_H3_coverage_summary.csv`

The worst-served populated H3 cell identified in the analysis was:

`8960a24a217ffff`

Its network distance to the nearest healthcare service was approximately 3,249.25 metres, with a building-footprint area of approximately 8,571.32 square metres.

### 7.5 Interpretation

The straight-line buffer method estimated substantially higher coverage than the walking-network method. This indicates that straight-line distance can overestimate practical healthcare accessibility because it does not account for road connectivity.

The coverage percentage also differed between H3 resolutions 8 and 9. This demonstrates that the spatial unit and resolution influence the accessibility results, illustrating the Modifiable Areal Unit Problem (MAUP).

The coverage percentages represent building-footprint-area-weighted estimates, not actual population coverage. They should therefore be interpreted as a spatial proxy.

### 7.6 Evidence

- `analysis/phase3/phase3_h3_access_res8_res9.geojson`
- `analysis/phase3/Q7_H3_coverage_summary.csv`
- `analysis/phase3/Q7_ward_coverage.csv`
- `analysis/phase3/PHASE3_summary.txt`

---

## Q8 – Accessibility for Elderly Walkers

### 8.1 Objective

Evaluate how healthcare accessibility changes when walking speed is reduced from 4.8 km/h to 3.6 km/h, representing a slower walking-speed scenario.

### 8.2 Methodology

1. Set walking speed to 3.6 km/h.
2. Retain the 15-minute walking-time threshold.
3. Calculate the new walking-distance threshold of 900 metres.
4. Recalculate network-based accessibility.
5. Compare the results with the 4.8 km/h scenario.

### 8.3 Results

| Metric | H3 Resolution 8 | H3 Resolution 9 |
|---|---:|---:|
| Coverage at 4.8 km/h | 65.34% | 75.12% |
| Coverage at 3.6 km/h | 59.98% | 72.38% |
| Coverage reduction | 5.36 percentage points | 2.74 percentage points |

### 8.4 Interpretation

Reducing the walking speed from 4.8 km/h to 3.6 km/h reduced the network-based healthcare coverage at both H3 resolutions.

The coverage reduction was 5.36 percentage points at resolution 8 and 2.74 percentage points at resolution 9. This indicates that accessibility estimates are sensitive to the assumed walking speed.

The H3 cells with lower network accessibility highlight locations where slower walkers may face greater difficulty reaching healthcare facilities. The results can help identify areas that may require improved pedestrian connectivity or additional healthcare services.

### 8.5 Evidence

- `analysis/phase3/isochrones_3_6_kmh_15min.geojson`
- `analysis/phase3/straight_buffers_900m.geojson`
- `analysis/phase3/phase3_h3_access_res8_res9.geojson`
- `analysis/phase3/PHASE3_summary.txt`

## Q9 – Building Layer Performance Benchmark

### Objective

Compare three methods of delivering the same Hyderabad building layer:

1. GeoServer tiled WMS (PNG)
2. GeoServer WFS (GeoJSON)
3. pg_tileserv MVT (Mapbox Vector Tiles)

The tests were performed at zoom levels 12, 14 and 16 where applicable, using Chrome Developer Tools Network panel.

### Results

#### A. GeoServer WMS (PNG)

| Zoom level | Requests | Transferred |
|---|---:|---:|
| 12 | 21 | 615 KB |
| 14 | 12 | 227 KB |
| 16 | 6 | 137 KB |

#### B. GeoServer WFS (GeoJSON)

| Test | Requests | Transferred | Response time |
|---|---:|---:|---:|
| Single GeoJSON request | 1 | 1,025 KB | 1.52 s |

#### C. pg_tileserv MVT

| Zoom level | Requests | Transferred |
|---|---:|---:|
| 12 | 4 | 261 KB |
| 14 | 2 | 50.3 KB |
| 16 | 8 | 58.1 KB |

### Additional Repeat Test - Zoom 12

A repeat WMS and MVT test was performed using the same browser viewport, map centre and zoom level, with Chrome DevTools cache disabled.

| Metric | WMS PNG | MVT PBF |
|---|---:|---:|
| Map idle time | 0.94 s | 4.29 s |
| Total requests | 6 | 5 |
| Successful requests | 6 | 4 |
| Cancelled requests | 0 | 1 |
| Transferred | 59.7 KB | 261 KB |
| Resources | 56.2 KB | 630 KB |

All six WMS requests returned HTTP 200. For MVT, four requests returned HTTP 200 and one request was cancelled with zero bytes transferred.

The map idle time is measured from adding the selected layer until MapLibre fires its idle event. It includes client-side loading and rendering and is not a server-only response-time measurement.

In this particular repeat test, WMS reached the idle state sooner and transferred fewer bytes than MVT. This is an observed result for the tested viewport and should not be generalised to every map extent or zoom level. The earlier benchmark results above are retained as separate recorded runs.

**Additional timing evidence:** `evidence/phase4/Q9_Z12_timing_observations.txt`
**MVT timing screenshot:** `evidence/phase4/Q9_MVT_Z12_timing.png`

### Interpretation

WFS delivered the building dataset in a single GeoJSON response, resulting in approximately 1 MB of transferred data.

WMS delivered raster image tiles. The number and size of requests varied with the zoom level and visible map extent.

pg_tileserv delivered vector tiles in PBF format. At zoom levels 14 and 16, the transferred data was substantially smaller than the WFS GeoJSON response.

Vector tiles provide a more efficient delivery approach for interactive map visualisation because the client receives only the data needed for the visible map tiles rather than the complete GeoJSON dataset.

### Limitations

- Measurements depend on the browser viewport, map extent, cache state and network conditions.
- The request counts are specific to the recorded test runs.
- Basemap and unrelated browser requests should not be included in the selected layer's measurements.
- These measurements are illustrative observations, not controlled server-side benchmarks.

### Evidence

Screenshots are stored in `evidence/phase4/`:

- Q9_WMS_Z12.png
- Q9_WMS_Z14.png
- Q9_WMS_Z16.png
- Q9_WFS_GeoJSON.png
- Q9_MVT_Z12.png
- Q9_MVT_Z14.png
- Q9_MVT_Z16.png

### Measurement Notes

The measurements were collected using Chrome Developer Tools Network panel. The WFS GeoJSON request transferred approximately 1,025 KB and took 1.52 seconds. The WMS and MVT request counts and transferred sizes were recorded at zoom levels 12, 14 and 16. These measurements depend on the browser viewport, map extent, cache state and network conditions. The recorded WMS totals should be checked against the WMS-filtered screenshots to ensure unrelated page requests are excluded. Response times for individual WMS and MVT tests were not separately recorded.
## Q10. Single-Stage and Multi-Stage Docker Image Comparison

Two builds of the same static WebGIS client were created to compare a full-base single-stage image with a slim Alpine multi-stage image. Both images contain the same five website files.

### Final comparison

| Measurement | Full-base single-stage | Alpine multi-stage |
|---|---:|---:|
| Base image | nginx:latest | alpine:3.21 build, nginx:alpine runtime |
| Docker image size | 240,961,599 bytes | 94,041,077 bytes |
| Decimal image size | 240.96 MB | 94.04 MB |
| Website files | 5 | 5 |
| Website directory size | 224 KiB | 224 KiB |

The Alpine multi-stage image was smaller by **146,920,522 bytes (approximately 146.92 MB)**, representing a **60.97% reduction** compared with the full-base single-stage image.

### Dockerfile configurations

The temporary full-base single-stage build used:

    FROM nginx:latest
    COPY client/ /usr/share/nginx/html/
    EXPOSE 80
    CMD ["nginx", "-g", "daemon off;"]

The Alpine multi-stage build used the repository Dockerfile:
- Build stage: alpine:3.21
- Runtime stage: nginx:alpine
- Website files were copied from the build stage into the final Nginx runtime image.

The repository Dockerfile and Docker Compose deployment were not modified for this comparison.

### Docker history observations

The full-base image history showed larger Debian/Nginx runtime layers, including approximately 88.8 MB and 87.7 MB layers. The website COPY layer was approximately 242 KB.

The Alpine multi-stage image history showed an approximately 52.4 MB Nginx/runtime package layer, a 5.75 MB package layer and a 9.09 MB Alpine base filesystem layer. The website COPY layer was approximately 242 KB. The separate preparation stage was not included in the final image.

### Interpretation

Both images contain the same five website files, with a website directory size of approximately 224 KiB. The principal difference is the size of the base operating system and Nginx runtime packaging. The Alpine-based final image therefore has a substantially smaller footprint.

The observed 60.97% reduction compares the complete full-base single-stage design against the Alpine multi-stage design. Since both the base image and build strategy differ, the entire reduction cannot be attributed to multi-stage construction alone.

### Preliminary same-base experiment

An earlier experiment compared single-stage and multi-stage images using Alpine-based Nginx runtimes. Their recorded sizes were 93,676,477 bytes and 93,671,942 bytes respectively, a difference of 4,535 bytes (approximately 0.0048%). This preliminary comparison is retained for completeness but did not satisfy the assignment's requested full-base versus slim/Alpine multi-stage comparison.

### Evidence

- evidence/docker/Q10_full_vs_alpine_comparison.txt - exact image sizes, website content checks and Docker history output.


## Q11. Kubernetes Self-Healing and Persistent Storage

A two-node Kubernetes cluster was created through Docker Desktop Kubernetes. PostGIS 16 with PostGIS 3.7 was deployed using a StatefulSet in the `webgis-k8s` namespace. The cluster used Docker Desktop Kubernetes rather than kind or minikube.

Configuration:
- Database: `webgis_k8s`
- Namespace: `webgis-k8s`
- StatefulSet: `postgis`
- Storage: 1 GiB PersistentVolumeClaim
- StorageClass: `standard`
- Access mode: ReadWriteOnce
- Credentials: Kubernetes Secret `postgres-secret`

**StatefulSet and PVC persistence test:**

A test table named `q11_persistence_test` was created in the StatefulSet database and a record was inserted. The `postgis-0` pod was deleted. Kubernetes recreated the pod, and the PVC remained Bound. After the replacement pod became Ready, querying `q11_persistence_test` returned the original record.

This confirms that the database data persisted across pod deletion and recreation because it was stored on the PersistentVolumeClaim.

**Deployment and emptyDir data-loss test:**

A separate PostgreSQL Deployment using `emptyDir` storage was tested. A table named `q11_emptydir_test` was created and a record was inserted. The `emptyDir` pod was deleted, and the Deployment created a replacement pod. After the replacement became Ready, querying the test table returned `relation "q11_emptydir_test" does not exist`.

This confirms that the temporary `emptyDir` volume did not retain the database data after pod replacement.

**Conclusion:** PVC-backed storage retained the test record after StatefulSet pod recreation, whereas `emptyDir` storage lost the test table after Deployment pod replacement. This demonstrates why persistent volumes are appropriate for database workloads and `emptyDir` is intended for temporary data.

The WebGIS client was also deployed using an Nginx Deployment, a ConfigMap and a ClusterIP Service. The dashboard was accessed locally through port-forwarding at `http://localhost:8087`.

Observed PostGIS pod recovery time in the earlier stopwatch trial: approximately **18.5 seconds**. This persistence test did not independently measure recovery time.

**Timing evidence note:** The 18.5-second recovery time was measured with a PowerShell stopwatch while polling pod readiness. Separate timestamps from `kubectl get pods -w` were not captured.

**Additional evidence:** `evidence/phase5/Q11_persistence_test.txt` contains the pod/PVC status and the results of both persistence checks.

## Q12. PMTiles and HTTP Range Request Performance

The H3 accessibility GeoJSON was converted into a PMTiles vector tile archive using Tippecanoe 2.80.0.

- Input: `analysis/phase3/phase3_h3_access_res8_res9.geojson`
- Input features: 163
- Minimum zoom: 0
- Maximum zoom: 14
- Output: `client/tiles/h3_access.pmtiles`
- Archive size: 81,219 bytes

The archive was generated successfully and published through GitHub Pages. HTTP Range support was verified using curl.exe.

- HTTP status: 206 Partial Content
- Requested byte range: 0-16383
- Content-Range: bytes 0-16383/81219
- Bytes downloaded: 16,384
- Accept-Ranges: bytes
- Full archive size: 81,219 bytes

The request transferred approximately 20.17% of the archive rather than its entire contents. This demonstrates that GitHub Pages supports partial byte-range delivery for the PMTiles archive.

Compared with Q9, the PMTiles archive is approximately 79.3 KiB, while the earlier WFS response was approximately 1,025 KB. These represent different delivery methods and data scopes, so the comparison is indicative rather than a direct like-for-like benchmark.

**Additional combined PMTiles archive:**

A second PMTiles archive was generated using Tippecanoe 2.80.0 through Docker. It combines the H3 accessibility polygons and healthcare service points in two separate named layers.

- H3 input: `analysis/phase3/phase3_h3_access_res8_res9.geojson` (163 polygons)
- Healthcare input: `data/study_area/healthcare_osm.geojson` (70 points)
- Total features: 233
- Vector tile layers: `h3_access` and `healthcare_services`
- Zoom range: 0-14
- Output: `client/tiles/hyderabad_h3_services.pmtiles`
- Archive size: 98,552 bytes

The original `h3_access.pmtiles` archive was preserved. The combined archive is an additional static-delivery artifact; the existing live MapLibre client continues to use pg_tileserv and pg_featureserv for its operational layers. The combined archive was published through GitHub Pages and verified using curl.exe.

- Public URL: `https://isharambhal.github.io/hyderabad-nearby-webgis-assignment/tiles/hyderabad_h3_services.pmtiles`
- Full request: HTTP 200 OK
- Full archive size: 98,552 bytes
- Accept-Ranges: bytes
- Partial request: HTTP 206 Partial Content
- Requested range: bytes 0-16383
- Content-Range: `bytes 0-16383/98552`
- Bytes transferred: 16,384 (approximately 16.62% of the archive)

This confirms that the combined archive is publicly accessible and supports partial byte-range delivery.

**Additional evidence:** `evidence/phase5/Q12_combined_PMtiles_range.txt` records the public URL and the observed HTTP response headers.
