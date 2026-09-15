"""Write the reproducible report tables and record explicit first-pass review decisions."""
import json
import hashlib
from pathlib import Path
import shutil
import geopandas as gpd
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from pyproj import Transformer

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"outputs/real"
REPORT=ROOT/"reports/trondheim-2022"

# Explicit visual adjudication, recorded after inspecting all dated imagery panels.
# These are screening labels, not independently verified survey ground truth.
DECISIONS={
 "G01":("false_positive","barrier_visible_under_canopy","20 July 2022 road frame shows steel rail with mesh panels at the frontage under the canopy, consistent with NVDB 671258022. The laser gap is rejected as an absence claim. Canopy interception is plausible; exact cause and survey-day condition are not proven."),
 "C01":("false_positive","building_and_garden","Hull crosses building footprints and a garden/terrace strip; incompatible with a single vehicle guardrail."),
 "C02":("false_positive","vegetated_slope","2022 imagery and laser profile show a wooded slope behind the registered roadside barrier. Leaf-off 2024/2026 imagery resolves the candidate strip as vegetation/terrain beside the track. Rejected at screening level, medium confidence; later images are corroboration, not 2022 ground truth."),
 "C03":("uncertain","railway_parking_boundary","2024/2026 leaf-off imagery resolves a linear boundary beside parking on the opposite side of the track. Road frames show the nearer registered rail, not this boundary. Barrier type and 2022 condition require close inspection."),
 "C04":("false_positive","vegetated_slope","Broad tree/undergrowth volume in 2022 laser; leaf-off 2024/2026 imagery exposes terrain between the road and track, separate from the registered roadside barrier. Rejected at screening level, medium confidence; no field verification."),
 "C05":("uncertain","railway_hedge_boundary","Boundary beside the track/access lane persists in later aerial imagery. 2022 returns mix vegetation and a low linear feature; road images do not resolve its type. Inspect from the access-lane side."),
 "C06":("false_positive","traffic_lane","Hull lies inside a traffic lane, not on a fixed roadside boundary. Transient vehicle returns are a plausible explanation, not proven."),
 "C07":("uncertain","changed_forecourt","2022 imagery and laser favour a hedge-like feature in the building forecourt. The forecourt changes in 2024/2026, so its later cleared state cannot establish the 2022 condition. A close 2022 photo or maintenance record is needed."),
 "C08":("false_positive","vegetated_track_margin","Irregular low vegetation and shrub returns beside the track in 2022, corroborated by exposed vegetated ground in leaf-off 2024/2026 imagery. Rejected at screening level, medium confidence; later imagery cannot prove survey-day absence."),
 "C09":("false_positive","building_footprint","Hull overlaps the roof/building footprint rather than a roadside guardrail."),
 "C10":("false_positive","vegetated_track_margin","2022 laser includes irregular undergrowth and tree returns. Leaf-off 2024/2026 imagery locates the hull on the track-side slope, beyond the registered wall/rail at road level. Rejected at screening level, medium confidence."),
 "C11":("uncertain","garden_access_boundary","Low hedge/wall-like feature beside the building access lane persists in spring imagery. Available road frames are over 40 m away and obscured by the road-level wall. Inspect the access-lane boundary and establish its type/history."),
 "C12":("false_positive","building_facade","Hull follows a roof/facade edge within a building footprint, not a roadside guardrail."),
 "C13":("false_positive","traffic_lane","Hull lies in the carriageway. A fixed guardrail is incompatible with the visible lane layout; vehicle explanation remains an inference."),
 "C14":("false_positive","traffic_lane","Hull lies in a traffic lane near a driveway; no fixed barrier is visible in that lane."),
 "C15":("false_positive","traffic_lane","Hull lies in a traffic lane. Likely transient returns; the image and laser were acquired on different dates."),
 "C16":("false_positive","vegetated_track_margin","2022 laser shows irregular vegetation returns; leaf-off 2024/2026 imagery exposes the narrow track margin, separate from the registered roadside barrier. Rejected at screening level, medium confidence; hidden 2022 infrastructure cannot be categorically excluded.")}

FOLLOWUP_IDS={'G01','C02','C03','C04','C05','C07','C08','C10','C11','C16'}

def review_counts(review):
    candidate=review.kind.eq('unregistered_candidate')
    gap=review.kind.eq('unsupported_gap')
    rejected=review.verdict.eq('false_positive')
    uncertain=review.verdict.eq('uncertain')
    return dict(confirmed=int(review.verdict.eq('confirmed').sum()),
                rejected_candidates=int((candidate & rejected).sum()),
                rejected_gaps=int((gap & rejected).sum()),
                uncertain_candidates=int((candidate & uncertain).sum()),
                uncertain_gaps=int((gap & uncertain).sum()))


def main():
    REPORT.mkdir(parents=True,exist_ok=True)
    lines=gpd.read_file(ROOT/"data/trondheim_2022/guardrails.gpkg")
    gaps=gpd.read_file(OUT/"flagged_gaps.gpkg")
    candidates=gpd.read_file(OUT/"unregistered_candidates.gpkg")
    expected=json.loads((REPORT/"review_basis.json").read_text(encoding="utf-8"))
    actual={f"{prefix}{idx+1:02}":hashlib.sha256(row.geometry.wkb).hexdigest()
            for prefix,frame in [("G",gaps),("C",candidates)] for idx,row in frame.iterrows()}
    if actual != expected:
        raise ValueError("Detections changed: review the new locations before reusing the saved visual decisions")
    transform=Transformer.from_crs(25833,4326,always_xy=True)
    rows=[]
    for kind,frame,prefix in [("unsupported_gap",gaps,"G"),("unregistered_candidate",candidates,"C")]:
        for idx,row in frame.iterrows():
            case_id=f"{prefix}{idx+1:02}"
            verdict,reason,notes=DECISIONS[case_id]
            center=row.geometry.centroid
            lon,lat=transform.transform(center.x,center.y)
            rows.append(dict(case_id=case_id,kind=kind,verdict=verdict,reason=reason,
                length_m=float(row.length_m),nvdb_id=row.get("nvdb_id",""),
                road_reference=row.get("road_reference",""),x=center.x,y=center.y,longitude=lon,latitude=lat,
                imagery_project="Trondheim kommune 2022",imagery_project_id=3999,
                imagery_date="2022-08-24 (project metadata)",imagery_resolution_m=.1,
                reviewer="Codex evidence review; not independent ground truth",
                review_stage="followup" if case_id in FOLLOWUP_IDS else "first_pass",
                followup_evidence="FOLLOWUP.md; evidence_manifest.json" if case_id in FOLLOWUP_IDS else "",
                confidence="medium" if case_id in FOLLOWUP_IDS and verdict=='false_positive' else "unrated",
                imagery_source="https://norgeibilder.no/",notes=notes))
    review=pd.DataFrame(rows)
    review.to_csv(REPORT/"review.csv",index=False)
    review.to_csv(OUT/"review.csv",index=False)
    summary=json.loads((OUT/"summary.json").read_text())
    performance=json.loads((OUT/"performance.json").read_text())
    provenance=json.loads((ROOT/"data/trondheim_2022/provenance.json").read_text())
    result=dict(study="FV6650, Trondheim",registered_objects=len(lines),registered_length_m=float(lines.length.sum()),
        laser_project=provenance["project_name"],laser_project_id=5765,laser_flight_dates=["2022-07-29","2022-07-30"],
        nominal_density_points_m2=30,laser_download_points=provenance["kept_points"],analysis_points=summary["crop"]["kept"],
        flags=dict(gaps=len(gaps),gap_length_m=float(gaps.length_m.sum()),candidates=len(candidates)),
        review=dict(**review_counts(review),
                    type="AI-assisted multi-source screening review, not field validation",
                    recall="Not measured: no independently labelled sample of supported/unflagged locations"),
        performance=performance,settings=summary["settings"],
        source_format=provenance["source_type"],source_url=provenance["source"],
        caveat="All linked intersecting viewer nodes downloaded, but original survey export not independently compared; no confirmed NVDB discrepancies.")
    (REPORT/"results.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
    for filename in ["support_per_object.csv","sensitivity.csv","gap_diagnostic.png"]:
        shutil.copyfile(OUT/filename,REPORT/filename)
    # Public figure uses NVDB and laser points only; the aerial review pack stays local.
    cloud=np.load(OUT/"corridor_cloud.npy",mmap_mode="r")
    fig,ax=plt.subplots(figsize=(6,12),layout="constrained")
    stride=max(1,len(cloud)//90000)
    ax.scatter(cloud[::stride,0],cloud[::stride,1],s=.3,c="#bfc6cb",rasterized=True)
    lines.plot(ax=ax,color="#236988",lw=2)
    gaps.plot(ax=ax,color="#dc4035",lw=4)
    candidates.boundary.plot(ax=ax,color="#c98d12",lw=1.3)
    for idx,row in candidates.iterrows():
        if idx+1 not in (1,2,6):
            continue
        p=row.geometry.centroid
        ax.annotate(f"C{idx+1:02}",(p.x,p.y),xytext=(8,0),textcoords="offset points",fontsize=7)
    p=gaps.geometry.iloc[0].centroid
    gap_label={'false_positive':'rejected','uncertain':'uncertain','confirmed':'confirmed'}[DECISIONS['G01'][0]]
    ax.annotate(f"G01: 7 m, {gap_label}",(p.x,p.y),xytext=(-105,0),textcoords="offset points",fontsize=8,color="#b42e25")
    ax.set_aspect("equal")
    ax.ticklabel_format(style="plain",useOffset=False)
    ax.set(xlabel="Easting (m), EPSG:25833",ylabel="Northing (m)",
           title="FV6650 · Trondheim · real laser data\n26 objects / 1,022 m registered guardrail\nNo confirmed NVDB discrepancy")
    ax.legend(handles=[Line2D([0],[0],color=c,lw=2,label=t) for c,t in
              [("#236988","Registered guardrail"),("#dc4035","Unsupported stretch"),("#c98d12","16 screening candidates")]],loc="lower right",fontsize=8)
    fig.supxlabel("Laser © Kartverket · NVDB: Statens vegvesen (NLOD)\nLaser July 2022 / NVDB September 2026",fontsize=8)
    fig.savefig(REPORT/"overview.png",dpi=160)
    plt.close(fig)
    print(json.dumps(result,indent=2))


if __name__=="__main__":
    main()
