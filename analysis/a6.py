"""A6/A9: scene cloud-cover limit (50, 70, 90%) and run-to-run reproducibility on a 9 km2 box in Torun (all epochs)."""
import sys, json, time, numpy as np
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent.parent / "aplikacja"))
from odc.geo.geom import box
from landcoverrewind import pipeline
g = box(18.60, 53.00, 18.645, 53.027, "EPSG:4326")
res = {}
for tag, mc in (("c50", 50), ("c70a", 70), ("c70b", 70), ("c90", 90)):
    t0 = time.time()
    r = pipeline.run(g, None, "pretrained", 0.65, tag, None, mc, log=lambda m: None)
    np.savez_compressed(f"{tag}.npz", **{f"b{t}": r["B"][t] for t in r["B"]}, **{f"p{t}": np.nan_to_num(r["P"][t], nan=-1) for t in r["P"]}, area=r["area"])
    res[tag] = dict(time_s=round(time.time() - t0), scenes={i["epoch"]: i["scenes"] for i in r["inputs"]}, skipped=r["skipped"],
                    ha={t: float(r["B"][t][r["area"]].sum() * 0.09) for t in r["B"]})
    print(tag, res[tag], flush=True)
json.dump(res, open("a6.json", "w"), indent=1)
