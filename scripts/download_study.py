"""Download all intersecting Potree 1.x LAZ nodes, not a display-level sample.

The public Kartverket viewer is the source, not an original survey export.
Node counts/checksums and source metadata are retained for reproducibility.
No authentication or email-based export request is needed for these public files.
"""
from collections import deque
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import struct
import time

import geopandas as gpd
import laspy
import numpy as np
from pyproj import CRS, Transformer
import requests
import shapely
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

ROOT = Path(__file__).resolve().parents[1]
DIRECTORY = ROOT / "data" / "trondheim_2022"
BASE = "https://hoydedata.no/Potree_vol14/5765/6319cbe1-11b8-4057-8e02-8d9537881c48"


def node_path(name, step=5):
    indices = name[1:]
    groups = [indices[i:i+step] for i in range(0, len(indices)-step+1, step)]
    return "/".join(["data", "r", *groups, name])


def child_bounds(bounds, index):
    lo, hi = np.asarray(bounds[:3]), np.asarray(bounds[3:])
    half = (hi-lo)/2
    shift = np.array([bool(index & 4), bool(index & 2), bool(index & 1)]) * half
    return np.r_[lo+shift, lo+shift+half]


def decode_hierarchy(blob, name, bounds):
    if len(blob) % 5:
        raise ValueError("Invalid hierarchy length")
    queue = deque([(name, bounds)])
    nodes = {}
    for offset in range(0, len(blob), 5):
        if not queue:
            raise ValueError("Unexpected hierarchy record")
        current, box = queue.popleft()
        mask, count = struct.unpack_from("<BI", blob, offset)
        nodes[current] = dict(bounds=box.tolist(), mask=mask, points=count)
        for index in range(8):
            if mask & (1 << index):
                queue.append((current+str(index), child_bounds(box, index)))
    return nodes


def download(url, path):
    if path.exists():
        return path.read_bytes()
    session = requests.Session()
    session.mount("https://", HTTPAdapter(max_retries=Retry(total=3, backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504])))
    r = session.get(url, timeout=(15, 90))
    r.raise_for_status()
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_suffix(path.suffix+".part")
    partial.write_bytes(r.content)
    partial.replace(path)
    return r.content


def main():
    started = time.perf_counter()
    DIRECTORY.mkdir(parents=True, exist_ok=True)
    lines = gpd.read_file(ROOT / "data/nvdb/guardrails.gpkg")
    lines = lines[lines.road_reference.str.startswith("FV6650")].copy()
    lines.to_file(DIRECTORY / "guardrails.gpkg", driver="GPKG")
    # Buffer a little beyond the analysis corridor to avoid crop-edge effects.
    native_lines = lines.to_crs(25832)
    corridor = shapely.union_all(native_lines.geometry.buffer(25).array)
    shapely.prepare(corridor)
    metadata = json.loads(download(BASE+"/cloud.js", DIRECTORY / "cloud.json"))
    box = metadata["boundingBox"]
    bounds = np.array([box[k] for k in ["lx", "ly", "lz", "ux", "uy", "uz"]])
    step = metadata["hierarchyStepSize"]
    def overlaps(node):
        a, b, _, c, d, _ = node["bounds"]
        return shapely.intersects(corridor, shapely.box(a, b, c, d))
    pending = deque([("r", bounds)])
    hierarchy_seen, selected = set(), {}
    while pending:
        name, bounds = pending.popleft()
        if name in hierarchy_seen:
            continue
        hierarchy_seen.add(name)
        relative = node_path(name, step)+".hrc"
        blob = download(BASE+"/"+relative, DIRECTORY / "source_nodes" / relative)
        nodes = decode_hierarchy(blob, name, bounds)
        for key, value in nodes.items():
            if not overlaps(value):
                continue
            selected[key] = value
            if key != name and (len(key)-1) % step == 0 and value["mask"]:
                pending.append((key, np.array(value["bounds"])))
        print(f"Hierarchy: {len(hierarchy_seen)} files, {len(selected)} selected nodes", flush=True)
    ordered = sorted(selected, key=lambda key: (len(key), key))
    (DIRECTORY / "selected_nodes.json").write_text(json.dumps(selected, indent=2), encoding="utf-8")
    print(f"Downloading {len(ordered)} nodes, {sum(n['points'] for n in selected.values()):,} source points", flush=True)
    def fetch_node(name):
        relative = node_path(name, step)+".laz"
        path = DIRECTORY / "source_nodes" / relative
        blob = download(BASE+"/"+relative, path)
        return name, path, hashlib.sha256(blob).hexdigest(), len(blob)
    manifest = []
    header = laspy.LasHeader(point_format=3, version="1.2")
    header.scales = [.001, .001, .001]
    header.offsets = [269000, 7040000, 0]
    header.add_crs(CRS.from_epsg(5973))
    transform = Transformer.from_crs(25832, 25833, always_xy=True)
    seen = kept = 0
    target = DIRECTORY / "tile.laz"
    with ThreadPoolExecutor(max_workers=4) as pool, laspy.open(target, mode="w", header=header) as writer:
        for idx, (name, path, sha, size) in enumerate(pool.map(fetch_node, ordered)):
            las = laspy.read(path)
            # Viewer hierarchy counts can differ slightly from actual LAZ records.
            # Keep the actual records and expose each discrepancy in the manifest.
            x, y = np.asarray(las.x), np.asarray(las.y)
            box = selected[name]["bounds"]
            if np.any((x < box[0]-.02) | (x > box[3]+.02) | (y < box[1]-.02) | (y > box[4]+.02)):
                raise ValueError(f"Coordinates outside hierarchy bounds: {name}")
            mask = shapely.intersects_xy(corridor, x, y)
            n = int(mask.sum())
            if n:
                pts = laspy.ScaleAwarePointRecord.zeros(n, header=header)
                pts.x, pts.y = transform.transform(x[mask], y[mask])
                pts.z = np.asarray(las.z)[mask]
                for dim in ["classification", "intensity", "return_number", "number_of_returns", "red", "green", "blue"]:
                    if dim in las.point_format.dimension_names:
                        setattr(pts, dim, np.asarray(getattr(las, dim))[mask])
                writer.write_points(pts)
            seen += len(las.points)
            kept += n
            manifest.append(dict(node=name, url=BASE+"/"+node_path(name, step)+".laz",
                                 sha256=sha, bytes=size, hierarchy_points=selected[name]["points"],
                                 source_points=len(las.points), kept_points=n))
            if idx % 10 == 0:
                print(f"LAZ {idx+1}/{len(ordered)}, {kept:,} kept", flush=True)
    provenance = dict(project_id=5765, project_name="NDH Trondheim 30pkt 2022",
        source=BASE, source_type="public Potree 1.7 LAZ derivative, all intersecting hierarchy levels",
        source_horizontal_crs=25832, source_vertical_crs=5941, output_crs=5973,
        crs_evidence="Kartverket project metadata; Potree node headers lack CRS",
        nominal_points_per_m2=30, road_filter="FV6650 in original 2x2 km NVDB extract",
        buffer_m=25, hierarchy_files=len(hierarchy_seen), node_files=len(manifest),
        source_points=seen, kept_points=kept, download_seconds=time.perf_counter()-started,
        bytes=sum(n["bytes"] for n in manifest), nodes=manifest)
    (DIRECTORY / "provenance.json").write_text(json.dumps(provenance, indent=2), encoding="utf-8")
    print(json.dumps({k:v for k,v in provenance.items() if k != "nodes"}, indent=2), flush=True)


if __name__ == "__main__":
    main()
