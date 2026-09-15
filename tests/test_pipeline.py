import geopandas as gpd
import numpy as np
import pandas as pd
import pytest
from shapely.geometry import LineString, MultiLineString

from guardrails.analysis import Settings, ground_height, sample_support, gaps_from_samples, run
from guardrails.demo import make_demo
from guardrails.io import validate_bbox, crop


def test_demo_end_to_end(tmp_path):
    lines, tile = make_demo(tmp_path / "inputs")
    result = run(lines, tile, tmp_path / "results", Settings(chunk_size=503), synthetic=True)
    assert result["flagged_count"] == 1
    assert 15 <= result["flagged_length_m"] <= 22
    assert result["candidate_count"] == 1
    assert result["unknown_length_m"] == 0
    for name in ["flagged_gaps.gpkg", "unregistered_candidates.gpkg", "overview.png", "support_per_object.csv", "summary.json", "review_template.csv"]:
        assert (tmp_path / "results" / name).stat().st_size > 0


def test_unknown_coverage_is_not_a_gap():
    lines = gpd.GeoDataFrame(dict(nvdb_id=[1], road_reference=[""]), geometry=[LineString([(0, 0), (20, 0)])], crs=25833)
    cloud = np.array([[100., 100., 10., 2.]])
    samples, parts, _ = sample_support(lines, cloud, np.array([0.]), Settings())
    assert (samples.status == "unknown").all()
    assert gaps_from_samples(samples, parts, Settings()).empty


def test_multiline_gaps_never_bridge_parts():
    lines = gpd.GeoDataFrame(dict(nvdb_id=[1], road_reference=["demo"]), geometry=[MultiLineString([[(0, 0), (4, 0)], [(100, 0), (104, 0)]])], crs=25833)
    cloud = np.array([[x, 0., 0., 2.] for x in list(range(5))+list(range(100,105))])
    samples, parts, _ = sample_support(lines, cloud, np.zeros(len(cloud)), Settings())
    assert gaps_from_samples(samples, parts, Settings()).empty


def test_curved_gap_preserves_line():
    part = LineString([(0, 0), (5, 0), (5, 5)])
    samples = pd.DataFrame([dict(row_id=0, part_id=0, nvdb_id="1", road_reference="", from_m=0., to_m=10., status="unsupported")])
    gap = gaps_from_samples(samples, {(0, 0): part}, Settings()).iloc[0]
    assert gap.geometry.length == 10
    assert len(gap.geometry.coords) == 3


def test_fallback_preserves_input_order():
    cloud = np.array([[10, 0, 20, 1], [0, 0, 2, 1], [10, 0, 22, 1], [0, 0, 0, 1]], dtype=float)
    hag, method = ground_height(cloud, Settings())
    np.testing.assert_allclose(hag, [-.1, 1.9, 1.9, -.1])
    assert "percentile" in method


def test_remote_ground_is_unknown():
    hag, _ = ground_height(np.array([[0, 0, 10, 2], [100, 0, 11, 1]], dtype=float), Settings())
    assert np.isnan(hag[1])


@pytest.mark.parametrize("bbox", ["10,63,11,64", "0,7040000,0,7042000", "nan,0,1,2"])
def test_bad_bbox(bbox):
    with pytest.raises(ValueError):
        validate_bbox(bbox)
