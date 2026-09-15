import struct
import geopandas as gpd
import numpy as np
from shapely.geometry import LineString
from guardrails.analysis import Settings, find_candidates
from scripts.download_study import node_path, decode_hierarchy, child_bounds


def test_hierarchy_path_and_axis_order():
    assert node_path("r0123456") == "data/r/01234/r0123456"
    assert node_path("r0123") == "data/r/r0123"
    np.testing.assert_array_equal(child_bounds([0,0,0,8,8,8],5),[4,0,4,8,4,8])


def test_hierarchy_breadth_first_and_boundary_frontier():
    # Root -> children 0, 4; child 0 has an external hierarchy continuation.
    blob=struct.pack("<BI",17,10)+struct.pack("<BI",1,20)+struct.pack("<BI",0,30)
    nodes=decode_hierarchy(blob,"r",np.array([0,0,0,8,8,8]))
    assert set(nodes)=={"r","r0","r4"}
    assert nodes["r0"]["mask"]==1
    assert nodes["r4"]["bounds"]==[4,0,0,8,4,4]


def test_neighboring_registered_road_excludes_candidate():
    x=np.linspace(0,20,500)
    cloud=np.column_stack([x,np.full(500,10.),np.ones(500),np.ones(500)])
    study=gpd.GeoDataFrame(geometry=[LineString([(0,0),(20,0)])],crs=25833)
    all_roads=gpd.GeoDataFrame(geometry=[study.geometry.iloc[0],LineString([(0,10),(20,10)])],crs=25833)
    assert len(find_candidates(study,cloud,np.ones(500,dtype=bool),Settings()))==1
    assert find_candidates(all_roads,cloud,np.ones(500,dtype=bool),Settings()).empty
