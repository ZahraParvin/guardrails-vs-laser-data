from unittest.mock import Mock
import geopandas as gpd
import pytest
from guardrails.io import BASE, fetch


def test_pagination_and_metadata(tmp_path, monkeypatch):
    session = Mock()
    monkeypatch.setattr("guardrails.io.requests.Session", lambda: session)
    obj = dict(id=1, geometri=dict(wkt="LINESTRING Z (270000 7040000 3,270010 7040000 4)", srid=5973),
               lokasjon=dict(vegsystemreferanser=[dict(kortform="FV1 S1D1 m0-10")]))
    next_url = BASE + "/vegobjekter/5?start=next"
    first = Mock(url=BASE + "/vegobjekter/5")
    first.json.return_value = dict(objekter=[obj], metadata=dict(neste=dict(href=next_url)))
    last = Mock(url=next_url)
    last.json.return_value = dict(objekter=[])
    session.get.side_effect = [first, last]
    result = fetch("269000,7040000,271000,7042000", tmp_path)
    assert result.road_reference.iloc[0] == "FV1 S1D1 m0-10"
    assert not result.geometry.iloc[0].has_z
    assert session.get.call_args_list[1].kwargs["params"] is None
    assert session.get.call_args_list[0].kwargs["params"]["srid"] == "UTM_33"
    assert (tmp_path / "fetch_metadata.json").exists()


def test_missing_next_link_is_valid_terminal_page(tmp_path, monkeypatch):
    session = Mock()
    monkeypatch.setattr("guardrails.io.requests.Session", lambda: session)
    session.get.return_value.json.return_value = dict(objekter=[dict(id=7, geometri=dict(wkt="LINESTRING (270000 7040000,270010 7040000)"))])
    assert len(fetch("269000,7040000,271000,7042000", tmp_path)) == 1
    assert session.get.call_count == 1
