"""Kameras + Wandband beider Laeufe im Objektrahmen ueber LoD2; Paarabstands-Verhaeltnis Teil 0."""
import os, sys, json
import numpy as np
sys.path.insert(0, "/home/oem/git/rc-park/.claude/worktrees/agent-a5d004d794431467c/tools")
import wolke_grundriss_pruefen as WG
OUT = os.path.dirname(os.path.abspath(__file__)); M = "/home/oem/git/rc-park/modelle"
L = json.load(open(f"{OUT}/lagen.json")); st0, st1 = L["st"]["schwabentor-1120"], L["st"]["schwabentor-1122"]
teil = {os.path.splitext(k)[0]: v for k, v in L["teil"].items()}
obj = json.load(open(f"{M}/schwabentor-1120/objekt.json")); B = WG.grundrisse(obj, 60.0)
namen = sorted(set(st0) & set(st1)); X0 = np.array([st0[n] for n in namen]); X1 = np.array([st1[n] for n in namen]); tl = np.array([teil.get(n, -1) for n in namen])
for k in (0, 1):
    m = (tl == k) & (np.abs(X0).max(1) < 120) & (np.abs(X1).max(1) < 120); i, j = np.triu_indices(m.sum(), 1)
    d0 = np.linalg.norm(X0[m][i] - X0[m][j], axis=1); d1 = np.linalg.norm(X1[m][i] - X1[m][j], axis=1); ok = (d0 > 5)
    print(f"Teil {k}: n {m.sum()}, Paarabstand 1120/1122 Median {np.median(d0[ok] / d1[ok]):.3f} (P10 {np.percentile(d0[ok]/d1[ok],10):.3f}, P90 {np.percentile(d0[ok]/d1[ok],90):.3f})")
    for nm, X in (("1120", X0), ("1122", X1)):
        e = np.linalg.norm(X[m][:, :2] - np.array([-2.09, 15.16]), axis=1); print(f"   {nm}: Entfernung zur Turmmitte Median {np.median(e):.1f} m, Hoehe Median {np.median(X[m][:, 2]):.2f} m, Azimut-Median {np.degrees(np.median(np.unwrap(np.arctan2(X[m][:,1]-15.16, X[m][:,0]+2.09))))%360:.0f}")
rng = np.random.default_rng(0)
W = {}
for o in ("schwabentor-1120", "schwabentor-1122"):
    X = np.load(f"{M}/{o}/sfm/punkte_modell_{o}.npy", mmap_mode="r"); idx = np.sort(rng.choice(len(X), min(len(X), 3000000), replace=False)); P = np.asarray(X[idx], float)
    P = P[(P[:, 2] > 1.5) & (P[:, 2] < 9)]; W[o] = P[rng.choice(len(P), min(len(P), 200000), replace=False)]
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
fig, axs = plt.subplots(1, 2, figsize=(22, 11))
for ax, lim in zip(axs, (45, 16)):
    ax.scatter(W["schwabentor-1120"][:, 0], W["schwabentor-1120"][:, 1], s=0.15, c="tab:green", alpha=.5, label="Wand 1120")
    ax.scatter(W["schwabentor-1122"][:, 0], W["schwabentor-1122"][:, 1], s=0.15, c="tab:purple", alpha=.5, label="Wand 1122")
    for b in B:
        for g in b["ground"]:
            q = np.vstack([g, g[:1]]); ax.plot(q[:, 0], q[:, 1], "k", lw=2 if b["id"] == obj["lod2"]["id"] else 0.8)
    if lim > 20:
        a0 = np.array([v for v in st0.values()]); a1 = np.array([v for v in st1.values()])
        ax.scatter(a0[:, 0], a0[:, 1], s=6, c="green", marker="^", label="Kamera 1120"); ax.scatter(a1[:, 0], a1[:, 1], s=6, c="purple", marker="v", label="Kamera 1122")
    c = np.array([-2.09, 15.16]) if lim < 20 else np.array([0, 5]); ax.set_xlim(c[0] - lim, c[0] + lim); ax.set_ylim(c[1] - lim, c[1] + lim); ax.set_aspect("equal"); ax.grid(alpha=.3); ax.legend(markerscale=8)
    ax.set_title("Wandband z 1,5-9 m: 1120 gruen, 1122 lila, LoD2 schwarz (Ziel dick)")
plt.tight_layout(); plt.savefig(f"{OUT}/ueberlagert_1120_1122.png", dpi=55)
