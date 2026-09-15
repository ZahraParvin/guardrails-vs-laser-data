"""Create a local, dated imagery review pack; these images are not open-data exports."""
import json
from pathlib import Path
import argparse

import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import requests
import shapely

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('output', nargs='?', default=str(ROOT/'outputs/real'))
parser.add_argument('--project', type=int, default=3999)
parser.add_argument('--label', default='2022')
parser.add_argument('--date', default='2022-08-24')
parser.add_argument('--cases', nargs='+', help='Optional case IDs to inspect')
args = parser.parse_args()
OUT = Path(args.output).resolve()
REVIEW = OUT / "review"
SERVICE = "https://services.norgeibilder.no/arcgis/rest/services/ortofoto/ImageServer"


def main():
    REVIEW.mkdir(parents=True, exist_ok=True)
    lines = gpd.read_file(ROOT / "data/trondheim_2022/reference_nvdb/guardrails.gpkg")
    gaps = gpd.read_file(OUT / "flagged_gaps.gpkg")
    candidates = gpd.read_file(OUT / "unregistered_candidates.gpkg")
    cases = [("G01", row.geometry, row.length_m) for row in gaps.itertuples()]
    cases += [(f"C{i+1:02}", row.geometry, row.length_m) for i,row in enumerate(candidates.itertuples())]
    if args.cases:
        cases = [c for c in cases if c[0] in args.cases]
        if not cases: raise ValueError('No matching case IDs')
    session = requests.Session()
    session.headers["Referer"] = "https://hoydedata.no/LaserInnsyn2/"
    token = session.get("https://hoydedata.no/LaserServices/REST/GetToken.ashx", params={"type":"NIB"},timeout=30).json()["token"]
    catalog = []
    for case_id, geom, length in cases:
        bounds = geom.bounds
        cx, cy = geom.centroid.x, geom.centroid.y
        size = max(bounds[2]-bounds[0], bounds[3]-bounds[1], 25) + 20
        extent = [cx-size/2, cy-size/2, cx+size/2, cy+size/2]
        path = REVIEW / f"{case_id}_{args.label}.png"
        meta_path = REVIEW / f"{case_id}_{args.label}.json"
        if not path.exists():
            params = dict(f="json", token=token, geometry=",".join(map(str,extent)),
                          geometryType="esriGeometryEnvelope", inSR=25833,spatialRel="esriSpatialRelIntersects",
                          where=f"nib_project_id = {args.project} AND lowps <= 0.11", returnGeometry="false",
                          outFields="objectid,nib_project_id,prosjektnavn,fotodato,pixelstorrelse_double,eier,lowps,highps,name",returnIdsOnly="false")
            query = session.get(SERVICE+"/query",params=params,timeout=45).json()
            if "error" in query:
                raise ValueError(query["error"])
            records = [f["attributes"] for f in query["features"]]
            ids = [record["objectid"] for record in records]
            if not ids:
                raise ValueError(f"No imagery in project {args.project} for {case_id}")
            rule = dict(mosaicMethod="esriMosaicLockRaster",lockRasterIds=ids,mosaicOperation="MT_FIRST")
            response = session.get(SERVICE+"/exportImage", params=dict(
                f="image", token=token, bbox=",".join(map(str,extent)), bboxSR=25833,
                imageSR=25833,size="1000,1000",format="png",adjustAspectRatio="false",
                mosaicRule=json.dumps(rule)),timeout=60)
            if not response.ok:
                raise RuntimeError(f'Image export failed for {case_id}: HTTP {response.status_code}; retry later')
            if not response.content.startswith(b"\x89PNG"):
                raise ValueError(response.text[:300])
            path.write_bytes(response.content)
            meta_path.write_text(json.dumps(dict(extent=extent,source=SERVICE,
                                records=records,mosaic_rule=rule),indent=2),encoding="utf-8")
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        extent = meta["extent"]
        catalog.append(dict(case_id=case_id,geometry=geom,length_m=float(length),extent=extent,
                            image=path,metadata=meta))
        print(f"Imagery {case_id}",flush=True)
    for offset in range(0,len(catalog),6):
        fig,axes=plt.subplots(2,3,figsize=(15,10),layout="constrained")
        for ax,case in zip(axes.flat,catalog[offset:offset+6]):
            a,b,c,d=case["extent"]
            ax.imshow(plt.imread(case["image"]),extent=[a,c,b,d])
            local=lines[lines.intersects(shapely.box(a,b,c,d))]
            if not local.empty:
                local.plot(ax=ax,color="#00d9ff",linewidth=1)
            geom=case["geometry"]
            if geom.geom_type=="Polygon":
                xs,ys=geom.exterior.xy
            else:
                xs,ys=geom.xy
            ax.plot(xs,ys,color="#ff453a" if case["case_id"].startswith("G") else "#ffee00",lw=2)
            ax.set(xlim=(a,c),ylim=(b,d),title=f"{case['case_id']} | {case['length_m']:.1f} m")
            ax.set_axis_off()
        for ax in list(axes.flat)[len(catalog[offset:offset+6]):]:
            ax.set_axis_off()
        fig.suptitle(f"Local visual review • project {args.project} • {args.date}\n© norgeibilder.no / imagery owner in metadata • Cyan: NVDB • Red: gap • Yellow: candidate",fontsize=12)
        suffix = '' if args.label == '2022' else f'_{args.label}'
        fig.savefig(REVIEW/f"atlas{suffix}_{offset//6+1}.png",dpi=160)
        fig.savefig(REVIEW/f"atlas{suffix}_{offset//6+1}.jpg",dpi=160)
        plt.close(fig)
    (REVIEW/f"catalog{suffix}.json").write_text(json.dumps([{k:v for k,v in c.items() if k not in ["geometry","image"]} for c in catalog],indent=2),encoding="utf-8")


if __name__=="__main__":
    main()
