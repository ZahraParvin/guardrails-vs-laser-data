"""Package review provenance and a small licensed evidence sample for the report."""
import hashlib
import json
from pathlib import Path
import shutil
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
REPORT=ROOT/'reports/trondheim-2022'

def main():
    destination=REPORT/'evidence'
    destination.mkdir(exist_ok=True)
    road=json.loads((ROOT/'data/followup/road_manifest.json').read_text())
    profiles=json.loads((ROOT/'data/followup/laser_profiles.json').read_text())
    cases=[]
    basis=json.loads((REPORT/'review_basis.json').read_text())
    for profile in profiles:
        cid=profile['case_id']
        imagery=[]
        for label,date in [('2022','2022-08-24'),('2024_native','2024-05-05'),('2026_native','2026-04-17')]:
            stem=ROOT/f'outputs/real/review/{cid}_{label}'
            meta=json.loads(stem.with_suffix('.json').read_text())
            imagery.append(dict(local_image=str(stem.with_suffix('.png').relative_to(ROOT)),
                sha256=hashlib.sha256(stem.with_suffix('.png').read_bytes()).hexdigest(),
                project_date=date,date_precision='project metadata',**meta))
        laser=ROOT/f'data/followup/{cid}_laser.jpg'
        shutil.copyfile(laser,destination/laser.name)
        frames=[dict(**r,sha256=hashlib.sha256((ROOT/'data/followup'/r['image']).read_bytes()).hexdigest()) for r in road if r['case_id']==cid]
        cases.append(dict(case_id=cid,geometry_sha256=basis[cid],aerial=imagery,
            road_frames=frames,laser_profile=profile,laser_figure=f'evidence/{laser.name}',
            laser_figure_sha256=hashlib.sha256(laser.read_bytes()).hexdigest()))
    source=ROOT/'data/followup/G01_lane2_0.jpg'
    shutil.copyfile(source,destination/'G01_road_2022.jpg')
    result=dict(review_date='2026-09-15',reviewer='Codex; not independent field validation',
        road_license='NLOD; Statens vegvesen; https://dataut.vegvesen.no/nb/dataset/vegbilder',
        road_catalog='https://ogckart-sn1.atlas.vegvesen.no/vegbilder_1_0/ows',
        published_road_frame=dict(path='evidence/G01_road_2022.jpg',
            source_record=next(r for r in road if r['image']==source.name),
            sha256=hashlib.sha256(source.read_bytes()).hexdigest()),
        aerial_notice='Local inspection only; aerial image pixels are not bundled in this report.',cases=cases)
    (REPORT/'evidence_manifest.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    review=pd.read_csv(REPORT/'review.csv')
    todo=review[review.verdict=='uncertain'][['case_id','longitude','latitude','length_m','notes']].copy()
    todo['required_evidence']='Close view identifying boundary type, plus dated evidence of its 2022 condition'
    todo.to_csv(REPORT/'field_checks.csv',index=False)
    print(f'Packaged {len(cases)} follow-up cases; {len(todo)} remain uncertain.')

if __name__=='__main__': main()
