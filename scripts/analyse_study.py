"""Reproducible sensitivity analysis and LiDAR diagnostic figures for the real case."""
from dataclasses import replace
import json
from pathlib import Path
import threading
import time

import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import psutil
from scipy.spatial import cKDTree
import shapely

from guardrails.analysis import Settings, ground_height, sample_support, gaps_from_samples

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/real"


def main():
    process = psutil.Process()
    peak = [process.memory_info().rss]
    stop = threading.Event()
    def monitor():
        while not stop.wait(.1):
            peak[0] = max(peak[0],process.memory_info().rss)
    worker=threading.Thread(target=monitor,daemon=True)
    worker.start()
    started=time.perf_counter()
    lines=gpd.read_file(ROOT/"data/trondheim_2022/guardrails.gpkg")
    cloud=np.load(OUT/"corridor_cloud.npy",mmap_mode="r")
    cfg=Settings()
    hag,method=ground_height(cloud,cfg)
    np.save(OUT/"height_above_ground.npy",hag)
    baseline,parts,band=sample_support(lines,cloud,hag,cfg)
    baseline_seconds=time.perf_counter()-started
    rows=[]
    for radius in [1.,1.5,2.]:
        samples,parts,_=sample_support(lines,cloud,hag,replace(cfg,radius=radius))
        for minimum in [5,10,20]:
            current=samples.copy()
            current["supported"]=current.n_pts>=minimum
            current["status"]=np.where(~current.observed,"unknown",np.where(current.supported,"supported","unsupported"))
            gaps=gaps_from_samples(current,parts,cfg)
            rows.append(dict(radius_m=radius,min_points=minimum,flagged_count=len(gaps),
                             flagged_length_m=float(gaps.length_m.sum()),
                             unsupported_m=float((current.to_m-current.from_m)[current.status=="unsupported"].sum())))
    pd.DataFrame(rows).to_csv(OUT/"sensitivity.csv",index=False)
    total_counts=cKDTree(cloud[:,:2]).query_ball_point(baseline[["x","y"]].to_numpy(),cfg.radius,return_length=True)
    diagnostics=dict(points=len(cloud),ground_method=method,band_points=int(band.sum()),
        unknown_height_points=int((~np.isfinite(hag)).sum()),
        sample_band_counts_quantiles=np.quantile(baseline.n_pts,[0,.1,.5,.9,1]).tolist(),
        sample_all_counts_quantiles=np.quantile(total_counts,[0,.1,.5,.9,1]).tolist(),
        baseline_ground_and_sampling_seconds=baseline_seconds,
        sensitivity_seconds=time.perf_counter()-started,
        peak_process_rss_mb=peak[0]/1024**2,
        timing_scope="cached cropped cloud: ground estimate, sampling and nine sensitivity combinations; excludes original download/crop/DBSCAN",
        memory_measurement="process RSS sampled every 100 ms; includes Python and dependencies")
    stop.set()
    worker.join()
    (OUT/"diagnostics.json").write_text(json.dumps(diagnostics,indent=2),encoding="utf-8")
    gap=gpd.read_file(OUT/"flagged_gaps.gpkg").iloc[0]
    geometry=lines.iloc[int(gap.row_id)].geometry
    mask=shapely.distance(shapely.points(cloud[:,:2]),geometry)<5
    local=cloud[mask]
    local_hag=hag[mask]
    distances=shapely.line_locate_point(geometry,shapely.points(local[:,:2]))
    lateral=shapely.distance(shapely.points(local[:,:2]),geometry)
    fig,axes=plt.subplots(1,2,figsize=(12,5),layout="constrained",gridspec_kw={"width_ratios":[2,1]})
    chosen=np.isfinite(local_hag)&(local_hag>-1)&(local_hag<5)
    axes[0].scatter(distances[chosen],local_hag[chosen],s=2,c=lateral[chosen],cmap="viridis",vmin=0,vmax=5)
    axes[0].axhspan(.3,1.5,alpha=.15,color="orange")
    axes[0].axvspan(gap.from_m,gap.to_m,alpha=.12,color="red")
    axes[0].set(xlabel="Distance along NVDB part (m)",ylabel="Height above nearest ground (m)",title="G01: heights within 5 m of line")
    narrow=lateral<=cfg.radius
    x0,y0=geometry.centroid.x,geometry.centroid.y
    axes[1].scatter(local[narrow,0]-x0,local[narrow,1]-y0,c=local_hag[narrow],s=4,cmap="viridis",vmin=0,vmax=2)
    axes[1].plot(np.asarray(geometry.xy[0])-x0,np.asarray(geometry.xy[1])-y0,color="black",lw=1,label="NVDB")
    axes[1].plot(np.asarray(gap.geometry.xy[0])-x0,np.asarray(gap.geometry.xy[1])-y0,color="red",lw=3,label="Flagged 7 m")
    axes[1].set_aspect("equal")
    axes[1].legend(loc="upper left",bbox_to_anchor=(1.01,1))
    axes[1].set(title="Local points within 1.5 m",xlabel="Local east (m)",ylabel="Local north (m)")
    axes[1].ticklabel_format(style="plain",useOffset=False)
    fig.suptitle("G01 | FV6650 S2D1 m842–856 | laser 29–30 July 2022\nLaser © Kartverket; NVDB © Statens vegvesen (NLOD)",fontsize=11)
    fig.savefig(OUT/"gap_diagnostic.png",dpi=160)
    plt.close(fig)
    print(json.dumps(diagnostics,indent=2))
    print(pd.DataFrame(rows).to_string(index=False))


if __name__=="__main__":
    main()
