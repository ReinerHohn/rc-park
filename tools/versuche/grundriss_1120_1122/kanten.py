"""Kantenweiser Grundriss-Vergleich (Logik wand_dicke_tor.kanten_messen) + Tor-A-Anteil (wie wolke_grundriss_pruefen, CPU) je Punktmenge."""
import os, sys, json
import numpy as np
from scipy.spatial import cKDTree
sys.path.insert(0, "/home/oem/git/rc-park/.claude/worktrees/agent-a5d004d794431467c/tools")
import wolke_grundriss_pruefen as WG, wand_dicke_tor as WD
from matplotlib.path import Path
OUT = os.path.dirname(os.path.abspath(__file__)); M = "/home/oem/git/rc-park/modelle"
obj = json.load(open(f"{M}/schwabentor-1120/objekt.json")); B = WG.grundrisse(obj, 60.0); zid = obj["lod2"]["id"]
gf = [g for b in B if b["id"] == zid for g in b["ground"]]; polys = [g for b in B for g in b["ground"] if len(g) >= 3]
W = np.vstack([p0 + np.linspace(0, 1, max(2, int(np.linalg.norm(p1 - p0) / 0.1)))[:, None] * (p1 - p0) for g in polys for p0, p1 in zip(np.vstack([g, g[:1]])[:-1], np.vstack([g, g[:1]])[1:])])
tw = cKDTree(W)
def tor_a(X, radius=60.0):
    band = (X[:, 2] > 1.5) & (X[:, 2] < 9) & (np.hypot(X[:, 0], X[:, 1]) < radius * 0.8); Q = X[band][:, :2]
    innen = np.zeros(len(Q), bool)
    for g in polys: innen |= Path(g).contains_points(Q)
    d, _ = tw.query(Q); return float((~innen & (d > 1.5)).mean()), int(len(Q))
rng = np.random.default_rng(0)
X20 = np.load(f"{M}/schwabentor-1120/sfm/punkte_modell_schwabentor-1120.npy", mmap_mode="r"); X20 = np.asarray(X20[np.sort(rng.choice(len(X20), 1500000, replace=False))], float)
X22 = np.load(f"{M}/schwabentor-1122/sfm/punkte_modell_schwabentor-1122.npy", mmap_mode="r"); X22 = np.asarray(X22[np.sort(rng.choice(len(X22), 1500000, replace=False))], float)
L = lambda n: np.load(f"{OUT}/{n}.npy").astype(float)
mengen = {"1120 dicht (ganz)": (X20, 200), "1122 dicht (ganz, geschrieben)": (X22, 200),
          "1120 sparse nur Teil0-Bilder": (L("p1120_sparse_t0"), 30), "1120 sparse nur Teil1-Bilder (verklebt)": (L("p1120_sparse_t1"), 30),
          "1120 sparse Fernfoto-Punkte": (L("p1120_sparse_fern"), 30), "1120 sparse Rest": (L("p1120_sparse_sonst"), 30),
          "1122 Teil0 dicht geschrieben": (L("p1122_teil0_lage1122"), 200), "1122 Teil1 dicht geschrieben": (L("p1122_teil1_lage1122"), 200),
          "1122 Teil0 dicht in 1120-Lage (Sim3 Kameras)": (L("p1122_teil0_lage1120"), 200)}
erg = {}
for name, (P, mp) in mengen.items():
    a, n = tor_a(P); ks = [k for g in gf for k in WD.kanten_messen(g, {"x": P}, min_punkte=mp)]
    erg[name] = dict(tor_a_anteil=round(a, 4), wandpunkte=n, kanten=[dict(von=k["von"], bis=k["bis"], L=k["laenge_m"], **k["teile"]["x"]) for k in ks])
    print(f"== {name}: Tor A {100*a:.1f} % (Wandband {n})")
    for k in erg[name]["kanten"]:
        print(f"   Kante {k['von']}->{k['bis']} ({k['L']} m): " + (f"Lage {k['lage_m']:+.2f} m, Dicke {k['dicke_m']:.2f}, n {k['n']}" + (f", Neigung {k['neigung_grad']}" if 'neigung_grad' in k else "") if "lage_m" in k else f"kein Urteil (n {k['n']})"))
json.dump(erg, open(f"{OUT}/kanten.json", "w"), indent=1)
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
fig, axs = plt.subplots(2, 3, figsize=(24, 16))
zeigen = [("1120 dicht (ganz)", "tab:green"), ("1120 sparse nur Teil0-Bilder", "tab:blue"), ("1120 sparse nur Teil1-Bilder (verklebt)", "tab:red"),
          ("1122 Teil0 dicht geschrieben", "tab:blue"), ("1122 Teil1 dicht geschrieben", "tab:red"), ("1122 Teil0 dicht in 1120-Lage (Sim3 Kameras)", "tab:purple")]
for ax, (name, col) in zip(axs.ravel(), zeigen):
    P = mengen[name][0]; P = P[(P[:, 2] > 1.5) & (P[:, 2] < 9)]; P = P[rng.choice(len(P), min(len(P), 150000), replace=False)]
    ax.scatter(P[:, 0], P[:, 1], s=0.3, c=col, alpha=.4)
    for b in B:
        for g in b["ground"]:
            q = np.vstack([g, g[:1]]); ax.plot(q[:, 0], q[:, 1], "k", lw=2 if b["id"] == zid else 0.7)
    ax.set_xlim(-22, 18); ax.set_ylim(-5, 35); ax.set_aspect("equal"); ax.grid(alpha=.3); ax.set_title(f"{name}\nTor A {100*erg[name]['tor_a_anteil']:.1f} %")
plt.tight_layout(); plt.savefig(f"{OUT}/kanten_vergleich.png", dpi=50)
