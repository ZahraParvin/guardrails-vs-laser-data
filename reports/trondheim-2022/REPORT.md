# FV6650 in Trondheim: NVDB vs 2022 laser data

## Results

**No NVDB discrepancies are confirmed.** Analysis of 26 guardrail objects, totalling 1,022.14 m, produced one unsupported 7 m interval and 16 possible unregistered objects. After follow-up with road photographs, laser profiles and spring aerial imagery, 12 candidates and the interval were rejected during screening. Four candidates remain uncertain. The [follow-up report](FOLLOWUP.md) explains the six new decisions and their limitations.

This is a real data pipeline and a documented trial of a simple detector. Buildings, vehicles and vegetation can be mistaken for guardrails. The assessments were made with Codex and are **not independent expert review or field-verified ground truth**.

| Check | Count |
|---|---:|
| Unsupported intervals ≥ 5 m | 1, length 7 m |
| Candidates away from nearby registered lines | 16 |
| Candidates rejected during review | 12 |
| Unsupported intervals rejected as missing guardrails | 1 |
| Uncertain candidates | 4 |
| Uncertain unsupported intervals | 0 |
| Confirmed registry discrepancies | 0 |

![Overview of the real study area](overview.png)

## Data selection

- **Road section:** FV6650 objects in the sample NVDB extract. Approximately 1.45 km north–south, with 1.02 km of registered guardrail; this is not 1.02 km of continuous road. An urban area with housing and a railway, selected before interpreting results because a dense laser survey and contemporary aerial imagery were available.
- **Laser:** NDH Trondheim 30pkt 2022, project 5765, Terratec for Kartverket. Nominal density: 30 points/m². The [project report](https://hoydedata.no/LaserServices/REST/DownloadPDF.ashx?projectId=5765) records flights on **29–30 July 2022**. The metadata field for the last flight date gives 29 July; the report provides the more complete period.
- **NVDB:** type 5, retrieved on 15 September 2026. Study subset: 26 objects. Separate reference extract: all 48 guardrail objects around the corridor, including neighbouring roads.
- **Aerial imagery:** “Trondheim kommune 2022”, project 3999, project date **24 August 2022**, pixel size 0.10 m, owned by Trondheim municipality. The date comes from project metadata; individual image date fields are empty in the raster catalogue. Source: [Norge i bilder](https://norgeibilder.no/), [API documentation](https://backend-api.klienter-prod-k8s2.norgeibilder.no/swagger/index.html).

### Extraction and quality checks

The source is Kartverket's public **Potree 1.7 viewer dataset**, with LAZ nodes. All linked hierarchy levels overlapping the 25 m buffer around the lines were read. No coarse display resolution was selected. The extract includes 94 hierarchy files and 1,363 LAZ files, approximately 58.7 MB of compressed point data.

- 11,876,117 LAZ records read from source files.
- 6,753,709 points retained within the 25 m corridor.
- 3,761,844 points analysed within the 15 m corridor.
- 920,208 class-2 points in the 25 m extract.
- 1,729 additional records with identical XYZ in the 25 m extract, approximately 0.026%. No deduplication was performed; identical coordinates may also belong to different returns.

**The viewer dataset has not been compared with the original delivery.** Hierarchy point counts differ from actual LAZ records in 1,019 nodes: the index lists 4,857,892 points in total, while the files contain 11,876,117. The cause has not been established. The analysis uses actual LAZ records. All available links were followed, but this does not prove that the dataset is identical to the original survey.

The source uses UTM32 / NN2000 according to the project metadata and report. The LAZ nodes lack a CRS declaration. The script therefore documents the CRS from the source and transforms XY from EPSG:25832 to EPSG:25833. Z remains in NN2000. Actual XY coordinates were checked against the octree node bounds. The URL, SHA-256 and point count for each node are stored locally in `data/trondheim_2022/provenance.json`.

## Method and assessments

Default parameters were retained: 0.3–1.5 m above the nearest class-2 point, a 1.5 m search radius, at least five points for support and at least 5 m of consecutive missing support. DBSCAN candidates must lie more than 5 m from registered lines, be at least 8 m long and have a length-to-width ratio of at least four. This is a heuristic, not a trained guardrail model.

### G01 – 7 m without laser support, rejected as a missing guardrail

Object **671258022**, road reference **FV6650 S2D1 m842–856**. The flag covers 0–7 m along the geometry part; this is not calculated official road chainage. The road photograph from **20 July 2022** shows a steel rail with mesh panels at the relevant frontage beneath the tree canopy, consistent with the NVDB description. The flag is rejected as a claim of a missing guardrail. The laser profile shows many high returns and few within the search band; occlusion is a plausible cause, but has not been isolated. The road photograph was taken 9–10 days before the laser survey and does not prove the condition on the flight date itself. See the [image and source](FOLLOWUP.md#g01-barrier-present-despite-low-laser-support).

![Laser profile for the unsupported interval](gap_diagnostic.png)

### C01, C09 and C12 – building-related candidates

The polygons follow or cross building surfaces and garden/terrace areas. Rejected during imagery review. A long, narrow cluster is not enough to identify a guardrail; the precise mechanism in the ground estimate has not been isolated.

### C06 and C13–C15 – candidates in traffic lanes

These lie within the carriageway, rather than along a fixed road edge. Rejected as fixed guardrails based on the image and road layout. Vehicles in the laser survey are a plausible explanation, but different acquisition dates mean this has not been verified.

### Vegetation and boundary objects

The follow-up rejects C02, C04, C08, C10 and C16 as vegetation/terrain candidates with medium screening confidence. The 2022 laser profiles and spring aerial imagery from 2024/2026 support this interpretation. Later images provide supporting evidence, not ground truth for 2022. C03, C05, C07 and C11 remain `uncertain`; they require close-up images and dated documentation of the boundary object.

All 17 assessments are in [review.csv](review.csv), including coordinates, date, source and reasoning. The [first-pass review](review_first_pass.csv) is preserved. The [evidence manifest](evidence_manifest.json) records follow-up road photographs, raster IDs, dates and file hashes. Image sheets are stored locally in `outputs/real/review/`; aerial images have not been copied into the publishable report directory.

### Correction during validation

The first run used only FV6650 as the registry reference and produced 18 candidates. Imagery review revealed a boundary object already registered on another road. The reference set was expanded to all 48 nearby guardrail objects; the rerun produced 16 candidates. A regression test covers this. Thresholds were not adjusted to match the labels.

## Sensitivity

| Search radius | Min. points | Flags ≥ 5 m | Flagged length |
|---|---:|---:|---:|
| 1.0 m | 5 | 4 | 31 m |
| 1.0 m | 20 | 13 | 99 m |
| **1.5 m** | **5** | **1** | **7 m** |
| 1.5 m | 10 | 2 | 15 m |
| 1.5 m | 20 | 7 | 53 m |
| 2.0 m | 5 | 1 | 6 m |

All nine combinations are in [sensitivity.csv](sensitivity.csv). Results depend on the parameters. A large radius can receive support from other objects. An independent ground-truth sample is needed before the thresholds can be considered calibrated. Precision and recall have not been measured; supported and unflagged control locations have not been systematically reviewed.

## Runtime and memory

Corrected local pipeline: **6.39 seconds**, including LAZ reading, cropping, ground estimation, support analysis, DBSCAN, export and plotting. Measured peak RSS: **618.8 MiB**, sampled every 50 ms; this is not a guaranteed upper bound. Imports and network downloads are excluded. Results depend on the machine and cache.

## Reproduce the study

Install the project with `.[dev]`. From the root directory, using the environment's Python:

```powershell
python -m guardrails fetch --bbox "269000,7040000,271000,7042000" --output data/nvdb
python scripts/download_study.py
python -m guardrails fetch --bbox "268915,7040315,269280,7041840" --output data/trondheim_2022/reference_nvdb
python scripts/run_real.py
python scripts/analyse_study.py
python scripts/review_study.py outputs/real
python scripts/report_study.py
```

New NVDB extracts may change the results. LAZ nodes are cached. `report_study.py` reproduces explicit assessments from this review; it does **not perform automated visual validation**. New source data must be reviewed again before using the labels.

## Further validation

Four locations remain in [field_checks.csv](field_checks.csv): C03, C05, C07 and C11. Available 2022 road photographs have been checked; they do not show these boundary objects clearly enough. Close-up photographs from the access roads and historical documentation are needed. Also compare with the original LAZ export and assess a representative sample of supported and unsupported locations. NVDB from 2026 cannot automatically serve as ground truth for laser data from 2022.

## Sources and attribution

- Laser: **© Kartverket**, NDH Trondheim 30pkt 2022, Terratec. [Høydedata](https://hoydedata.no/LaserInnsyn2/) and [terms](https://www.kartverket.no/api-og-data/vilkar-for-bruk).
- NVDB: Contains data made available by **Statens vegvesen** under the Norwegian Licence for Open Government Data (NLOD).
- Local imagery review material: **© norgeibilder.no / Trondheim kommune**, project 3999. Aerial imagery consists of licensed products with their own terms; it is not a generic CC BY point cloud.
- Follow-up: [Road photographs, Statens vegvesen, NLOD](https://dataut.vegvesen.no/nb/dataset/vegbilder), acquired on 8 June and 20 July 2022; spring aerial imagery from Norge i bilder, projects 4629 and 5077. See the [follow-up report](FOLLOWUP.md).
