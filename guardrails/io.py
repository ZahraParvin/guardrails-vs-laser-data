"""Network ingestion and bounded-memory point-cloud cropping."""
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse

import geopandas as gpd
import laspy
import numpy as np
import requests
import shapely
from pyproj import CRS
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

CRS_CODE = 25833
BASE = "https://nvdbapiles.atlas.vegvesen.no/vegobjekter/api/v4"


def validate_bbox(bbox):
    values = tuple(float(v) for v in bbox.split(","))
    if len(values) != 4 or not np.isfinite(values).all():
        raise ValueError("bbox must contain four finite coordinates")
    a, b, c, d = values
    if not (a < c and b < d and 6_000_000 < b < d < 9_000_000):
        raise ValueError("Expected minx,miny,maxx,maxy in EPSG:25833 metres")
    if (c-a)*(d-b) > 100_000_000:
        raise ValueError("Choose a study area smaller than 100 square kilometres")
    return values


def fetch(bbox, output, client="guardrails-vs-laser-data", base=BASE):
    validate_bbox(bbox)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.headers.update({"Accept": "application/json", "X-Client": client})
    session.mount("https://", HTTPAdapter(max_retries=Retry(
        total=4, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])))
    url = base.rstrip("/") + "/vegobjekter/5"
    origin = urlparse(url).netloc
    params = dict(kartutsnitt=bbox, srid="UTM_33",
                  inkluder="lokasjon,geometri,egenskaper", antall=1000,
                  segmentering="true")
    objects, visited = [], set()
    while url:
        if url in visited:
            raise ValueError("NVDB pagination repeated a URL")
        if urlparse(url).netloc != origin or urlparse(url).scheme != "https":
            raise ValueError("Unexpected NVDB pagination origin")
        visited.add(url)
        response = session.get(url, params=params, timeout=60)
        response.raise_for_status()
        page = response.json()
        batch = page["objekter"]
        if not batch:
            break
        objects.extend(batch)
        link = (page.get("metadata", {}).get("neste") or {}).get("href")
        url = urljoin(response.url, link) if link else None
        params = None
    (output / "nvdb_raw.json").write_text(json.dumps(objects, ensure_ascii=False), encoding="utf-8")
    rows = []
    for obj in objects:
        geometry = obj.get("geometri", {})
        if not geometry.get("wkt"):
            continue
        # V4 UTM_33 uses compound EPSG:5973 (25833 + NN2000 height).
        if geometry.get("srid", CRS_CODE) not in (CRS_CODE, 5973):
            raise ValueError("NVDB returned an unexpected CRS")
        geom = shapely.from_wkt(geometry["wkt"])
        if geom.is_empty or geom.geom_type not in ("LineString", "MultiLineString"):
            continue
        refs = obj.get("lokasjon", {}).get("vegsystemreferanser", [])
        rows.append(dict(nvdb_id=str(obj["id"]),
                         road_reference="; ".join(r.get("kortform", "") for r in refs),
                         properties=json.dumps(obj.get("egenskaper", []), ensure_ascii=False),
                         geometry=shapely.force_2d(geom)))
    if not rows:
        raise ValueError("No guardrail line geometries found; check bbox and coverage")
    frame = gpd.GeoDataFrame(rows, crs=CRS_CODE)
    frame.to_file(output / "guardrails.gpkg", driver="GPKG")
    (output / "fetch_metadata.json").write_text(json.dumps(dict(
        bbox=bbox, crs=CRS_CODE, endpoint=base, client=client,
        retrieved_utc=datetime.now(timezone.utc).isoformat(),
        fetched_objects=len(objects), exported_lines=len(frame)), indent=2), encoding="utf-8")
    return frame


def read_lines(path):
    frame = gpd.read_file(path)
    if frame.crs is None or frame.crs.to_epsg() != CRS_CODE:
        raise ValueError("Guardrails must declare EPSG:25833")
    if frame.empty or "nvdb_id" not in frame:
        raise ValueError("Guardrails require nonempty geometries and nvdb_id")
    if not frame.geometry.geom_type.isin(["LineString", "MultiLineString"]).all():
        raise ValueError("Only line geometries are supported")
    if frame.geometry.is_empty.any() or frame.geometry.isna().any():
        raise ValueError("Empty line geometry")
    frame.geometry = shapely.force_2d(frame.geometry.array)
    if "road_reference" not in frame:
        frame["road_reference"] = ""
    return frame.reset_index(drop=True)


def inspect_las(path, chunk_size=1_000_000):
    counts = Counter()
    with laspy.open(path) as reader:
        header = reader.header
        for pts in reader.chunk_iterator(chunk_size):
            classes, n = np.unique(pts.classification, return_counts=True)
            counts.update(dict(zip(map(int, classes), map(int, n))))
        return dict(version=str(header.version), points=header.point_count,
                    crs=str(header.parse_crs()), mins=header.mins.tolist(),
                    maxs=header.maxs.tolist(), classes=dict(counts))


def crop(path, lines, output, buffer=15.0, chunk_size=1_000_000):
    """Stream to disk; only the cropped cloud is subsequently loaded for analysis."""
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    corridor = shapely.union_all(lines.geometry.buffer(buffer).array)
    shapely.prepare(corridor)
    minx, miny, maxx, maxy = corridor.bounds
    raw = output.with_suffix(".raw.tmp")
    seen = kept = 0
    try:
        with laspy.open(path) as reader, raw.open("wb") as sink:
            crs = reader.header.parse_crs()
            horizontal = crs.sub_crs_list[0] if crs is not None and crs.is_compound else crs
            if horizontal is None or not horizontal.equals(CRS.from_epsg(CRS_CODE)):
                raise ValueError("LAS/LAZ must declare EPSG:25833; reproject before running")
            for pts in reader.chunk_iterator(chunk_size):
                x, y = np.asarray(pts.x), np.asarray(pts.y)
                seen += len(pts)
                mask = (x >= minx) & (x <= maxx) & (y >= miny) & (y <= maxy)
                idx = np.flatnonzero(mask)
                idx = idx[shapely.intersects_xy(corridor, x[idx], y[idx])]
                block = np.column_stack((x[idx], y[idx], np.asarray(pts.z)[idx],
                                         np.asarray(pts.classification)[idx]))
                block.astype("float64").tofile(sink)
                kept += len(idx)
        if not kept:
            raise ValueError("No points overlap the guardrail search corridor")
        source = np.memmap(raw, dtype="float64", mode="r", shape=(kept, 4))
        target = np.lib.format.open_memmap(output, mode="w+", dtype="float64", shape=(kept, 4))
        for start in range(0, kept, chunk_size):
            target[start:start+chunk_size] = source[start:start+chunk_size]
        target.flush()
        del target, source
    finally:
        raw.unlink(missing_ok=True)
    return dict(seen=seen, kept=kept, buffer_m=buffer)
