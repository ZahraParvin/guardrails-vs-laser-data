"""Plot unchanged 2022 laser returns at the ten initially uncertain locations."""
from pathlib import Path
import json
import geopandas as gpd
import numpy as np
import shapely
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'outputs/real'

def main():
    (ROOT/'data/followup').mkdir(parents=True,exist_ok=True)
    cloud=np.load(OUT/'corridor_cloud.npy',mmap_mode='r')
    hag=np.load(OUT/'height_above_ground.npy',mmap_mode='r')
    gaps=gpd.read_file(OUT/'flagged_gaps.gpkg')
    candidates=gpd.read_file(OUT/'unregistered_candidates.gpkg')
    cases=[('G01',gaps.geometry.iloc[0])]+[(f'C{i:02}',candidates.geometry.iloc[i-1]) for i in [2,3,4,5,7,8,10,11,16]]
    records=[]
    for cid,geom in cases:
        a,b,c,d=geom.buffer(3).bounds
        select=(cloud[:,0]>=a)&(cloud[:,0]<=c)&(cloud[:,1]>=b)&(cloud[:,1]<=d)
        local=np.asarray(cloud[select]);h=np.asarray(hag[select])
        inside=shapely.intersects_xy(geom.buffer(.5) if cid=='G01' else geom,local[:,0],local[:,1])
        center=np.array([geom.centroid.x,geom.centroid.y])
        _,vectors=np.linalg.eigh(np.cov((local[inside,:2]-center).T))
        along=(local[:,:2]-center)@vectors[:,-1]
        across=(local[:,:2]-center)@vectors[:,0]
        fig,axes=plt.subplots(1,3,figsize=(14,4),layout='constrained')
        axes[0].scatter(local[:,0]-center[0],local[:,1]-center[1],s=1,c=h,cmap='viridis',vmin=0,vmax=8)
        outline=geom.exterior if geom.geom_type=='Polygon' else geom
        axes[0].plot(np.asarray(outline.xy[0])-center[0],np.asarray(outline.xy[1])-center[1],color='red')
        axes[0].set_aspect('equal');axes[0].set(xlabel='Local east (m)',ylabel='Local north (m)',title='Plan: colour = estimated height 0–8 m')
        axes[1].scatter(along[inside],h[inside],s=2,color='#236988')
        axes[1].axhspan(.3,1.5,color='orange',alpha=.25)
        axes[1].set(xlabel='Along principal axis (m)',ylabel='Height above nearest ground (m)',title='Returns inside the flagged geometry')
        axes[2].scatter(across,local[:,2],s=1,c=np.where(local[:,3]==2,'#994400','#236988'))
        axes[2].set(xlabel='Across principal axis (m)',ylabel='Elevation NN2000 (m)',title='Bounding-box context; brown = ground')
        fig.suptitle(f'{cid} | July 2022 laser © Kartverket | shape is not a semantic label')
        fig.savefig(ROOT/f'data/followup/{cid}_laser.jpg',dpi=150);plt.close(fig)
        finite=h[inside&np.isfinite(h)]
        records.append(dict(case_id=cid,points_inside=int(inside.sum()),height_quantiles_m=np.quantile(finite,[.1,.5,.9]).tolist(),band_fraction=float(np.mean((finite>=.3)&(finite<=1.5)))))
    (ROOT/'data/followup/laser_profiles.json').write_text(json.dumps(records,indent=2))

if __name__=='__main__': main()
