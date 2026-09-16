# Guardrails vs Laser Data

**A weekend project on Norwegian open data.**

Where does NVDB say there is a guardrail, while the laser data disagrees?
Four steps, from an empty folder to a figure and a number you can send to someone.

Built on two open sources: the National Road Database (NVDB) at Statens vegvesen,
and Kartverket's national detailed elevation model. Everything below is written for
one stretch of road a couple of kilometres long — not for the whole road network,
and that is the point.

| | |
|---|---|
| Road object type | 5 — Guardrail (NVDB: Rekkverk) |
| Coordinate system | EPSG:25833 |
| Point format | LAZ 1.2–1.4 |
| Time budget | ≈ 14 hours |

**Progress**

- [ ] 0 — Pick the stretch, lock the CRS
- [ ] 1 — Guardrails out of NVDB
- [ ] 2 — Download the laser tile
- [ ] 3 — Chunked read, crop corridor
- [ ] 4 — Find the disagreements
- [ ] 5 — Calibrate against imagery
- [ ] 6 — README and licences

---

## Step 0 — Pick the stretch, and lock the coordinate system

*30 min*

Everything that goes wrong later goes wrong because two datasets are in different
coordinate systems. Decide now and hold to it.

### Find a stretch worth looking at

Open **vegkart.no**, which is Statens vegvesen's own map view of NVDB. Search for an
area, pick the *Guardrail* object type (labelled *Rekkverk*) in the left menu, and see where guardrail is
actually dense.

- **Choose a fjord or mountain road, not a city street.** You want several hundred
  metres of continuous guardrail, not fifty metres beside a bus stop.
- **Check that laser data exists over the place** before you commit to it — see step 2.
  Coverage is good but not complete, and projects differ in age and point density.
- **Keep the area around 2 × 2 km.** Big enough that the file isn't a toy, small enough
  that a full run through the pipeline takes minutes rather than hours.

### Write down one bbox, in EPSG:25833

Norway uses three UTM zones — 32N in the south and west, 33N through the centre and
north, 35N in Finnmark — but **EPSG:25833 (ETRS89 / UTM zone 33N) is the national
standard**, and it is what NVDB works in. Choose 25833 in both places and you never
have to reproject at all.

You need four numbers: `minx, miny, maxx, maxy` in metres. Get them from vegkart, from
norgeskart.no, or by drawing a rectangle in QGIS with the project CRS set to EPSG:25833
and reading off the extent.

> **⚠ Common failure**
> If your bbox numbers look like `10.4, 63.4` they are degrees (WGS84), not metres.
> UTM33 coordinates in Norway have six digits easting (roughly 200,000–700,000) and
> seven northing (roughly 6,400,000–7,900,000). If NVDB returns zero objects, this is
> the cause nine times out of ten.

### Set up the folder

One line at a time:

```
mkdir guardrail-nvdb && cd guardrail-nvdb
```
```
python -m venv .venv
```
```
source .venv/bin/activate
```
```
pip install requests shapely geopandas "laspy[lazrs]" scipy scikit-learn pandas matplotlib
```

> **Why not PDAL**
> PDAL is the industry standard, but `pip install pdal` only gives you the Python
> bindings — the C++ library itself wants conda. `laspy` with the `lazrs` backend reads
> LAZ with nothing outside pip, and covers everything you need here. Mention PDAL in the
> README as what you'd reach for in production; don't let the install eat an evening.

---

## Step 1 — Guardrails out of NVDB

*2–3 hours*

### What you are actually fetching

The National Road Database (Nasjonal vegdatabank) is the register of everything standing
along and in the road. Each element is a *vegobjekt* with a *vegobjekttype*. Guardrail is
**type 5**, described in the data catalogue as "a device intended to prevent vehicles
leaving the road", and it is located as a **LINE** — a curve running along the road, not
a point.

That is exactly why the comparison is possible: you get a line with a length, and you can
ask, for every metre of it, whether the laser data sees anything there.

### The key terms

| Term | What it means |
|---|---|
| `vegobjekttype` | The category. 5 = guardrail. The full catalogue is at `/vegobjekttyper`. |
| `kartutsnitt` | Spatial filter, `minx,miny,maxx,maxy` in whichever srid you declare. |
| `srid` | Coordinate system of the geometry you get back. Set it explicitly to 25833 — don't rely on the default, it has differed between API versions. |
| `inkluder` | What the response should contain. `geometri` gives WKT, `egenskaper` gives the field values, `lokasjon` gives the road system reference. |
| `segmentering` | Splits an object where the road system reference changes. Gives shorter, more uniform lines — convenient here. |
| `X-Client` | Header where you identify your client. Vegvesen asks for it. Costs nothing and is good manners. |

### Confirm you can reach it before writing anything

One call, in the browser or with curl. If you get JSON back containing
`"navn": "Rekkverk"`, everything works:

```
curl -H "X-Client: zahra-test" https://nvdbapiles-v3.atlas.vegvesen.no/vegobjekttyper/5
```

If you get nothing, check the current base URL in the V4 documentation
(https://nvdb-docs.atlas.vegvesen.no/nvdbapil/v4/introduksjon/Oversikt/) — the parameters
have the same shape, only the host may have moved.

### The fetch script

The API parameters stay in Norwegian because that is literally what the API is called;
the variable names are English, which is how a Norwegian repo normally reads.

```python
# fetch_guardrails.py
import requests, geopandas as gpd
from shapely import wkt

BASE = "https://nvdbapiles-v3.atlas.vegvesen.no"
HEAD = {"Accept": "application/json", "X-Client": "zahra-guardrail-demo"}
BBOX = "269000,7040000,271000,7042000"   # minx,miny,maxx,maxy in EPSG:25833

def fetch_guardrails(bbox):
    url = f"{BASE}/vegobjekter/5"               # 5 = Guardrail
    params = {
        "kartutsnitt":  bbox,
        "srid":         25833,
        "inkluder":     "lokasjon,geometri,egenskaper",
        "antall":       1000,
        "segmentering": "true",
    }
    out = []
    while url:
        r = requests.get(url, headers=HEAD, params=params, timeout=60)
        r.raise_for_status()
        d = r.json()
        if not d["objekter"]:                   # empty page = we're done
            break
        out += d["objekter"]
        url    = d["metadata"]["neste"]["href"] # href already carries the params
        params = None                            # so don't send them twice
        print(f"  {len(out)} objects ...")
    return out

objs = fetch_guardrails(BBOX)

gdf = gpd.GeoDataFrame(
    {"nvdb_id": [o["id"] for o in objs]},
    geometry=[wkt.loads(o["geometri"]["wkt"]) for o in objs],
    crs="EPSG:25833",
)
gdf.to_file("guardrails.gpkg", driver="GPKG")

print(f"\n{len(gdf)} guardrail objects")
print(f"{gdf.length.sum():,.0f} m total length")
print(f"extent: {[round(v) for v in gdf.total_bounds]}")
```

#### The pagination, since it's the one trap

NVDB gives you at most `antall` objects per response plus a link onward in
`metadata.neste.href`. That link already contains all your parameters plus a position
token. This is why `params = None` after the first round — send the parameters again
*on top of* the href and you get either a 400 or the same page over and over. The loop
ends when a page comes back empty, not when the href is missing.

### Look at what you got, before moving on

Print one object raw and read through it:

```python
import json
print(json.dumps(objs[0], indent=2, ensure_ascii=False)[:2500])
```

Note three things. `geometri.wkt` is often **3D** — `LINESTRING Z (...)` — so the lines
already carry a height from the register, useful as a cross-check later. `egenskaper` is
a list of `{id, navn, verdi}`; scroll through and see which ones exist for guardrail in
your area, and carry the interesting ones as columns. And `lokasjon.vegsystemreferanser`
is road number plus metre value — that is *the* key iSi and Statens vegvesen actually
talk to each other in, not coordinates.

> **✓ Worth carrying through**
> Put the road system reference into the GeoPackage now. When you finally report "these
> 40 metres look wrong", *Fv6652 S1D1 m1240–1280* is an answer a road authority can act
> on. A pair of UTM coordinates is not.

### Checks before you continue

- Is the object count close to what vegkart showed for the same area?
- Does `gdf.total_bounds` sit inside your bbox?
- Does `gdf.plot()` look like a road?

If any answer is no, it's the coordinate system. It always is.

---

## Step 2 — Download the laser tile

*1 hour, mostly waiting*

### What the data is

Kartverket's national detailed elevation model is airborne laser scanning of the whole
country, collected project by project over several years. Each project has its own year
and point density — a label like *"Trondheim 10pkt 2023"* means 10 points per square
metre, flown in 2023.

Density matters a lot here. A guardrail is a thin, vertical thing. At 2 pts/m² you get a
handful of returns per metre of barrier; at 10 pts/m² you get enough that it has a shape.
**Pick the densest project covering your stretch**, even if it is older.

### Through the portal

1. Go to **hoydedata.no/LaserInnsyn2**.
2. Use *Search* (labelled *Søk*) to find a place name, address or coordinates.
3. See which projects cover the area, and note name, year and density. You want them in
   the README.
4. Open the export menu. Choose **Point cloud** (labelled *Punktsky*) — not DTM or DOM,
   which are already rasterised and have thrown away exactly the points you're after.
5. Draw the area, or use *Current map view* (labelled *Gjeldende kartutsnitt*). Cover the bbox from
   step 0, ideally a little generously.
6. Choose coordinate system **UTM33**, so it matches the NVDB extract.
7. Select *Prepare export* (labelled *Klargjør eksport*), and wait.

> **Setting expectations**
> Expect a few hundred megabytes and tens of millions of points for 2 × 2 km at high
> density. That's intentional. It's the first dataset you've worked with that doesn't
> comfortably fit in memory, and that is half the point of the project.

### Inspect the file before trusting it

```python
# inspect.py
import laspy, numpy as np

with laspy.open("tile.laz") as f:
    h = f.header
    print(f"LAS version   {h.version}")
    print(f"points        {h.point_count:,}")
    print(f"extent        x {h.mins[0]:.0f}–{h.maxs[0]:.0f}")
    print(f"              y {h.mins[1]:.0f}–{h.maxs[1]:.0f}")
    print(f"              z {h.mins[2]:.1f}–{h.maxs[2]:.1f}")
    print(f"crs           {h.parse_crs()}")

    las = f.read()
    cls, cnt = np.unique(las.classification, return_counts=True)
    print("\nclasses:")
    for c, n in zip(cls, cnt):
        print(f"  {c:>2}  {n:>12,}  ({100*n/len(las.classification):.1f}%)")
```

Three things to read out of this. The **extent** must overlap your bbox — if it doesn't,
one of the datasets is in the wrong zone. The **point count** tells you how careful step 3
has to be with memory. And the **class list** is the important one.

> **✓ This saves you a lot of work**
> Kartverket's laser data is normally classified to the ASPRS standard, where
> **class 2 is ground**. If your tile has class 2, you have a ground surface for free and
> don't have to estimate one. That makes step 4 both simpler and more accurate. Look for
> class 2 in the output above — if it's there, use it.

If the tile is unclassified it isn't a disaster. Step 4 has a fallback method, and the
difference between the two is something you can write about in the README.

---

## Step 3 — Chunked read, crop to the corridor

*2 hours*

### Why chunked

You could write `las = laspy.read("tile.laz")` and get the whole cloud as one array. On
this tile it might be fine. On the next one it isn't, and on a nationwide dataset it isn't
even a question.

`chunk_iterator` hands you a fixed number of points at a time, however large the file is.
Memory use becomes constant instead of proportional to file size. **Write it this way even
though you don't need to here** — it is the pattern that separates someone who has handled
real point clouds from someone who hasn't, and it is one of the things the review flagged
as missing from your CV.

### Two filters, in the right order

For each chunk you run two tests. First a **bounding-box test**: is the point even inside
the corridor's bounding rectangle? That's pure arithmetic on numpy arrays and costs almost
nothing. Only the survivors go on to the **real polygon test**, which is far more
expensive.

On a typical tile the bbox test discards 95% of the points. Reversing the order makes the
script twenty times slower, and it's the kind of detail a technical lead notices.

```python
# crop_corridor.py
import laspy, numpy as np, shapely, geopandas as gpd

BUFFER = 3.0          # m either side of the guardrail line
CHUNK  = 2_000_000    # points per chunk

gdf      = gpd.read_file("guardrails.gpkg")
corridor = gdf.geometry.buffer(BUFFER).union_all()
minx, miny, maxx, maxy = corridor.bounds

kept, seen = [], 0
with laspy.open("tile.laz") as f:
    total = f.header.point_count
    print(f"{total:,} points in file")

    for pts in f.chunk_iterator(CHUNK):
        x = np.asarray(pts.x); y = np.asarray(pts.y); z = np.asarray(pts.z)
        cl = np.asarray(pts.classification)
        seen += len(x)

        # 1) cheap bounding-box test
        m = (x >= minx) & (x <= maxx) & (y >= miny) & (y <= maxy)
        if not m.any():
            continue
        x, y, z, cl = x[m], y[m], z[m], cl[m]

        # 2) expensive, but now on a small subset — vectorised, not a loop
        inside = shapely.contains_xy(corridor, x, y)
        if inside.any():
            kept.append(np.column_stack([x[inside], y[inside],
                                         z[inside], cl[inside]]))

        print(f"  {seen:>12,} / {total:,}", end="\r")

cloud = np.vstack(kept)
np.save("corridor_cloud.npy", cloud)
print(f"\n{len(cloud):,} points kept ({100*len(cloud)/total:.2f}% of the file)")
```

> **The details that matter**
> `shapely.contains_xy` is vectorised and takes whole arrays. The naive version —
> `corridor.contains(Point(x, y))` in a loop — gives the same answer and takes hundreds of
> times longer. We carry `classification` as a fourth column because step 4 needs it for
> the ground surface. And we save to `.npy` so you never read the LAZ file more than once.

### Checks

- Did you keep somewhere between 0.5% and 5% of the points? Much less: the buffer is too
  narrow or the lines are misplaced. Much more: the corridor covers half the tile, check
  the buffer.
- Plot `cloud[::50, 0]` against `cloud[::50, 1]`. It should look like a ribbon along a
  road, not like a blob or a rectangle.

---

## Step 4 — Find the disagreements

*6–8 hours*

This is where the work is, and where the thing worth showing lives. The three previous
steps are plumbing; this is the actual question.

### The idea, in one picture

A guardrail is a horizontal beam at a particular height above the ground. The road surface
sits below it, vegetation and signs above. If you can compute **height above ground** for
every point, you can slice out exactly the band a barrier lives in — and then the question
is simply whether there are points in that band where the register says a barrier should be.

```
                                                  o  o     <- vegetation, above the band
        o   o
   - - - - - - - - - - - - - - - - - - - - - - - - - -   1.5 m above ground
                 ·  ·  ·  ·  ·  ·  ·  ·  ·  ·
              ===========================  <- guardrail beam, points cluster here
                 |     |     |     |
   - - - - - - - - - - - - - - - - - - - - - - - - - -   0.3 m above ground
   ____________________________________________________
   .   .   .   .   .   .   .   .   .   .   .   .   .      <- ground points (class 2)
                                            \___ terrain slopes downhill
```

The terrain slopes. That is the entire reason the band has to be measured from the ground
and not from sea level — a fixed absolute height interval would hit the barrier at one end
of the stretch and the road surface at the other.

### 4a — Ground level

Two methods, depending on what step 2 showed.

**If you have class 2:** build a KD-tree of the ground points and look up the nearest
ground point for every other point. Accurate, and it follows the terrain exactly.

**If you don't:** divide the corridor into 2 × 2 m cells and set the ground level in each
cell to the 5th percentile of z. Percentile rather than minimum, because points below
ground do occur — reflections, measurement noise — and a minimum would let a single such
point ruin the whole cell.

```python
# ground.py
import numpy as np, pandas as pd
from scipy.spatial import cKDTree

CELL = 2.0

def height_above_ground(x, y, z, cl=None):
    """Return height above the local ground surface for every point."""
    if cl is not None and (cl == 2).sum() > 500:
        # ASPRS class 2 = ground. Nearest ground point in plan view.
        ground = np.column_stack([x[cl == 2], y[cl == 2]])
        z_grd  = z[cl == 2]
        tree   = cKDTree(ground)
        _, i   = tree.query(np.column_stack([x, y]), workers=-1)
        print(f"  ground from {len(z_grd):,} class-2 points")
        return z - z_grd[i]

    # fallback: 5th percentile per cell
    df = pd.DataFrame({
        "ix": np.floor((x - x.min()) / CELL).astype(np.int32),
        "iy": np.floor((y - y.min()) / CELL).astype(np.int32),
        "z":  z,
    })
    g = (df.groupby(["ix", "iy"], as_index=False)["z"]
           .quantile(0.05).rename(columns={"z": "ground"}))
    df = df.merge(g, on=["ix", "iy"], how="left")
    print(f"  ground estimated over {len(g):,} cells")
    return df["z"].values - df["ground"].values
```

> **⚠ The trap here**
> Don't use `groupby().transform(lambda s: s.quantile(...))`. It looks tidier and is a
> hundred times slower on millions of rows, because the lambda runs once per group in
> Python. `groupby().quantile()` followed by a `merge` stays vectorised the whole way.

### 4b — Sample points along the line

Cut every guardrail line into points one metre apart. For each sample point you ask: how
many laser points at guardrail height lie within 1.5 m horizontally? Below the threshold,
that metre is *unsupported*.

One thing to watch: NVDB geometry can be a `MultiLineString`, several separate curves in
one object. Handle both cases or the script crashes on the twentieth object.

```python
# sampling.py
import numpy as np, pandas as pd
from scipy.spatial import cKDTree

BAND_LO, BAND_HI = 0.30, 1.50   # m above ground
SEARCH_R         = 1.50         # m horizontal search radius
MIN_PTS          = 5            # points before a metre counts as supported
STEP             = 1.0          # m between sample points

def points_along(geom, step=STEP):
    parts   = geom.geoms if geom.geom_type == "MultiLineString" else [geom]
    running = 0.0
    for part in parts:
        n = max(int(part.length // step), 1)
        for d in np.linspace(0, part.length, n + 1):
            p = part.interpolate(d)
            yield p.x, p.y, running + d
        running += part.length

def coverage(gdf, x, y, hag):
    band = (hag > BAND_LO) & (hag < BAND_HI)
    tree = cKDTree(np.column_stack([x[band], y[band]]))
    print(f"  {band.sum():,} points at guardrail height")

    rows = [(r.nvdb_id, px, py, m)
            for _, r in gdf.iterrows()
            for px, py, m in points_along(r.geometry)]
    sp = pd.DataFrame(rows, columns=["nvdb_id", "x", "y", "m"])

    sp["n_pts"]     = tree.query_ball_point(
        sp[["x", "y"]].values, r=SEARCH_R, return_length=True, workers=-1)
    sp["supported"] = sp["n_pts"] >= MIN_PTS
    return sp
```

`return_length=True` is worth noting: it counts the neighbours without building the index
lists, saving both time and memory once you have hundreds of thousands of sample points.
`workers=-1` uses every core.

### 4c — From single metres to stretches

One unsupported sample means nothing — it could be a shadow under a tree. Twenty in a row
means something. Merge consecutive unsupported samples into stretches and discard anything
shorter than five metres.

```python
# gaps.py
from shapely.geometry import LineString
import geopandas as gpd

MIN_GAP = 5.0   # m

def find_gaps(group):
    out, start = [], None
    for _, r in group.iterrows():
        if not r.supported and start is None:
            start = r
        elif r.supported and start is not None:
            if r.m - start.m >= MIN_GAP:
                out.append((start, r))
            start = None
    if start is not None:                       # gap running off the end
        last = group.iloc[-1]
        if last.m - start.m >= MIN_GAP:
            out.append((start, last))
    return out

geoms, meta = [], []
for nvdb_id, g in sp.groupby("nvdb_id"):
    g = g.sort_values("m")
    for a, b in find_gaps(g):
        geoms.append(LineString([(a.x, a.y), (b.x, b.y)]))
        meta.append({"nvdb_id": nvdb_id, "from_m": round(a.m, 1),
                     "to_m": round(b.m, 1), "length_m": round(b.m - a.m, 1)})

gaps = gpd.GeoDataFrame(meta, geometry=geoms, crs=gdf.crs)
gaps = gaps.sort_values("length_m", ascending=False)
gaps.to_file("flagged_gaps.gpkg", driver="GPKG")
```

### 4d — The other direction

The more interesting half: points at guardrail height lying *far from* any registered
line. Those are candidates for barriers standing there without being in the register.

The problem is that noise barriers, wildlife fences, hedges and parked cars all live in
that height band too. One filter helps a lot: **shape**. A guardrail is long and thin. A
bush is round. Keep clusters longer than eight metres and at least four times as long as
they are wide.

```python
# unregistered.py
import numpy as np, shapely, geopandas as gpd
from scipy.spatial import cKDTree
from sklearn.cluster import DBSCAN

MIN_DIST = 5.0    # m from the nearest NVDB line

tree_nvdb = cKDTree(sp[["x", "y"]].values)
xy_band   = np.column_stack([x[band], y[band]])
dist, _   = tree_nvdb.query(xy_band, workers=-1)
far       = xy_band[dist > MIN_DIST]

candidates = []
if len(far) > 50:
    labels = DBSCAN(eps=1.5, min_samples=40).fit_predict(far)
    for k in set(labels) - {-1}:
        p        = far[labels == k]
        spread   = p.max(0) - p.min(0)
        elongate = max(spread) / max(min(spread), 0.5)
        if max(spread) > 8.0 and elongate > 4.0:       # long and thin
            candidates.append({
                "geometry":   shapely.MultiPoint(p).convex_hull,
                "n_pts":      len(p),
                "length_m":   round(max(spread), 1),
                "elongation": round(elongate, 1),
            })

if candidates:
    gpd.GeoDataFrame(candidates, crs=gdf.crs).to_file(
        "unregistered_candidates.gpkg", driver="GPKG")
```

### 4e — Calibrate against something you can see

This is the step that separates the project from a script someone ran once. The four
parameters `BAND_LO`, `BAND_HI`, `MIN_PTS` and the shape filter decide the whole result,
and they cannot be chosen theoretically.

1. Open `flagged_gaps.gpkg` in QGIS alongside the guardrail lines.
2. Add aerial imagery underneath — norgeibilder.no, or Kartverket's WMS straight into QGIS.
3. Walk through the twenty longest flagged stretches one by one and write down what you
   actually see: is there a barrier? Has it been removed? Is it a driveway breaking the
   run, meaning the register is right and the line just isn't split?
4. Adjust the parameters, re-run, count again.

> **✓ This is the actual result**
> The number you report at the end is not "X% coverage". It is **"of the twenty longest
> flagged stretches, N were real discrepancies and M were false positives, and here is
> what set the false ones off"**. That sentence is the difference between someone who ran
> a script and someone who built a detector, and it is what a technical interview will be
> about.

### What comes out

| File | Contents |
|---|---|
| `flagged_gaps.gpkg` | Stretches where NVDB has guardrail and the laser data sees nothing, sorted by length. |
| `unregistered_candidates.gpkg` | Elongated clusters at guardrail height, far from any registered line. |
| `support_per_object.csv` | Coverage per NVDB object, with road system reference. |
| `overview.png` | One map: lines, points, flags, candidates. |

---

## When you write the README

Norwegian, short, no marketing voice — the repo is aimed at a Norwegian reader even though
this guide isn't.

The part a technical lead reads most closely is not the result but the paragraph on **what
would change at national scale**: that tiling should be driven by the road network rather
than a grid, since the overwhelming majority of tiles contain no road at all; that linear
road referencing is the key rather than coordinates; and where the ground estimate would be
replaced by a ready-made terrain model. That is where you show you understand the distance
between your 2 × 2 km and a whole road network, without having had to build it.

Check the licence terms at both Kartverket and Statens vegvesen before publishing, and
attribute them exactly as they ask. For a company whose customer is Statens vegvesen,
getting that right is itself a signal.

The repo link belongs in the follow-up email, not in the CV. The CV says you have LiDAR
from coursework. The repo shows you can do it on their data.

### README skeleton

```markdown
# Guardrails: NVDB vs laser data

How well do guardrails registered in the National Road Database match
what the laser data actually shows?

## The question
[2-3 sentences.]

## Data
- Guardrails from the NVDB API, road object type 5 — [licence + attribution]
- Point cloud from Kartverket's national detailed elevation model,
  [project name, year, point density] — [licence + attribution]
- Road section: [road number, municipality], approx. [N] km, EPSG:25833

## Method
[The five steps, one bullet point each.]

## Results
[One headline number. Number of flagged sections and their total length. Candidate count.
overview.png. 3-4 close-up views of the most interesting discrepancies.]

## Calibration and sources of error
[Which parameters you adjusted and against what reference. Number of false positives.]

## What would change at full scale
[Tiling driven by the road network. Linear road references as the key.
An existing DTM instead of a custom ground estimate.]

## Running the project
[Three commands.]
```

---

## Sources

- NVDB road object types — https://api.vegdata.no/endepunkt/vegobjekttyper.html
- NVDB road objects — https://api.vegdata.no/endepunkt/vegobjekter.html
- NVDB API Les V4 — https://nvdb-docs.atlas.vegvesen.no/nvdbapil/v4/introduksjon/Oversikt/
- Kartverket elevation data — https://www.kartverket.no/en/api-and-data/terrengdata
- vegkart.no — https://vegkart.no
