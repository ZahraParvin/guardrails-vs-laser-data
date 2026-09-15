"""Download nearest public 2022 road frames for unresolved screening cases."""
import json
from pathlib import Path
import requests
import pandas as pd
import numpy as np
from pyproj import Geod
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'data/followup'

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    cases = pd.read_csv(ROOT / 'reports/trondheim-2022/review.csv')
    initial_ids = ['G01','C02','C03','C04','C05','C07','C08','C10','C11','C16']
    cases = cases[cases.case_id.isin(initial_ids)]
    session = requests.Session()
    response = session.get('https://ogckart-sn1.atlas.vegvesen.no/vegbilder_1_0/ows',params=dict(
        service='WFS',version='2.0.0',request='GetFeature',typenames='vegbilder_1_0:Vegbilder_2022',
        count=10000,srsname='urn:ogc:def:crs:EPSG::4326',outputformat='application/json',
        bbox='63.420,10.367,63.430,10.374,urn:ogc:def:crs:EPSG::4326'),timeout=60)
    response.raise_for_status()
    catalog = response.json()
    features = catalog['features']
    if len(features) >= 10000: raise ValueError('Image catalog may be truncated')
    features = [f for f in features if f['properties']['VEGNUMMER'] == 6650]
    geod = Geod(ellps='GRS80')
    manifest = []
    manifest_path = OUT/'road_manifest.json'
    previous = {r['image']:r['feature_id'] for r in json.loads(manifest_path.read_text())} if manifest_path.exists() else {}
    for case in cases.itertuples():
        panels = []
        for lane in sorted({f['properties']['FELTKODE'] for f in features}):
            choices = []
            for f in features:
                p = f['properties']
                if p['FELTKODE'] != lane: continue
                bearing,_,distance = geod.inv(*f['geometry']['coordinates'],case.longitude,case.latitude)
                forward = distance*np.cos(np.radians(bearing-p['RETNING']))
                if 8 < forward < 45:
                    choices.append((distance,f))
            for rank,(distance,f) in enumerate(sorted(choices,key=lambda a:a[0])[:2]):
                p = f['properties']
                name = f'{case.case_id}_lane{lane}_{rank}.jpg'
                path = OUT/name
                if not path.exists() or previous.get(name) != f['id']:
                    response = session.get(p['URL'],timeout=45)
                    response.raise_for_status()
                    path.write_bytes(response.content)
                # Persist stable source URL without expiring query credentials.
                manifest.append(dict(case_id=case.case_id,image=name,feature_id=f['id'],
                    properties={k:v.split('?')[0] if k in ('URL','URLPREVIEW') else v for k,v in p.items()},
                    coordinates=f['geometry']['coordinates'],distance_m=float(distance)))
                im = Image.open(path).convert('RGB')
                im.thumbnail((1000,560))
                panel=Image.new('RGB',(1000,600),'white');panel.paste(im,(0,30))
                ImageDraw.Draw(panel).text((10,8),f'{name} | {p["TIDSPUNKT"]} | camera distance {distance:.1f} m',fill='black')
                panels.append(panel)
        atlas=Image.new('RGB',(2000,max(1,600*((len(panels)+1)//2))),'white')
        for i,panel in enumerate(panels): atlas.paste(panel,((i%2)*1000,(i//2)*600))
        if panels: atlas.save(OUT/f'{case.case_id}_road.jpg',quality=90)
        print(case.case_id,len(panels),flush=True)
    (OUT/'road_manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')

if __name__ == '__main__': main()
