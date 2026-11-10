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