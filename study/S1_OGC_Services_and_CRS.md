# S1 – OGC Services and Coordinate Reference Systems (CRS)

## 1. Objective

To understand OGC web services, coordinate reference systems, and their application in the Hyderabad Nearby Services WebGIS project.

## 2. OGC Services

The Open Geospatial Consortium (OGC) develops standards that enable different GIS applications to share and access geographic information.

Three important services are:

| Service | Full form | Purpose |
|---|---|---|
| WMS | Web Map Service | Displays rendered map images |
| WFS | Web Feature Service | Provides geographic features and attributes |
| WCS | Web Coverage Service | Provides coverage data, such as elevation rasters |

### Application in my project

The Hyderabad WebGIS project uses PostgreSQL/PostGIS to store spatial data. GeoServer will be used to publish GIS layers using OGC services.

- WMS: Display map layers.
- WFS: Access healthcare facility features.
- WCS: Access elevation coverage data.

## 3. Coordinate Reference Systems

A Coordinate Reference System (CRS) defines how geographic locations are represented using coordinates.

### Geographic CRS – EPSG:4326

- Name: WGS 84
- Uses latitude and longitude.
- Units: Degrees.
- Suitable for storing and exchanging geographic coordinates.

### Projected CRS – EPSG:32644

- Name: WGS 84 / UTM Zone 44N
- Uses Easting and Northing.
- Units: Metres.
- Suitable for local distance and area calculations around Hyderabad.

Hyderabad lies within UTM Zone 44N, which extends from 78°E to 84°E.

## 4. Assign CRS vs Reproject Layer

**Assign CRS** defines or corrects the CRS associated with existing coordinates without transforming their numerical values.

**Reproject Layer** transforms coordinates from one CRS to another.

For this exercise, I used reprojection to convert my study-area polygon from EPSG:4326 to EPSG:32644.

## 5. Practical Exercise – QGIS CRS Transformation

**Study area:** Ward 106 – Serilingampally and Ward 109 – Hafeezpet, Hyderabad.

**Software:** QGIS 4.2.3

### Steps performed

1. Opened the existing study-area QGIS project.
2. Verified that the original study-area layer used EPSG:4326.
3. Selected Export → Save Features As.
4. Selected GeoJSON as the output format.
5. Selected EPSG:32644 as the target CRS.
6. Exported the transformed layer as `study_area_utm44n.geojson`.
7. Verified that the output layer used metres and contained one polygon.
8. Used the QGIS Field Calculator to compare planar and ellipsoidal area measurements.

### Coordinate comparison

| Property | Original | Reprojected |
|---|---|---|
| CRS | EPSG:4326 | EPSG:32644 |
| Coordinate units | Degrees | Metres |
| X minimum | 78.3108 | 214,403.29 |
| Y minimum | 17.4385 | 1,929,995.85 |
| X maximum | 78.3639 | 220,039.64 |
| Y maximum | 17.4959 | 1,936,359.15 |

These are layer bounding-box extents, not the transformed coordinates of one individual point.

## 6. Area Calculation

Two QGIS expressions were compared.

**Planar area:**

```qgis
area($geometry) / 1000000
```

Result: **15.5148 km²**

**Ellipsoidal area:**

```qgis
$area / 1000000
```

Result: **15.4966 km²**

The difference is approximately 0.0182 km² (0.12%).

The planar calculation uses projected geometry coordinates, while the ellipsoidal calculation uses the project's WGS 84 ellipsoid measurement settings.

For the study-area summary, I report **15.5148 km² as the planar area in EPSG:32644**, with the method stated explicitly.

## 7. WMS Axis Order

WMS versions can interpret EPSG:4326 bounding boxes differently.

- WMS 1.1.1 commonly uses longitude, latitude order for EPSG:4326.
- WMS 1.3.0 uses latitude, longitude order for EPSG:4326.

This will be tested later using GeoServer GetMap requests.

## 8. Practical Evidence

The CRS transformation screenshot is stored at:

`evidence/day1/08_crs_reprojection.png`

The original and projected study-area datasets are stored under:

`analysis/study_area/`

## 9. Learning Outcomes

After completing this exercise, I can:

- Explain the difference between WMS, WFS and WCS.
- Distinguish geographic and projected CRS.
- Explain why Hyderabad uses UTM Zone 44N.
- Differentiate assigning a CRS from reprojecting a layer.
- Reproject a GeoJSON layer in QGIS.
- Compare planar and ellipsoidal area calculations.

## 10. Pending Practical Work

- Test WMS 1.1.1 and 1.3.0 axis order using GeoServer.
- Complete the remaining Phase 0 study notes and container labs.
