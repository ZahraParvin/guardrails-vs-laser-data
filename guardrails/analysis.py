"""Heuristic screening; outputs are candidates requiring visual review."""
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely
from scipy.spatial import cKDTree
from sklearn.cluster import DBSCAN
from shapely.ops import substring

from .io import CRS_CODE, crop, read_lines


@dataclass
class Settings:
    buffer: float = 15.0
    chunk_size: int = 1_000_000
    band_lo: float = .3
    band_hi: float = 1.5
    radius: float = 1.5
    min_points: int = 5
    step: float = 1.0
    min_gap: float = 5.0
    max_ground_distance: float = 5.0
    cell: float = 2.0
    min_distance: float = 5.0
    cluster_eps: float = 1.5
    cluster_min_samples: int = 40
    min_candidate_length: float = 8.0
    min_elongation: float = 4.0
    max_analysis_points: int = 5_000_000
    max_cluster_points: int = 200_000

    def validate(self):
        for key, value in asdict(self).items():
            if not np.isfinite(value) or value <= 0:
                raise ValueError(f"{key} must be positive and finite")
        if self.band_lo >= self.band_hi or self.buffer <= self.min_distance + self.radius:
            raise ValueError("Invalid height band or search corridor too narrow")
        for key in ("chunk_size", "min_points", "cluster_min_samples", "max_analysis_points", "max_cluster_points"):
            if not isinstance(getattr(self, key), int):
                raise ValueError(f"{key} must be an integer")


def ground_height(cloud, cfg):
    xy, z, cl = cloud[:, :2], cloud[:, 2], cloud[:, 3]
    ground = cl == 2
    if ground.any():
        distance, idx = cKDTree(xy[ground]).query(xy, workers=-1)
        hag = z - z[ground][idx]
        hag[distance > cfg.max_ground_distance] = np.nan
        return hag, "classified-nearest"
    cells = np.floor((xy - xy.min(axis=0)) / cfg.cell).astype(np.int64)
    df = pd.DataFrame(dict(ix=cells[:, 0], iy=cells[:, 1], z=z))
    estimates = df.groupby(["ix", "iy"])["z"].quantile(.05)
    ground_z = estimates.reindex(pd.MultiIndex.from_frame(df[["ix", "iy"]])).to_numpy()
    return z - ground_z, "cell-percentile-5 (unclassified, low confidence)"


def sample_support(lines, cloud, hag, cfg):
    band = (hag >= cfg.band_lo) & (hag <= cfg.band_hi) & ~np.isin(cloud[:, 3], [7, 18])
    band_tree = cKDTree(cloud[band, :2])
    observed_tree = cKDTree(cloud[np.isfinite(hag) & ~np.isin(cloud[:, 3], [7, 18]), :2])
    rows, parts = [], {}
    for row_id, row in lines.iterrows():
        geoms = list(row.geometry.geoms) if row.geometry.geom_type == "MultiLineString" else [row.geometry]
        for part_id, part in enumerate(geoms):
            if part.length <= 0:
                continue
            parts[(row_id, part_id)] = part
            # Midpoint of each interval; interval widths make coverage length-weighted.
            edges = np.append(np.arange(0, part.length, cfg.step), part.length)
            for start, end in zip(edges[:-1], edges[1:]):
                point = part.interpolate((start+end)/2)
                rows.append((row_id, part_id, str(row.nvdb_id), row.road_reference,
                             start, end, point.x, point.y))
    sp = pd.DataFrame(rows, columns=["row_id", "part_id", "nvdb_id", "road_reference", "from_m", "to_m", "x", "y"])
    if sp.empty:
        raise ValueError("No nonzero guardrail lines")
    xy = sp[["x", "y"]].to_numpy()
    sp["n_pts"] = band_tree.query_ball_point(xy, cfg.radius, return_length=True, workers=-1)
    sp["observed"] = observed_tree.query_ball_point(xy, cfg.radius, return_length=True, workers=-1) > 0
    sp["supported"] = sp.n_pts >= cfg.min_points
    sp["status"] = np.where(~sp.observed, "unknown", np.where(sp.supported, "supported", "unsupported"))
    return sp, parts, band


def gaps_from_samples(samples, parts, cfg):
    rows = []
    for key, group in samples.groupby(["row_id", "part_id"], sort=False):
        run = []
        def flush():
            if run and run[-1].to_m - run[0].from_m >= cfg.min_gap:
                a, b = run[0], run[-1]
                rows.append(dict(nvdb_id=a.nvdb_id, road_reference=a.road_reference,
                                 row_id=int(key[0]), part_id=int(key[1]), from_m=a.from_m,
                                 to_m=b.to_m, length_m=b.to_m-a.from_m,
                                 geometry=substring(parts[key], a.from_m, b.to_m)))
        for row in group.sort_values("from_m").itertuples():
            if row.status == "unsupported":
                run.append(row)
            else:
                flush()
                run = []
        flush()
    columns = ["nvdb_id", "road_reference", "row_id", "part_id", "from_m", "to_m", "length_m", "geometry"]
    result = gpd.GeoDataFrame(rows, columns=columns, geometry="geometry", crs=CRS_CODE)
    return result.sort_values("length_m", ascending=False).reset_index(drop=True)


def find_candidates(lines, cloud, band, cfg):
    xy = np.asarray(cloud[band, :2])
    if len(xy):
        # Exact distance to polylines, not approximate distance to samples.
        registered = shapely.union_all(lines.geometry.array)
        xy = xy[shapely.distance(shapely.points(xy), registered) > cfg.min_distance]
    if len(xy) > cfg.max_cluster_points:
        raise ValueError("Too many candidate points for DBSCAN; reduce study area")
    rows = []
    if len(xy) >= cfg.cluster_min_samples:
        labels = DBSCAN(eps=cfg.cluster_eps, min_samples=cfg.cluster_min_samples).fit_predict(xy)
        for label in sorted(set(labels) - {-1}):
            points = xy[labels == label]
            centered = points - points.mean(axis=0)
            _, _, axes = np.linalg.svd(centered, full_matrices=False)
            spread = np.ptp(centered @ axes.T, axis=0)
            length, width = float(max(spread)), float(min(spread))
            elongation = length / max(width, .1)
            if length >= cfg.min_candidate_length and elongation >= cfg.min_elongation:
                hull = shapely.MultiPoint(points).convex_hull
                if hull.geom_type != "Polygon":
                    hull = hull.buffer(.05)
                rows.append(dict(n_pts=len(points), length_m=length, elongation=elongation, geometry=hull))
    return gpd.GeoDataFrame(rows, columns=["n_pts", "length_m", "elongation", "geometry"], geometry="geometry", crs=CRS_CODE)


def run(lines_path, tile_path, output, cfg, synthetic=False, reference_lines_path=None):
    cfg.validate()
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    lines = read_lines(lines_path)
    reference_lines = read_lines(reference_lines_path) if reference_lines_path else lines
    stats = crop(tile_path, lines, output / "corridor_cloud.npy", cfg.buffer, cfg.chunk_size)
    if stats["kept"] > cfg.max_analysis_points:
        raise ValueError("Crop saved, but too many points for in-memory analysis; reduce study area")
    cloud = np.load(output / "corridor_cloud.npy", mmap_mode="r")
    hag, method = ground_height(cloud, cfg)
    samples, parts, band = sample_support(lines, cloud, hag, cfg)
    gaps = gaps_from_samples(samples, parts, cfg)
    candidates = find_candidates(reference_lines, cloud, band, cfg)
    gaps.to_file(output / "flagged_gaps.gpkg", driver="GPKG")
    candidates.to_file(output / "unregistered_candidates.gpkg", driver="GPKG")
    samples.to_csv(output / "samples.csv", index=False)
    lengths = samples.assign(length_m=samples.to_m-samples.from_m)
    support = lengths.pivot_table(index=["nvdb_id", "road_reference"], columns="status", values="length_m", aggfunc="sum", fill_value=0)
    for status in ["supported", "unsupported", "unknown"]:
        if status not in support:
            support[status] = 0.
    support["total_m"] = support[["supported", "unsupported", "unknown"]].sum(axis=1)
    support["support_fraction_observed"] = support.supported / (support.supported+support.unsupported).replace(0, np.nan)
    support.to_csv(output / "support_per_object.csv")
    review_path = output / "review_template.csv"
    review = gaps.head(20).drop(columns="geometry").copy()
    for name in ["verdict", "imagery_date", "imagery_source", "notes"]:
        review[name] = ""
    review.to_csv(review_path, index=False)
    summary = dict(synthetic=synthetic, created_utc=datetime.now(timezone.utc).isoformat(),
                   inputs=dict(guardrails=str(Path(lines_path).resolve()), laser=str(Path(tile_path).resolve()),
                               reference_guardrails=str(Path(reference_lines_path).resolve()) if reference_lines_path else None),
                   settings=asdict(cfg), crop=stats, ground_method=method,
                   flagged_count=len(gaps), flagged_length_m=float(gaps.length_m.sum()),
                   candidate_count=len(candidates), unknown_length_m=float(support.unknown.sum()),
                   calibration="Not visually reviewed; flags are not confirmed discrepancies")
    (output / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    plot_overview(lines, cloud, gaps, candidates, output / "overview.png", synthetic)
    return summary


def plot_overview(lines, cloud, gaps, candidates, path, synthetic):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D
    fig, ax = plt.subplots(figsize=(11, 7), layout="constrained")
    fig.set_facecolor("#f5f6f8")
    stride = max(1, len(cloud)//50000)
    ax.scatter(cloud[::stride, 0], cloud[::stride, 1], s=1, c="#bcc6cc", rasterized=True)
    lines.plot(ax=ax, color="#17658c", linewidth=2)
    if not gaps.empty:
        gaps.plot(ax=ax, color="#dc523f", linewidth=4)
    if not candidates.empty:
        candidates.boundary.plot(ax=ax, color="#b07812", linewidth=2)
    ax.legend(handles=[Line2D([0], [0], color=c, lw=3, label=l) for c, l in
                       [("#17658c", "NVDB lines"), ("#dc523f", "Unsupported stretches"), ("#b07812", "Unregistered candidates")]])
    ax.set(title="Guardrails vs laser data" + (" — SYNTHETIC DEMO" if synthetic else " — unreviewed candidates"),
           xlabel="Easting (m), EPSG:25833", ylabel="Northing (m)")
    ax.ticklabel_format(style="plain", useOffset=False)
    ax.set_aspect("equal")
    ax.grid(alpha=.15)
    fig.savefig(path, dpi=170)
    plt.close(fig)
