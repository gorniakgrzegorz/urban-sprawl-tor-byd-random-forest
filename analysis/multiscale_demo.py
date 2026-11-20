"""Multi-scale agreement of new built-up land 1990-2015 (default series vs WSF Evolution) for the seven sites, computed
with landcoverrewind.accuracy.multiscale_agreement (blocks of 1, 3, 10 and 33 pixels, i.e. 30 m to about 1 km, and the
whole area). Rule fixed before computing: same sites, period and reference as the change F1 of the manuscript."""
import sys, json
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent.parent / "aplikacja"))
from landcoverrewind import accuracy as A
from common import *
out = {}
for d in sorted(OUT.iterdir()):
    if not (d / "gotowy.json").exists(): continue
    s = load_site(d.name, "gotowy"); w = wsf_on_grid(s)
    a = s["b"][2015] & ~s["b"][1990]; r = (w > 1990) & (w <= 2015)
    out[d.name] = {str(k): v for k, v in A.multiscale_agreement(a, r, s["area"]).items()}
    print(d.name, {k: round(v, 3) for k, v in out[d.name].items()})
json.dump(out, open("multiscale_demo.json", "w"), indent=1)
