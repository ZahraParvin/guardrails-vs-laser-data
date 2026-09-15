"""Deterministic fictional data; no real-world claims."""
from pathlib import Path
import geopandas as gpd
import laspy
import numpy as np
from pyproj import CRS
from shapely.geometry import LineString


def make_demo(directory):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(42)
    origin = np.array([270000., 7040000.])
    line = LineString(origin + [[0, 0], [100, 0]])
    gpd.GeoDataFrame(dict(nvdb_id=["demo-1"], road_reference=["SYNTHETIC ROAD"]), geometry=[line], crs=25833).to_file(directory / "guardrails.gpkg", driver="GPKG")
    gx, gy = np.meshgrid(np.arange(-5, 106, .4), np.arange(-16, 17, .4))
    ground = np.column_stack([gx.ravel(), gy.ravel()])
    rail_x = np.arange(0, 100, .08)
    rail_x = rail_x[(rail_x < 35) | (rail_x > 55)]
    rail = np.column_stack([rail_x, rng.normal(0, .07, len(rail_x))])
    other_x = np.arange(65, 95, .04)
    other = np.column_stack([other_x, 9+rng.normal(0, .08, len(other_x))])
    xy = np.vstack([ground, rail, other])
    z = 100 + .02*xy[:, 0]
    z[len(ground):] += .75
    header = laspy.LasHeader(point_format=3, version="1.2")
    header.scales = [.001, .001, .001]
    header.offsets = [*origin, 100]
    header.add_crs(CRS.from_epsg(25833))
    las = laspy.LasData(header)
    las.x, las.y, las.z = xy[:, 0]+origin[0], xy[:, 1]+origin[1], z
    las.classification = np.r_[np.full(len(ground), 2), np.ones(len(rail)+len(other))].astype("uint8")
    las.write(directory / "tile.laz")
    return directory / "guardrails.gpkg", directory / "tile.laz"
