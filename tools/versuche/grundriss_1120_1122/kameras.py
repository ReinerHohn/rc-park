"""Kamera-Vergleich 1122 -> 1120 im Objektrahmen (Standorte der SFM-AUSRICHTUNG), Sim3 global und je Teil, Restabweichung je Gruppe/Seite/Hoehe."""
import os, sys, json, collections
import numpy as np
sys.path.insert(0, "/home/oem/git/rc-park/.claude/worktrees/agent-a5d004d794431467c/tools")
import wolke_grundriss_pruefen as WG
OUT = os.path.dirname(os.path.abspath(__file__)); M = "/home/oem/git/rc-park/modelle"
L = json.load(open(f"{OUT}/lagen.json")); st0, st1 = L["st"]["schwabentor-1120"], L["st"]["schwabentor-1122"]; teil = {os.path.splitext(k)[0]: v for k, v in L["teil"].items()}
sys.path.insert(0, OUT); from eingaben_gruppe import gruppe
obj = json.load(open(f"{M}/schwabentor-1120/objekt.json")); B = WG.grundrisse(obj, 60.0)
zg = [g for b in B if b["id"] == obj["lod2"]["id"] for g in b["ground"]]; c0 = WG.flaechenmitte(max(zg, key=lambda g: WG.flaechenmitte(g)[1]))[0]

def sim3(X, Y, w=None):
    w = np.ones(len(X)) if w is None else w; w = w / w.sum(); mx, my = w @ X, w @ Y; Xc, Yc = X - mx, Y - my
    U, S, Vt = np.linalg.svd((Yc * w[:, None]).T @ Xc); Dm = np.eye(3); Dm[2, 2] = np.sign(np.linalg.det(U @ Vt)); R = U @ Dm @ Vt
    s = (S * np.diag(Dm)).sum() / (w @ (Xc ** 2).sum(1)); return s, R, my - s * R @ mx

def robust(X, Y, it=6):
    rng = np.random.default_rng(0); best = None
    for _ in range(800):
        i = rng.choice(len(X), 4, replace=False); s, R, t = sim3(X[i], Y[i]); r = np.linalg.norm(X @ (s * R).T + t - Y, axis=1); sc = np.minimum(r, 3.0).sum()
        if best is None or sc < best[0]: best = (sc, r)
    w = (best[1] < 3.0).astype(float)
    for _ in range(it):
        s, R, t = sim3(X, Y, w); r = np.linalg.norm(X @ (s * R).T + t - Y, axis=1); k = max(np.median(r[w > 0]) * 3, 0.3); w = (r < k).astype(float)
    return s, R, t, r, w > 0

def drehung_grad(R): return float(np.degrees(np.arctan2(R[1, 0], R[0, 0])))
def kipp_grad(R): return float(np.degrees(np.arccos(np.clip(R[2, 2], -1, 1))))
namen = sorted(set(st0) & set(st1))
X1 = np.array([st1[n] for n in namen], float); X0 = np.array([st0[n] for n in namen], float)
nah = (np.linalg.norm(X0[:, :2] - c0, axis=1) < 150) & (np.abs(X0[:, 2]) < 60) & (np.linalg.norm(X1[:, :2] - c0, axis=1) < 150) & (np.abs(X1[:, 2]) < 60)          # Fernfotos/Ausreisser aus dem Fit (ANNAHME 150 m)
erg = dict(gemeinsam=len(namen), nah=int(nah.sum()), lod2_mitte=c0.round(2).tolist())
roh = np.linalg.norm(X1 - X0, axis=1)
erg["roh_ohne_fit"] = dict(median_m=round(float(np.median(roh[nah])), 2), p90_m=round(float(np.percentile(roh[nah], 90)), 2))
tl = np.array([teil.get(n, -1) for n in namen]); gr = np.array([gruppe(n) for n in namen])
az = np.degrees(np.arctan2(X0[:, 1] - c0[1], X0[:, 0] - c0[0])) % 360; ent = np.linalg.norm(X0[:, :2] - c0, axis=1)
def bericht(r, maske, schl):
    out = {}
    for k in sorted(set(schl[maske])):
        m = maske & (schl == k)
        if m.sum() >= 3: out[str(k)] = dict(n=int(m.sum()), median_m=round(float(np.median(r[m])), 2), p90_m=round(float(np.percentile(r[m], 90)), 2))
    return out
# global
s, R, t, r, inl = robust(X1[nah], X0[nah]); rg = np.full(len(namen), np.nan); rg[nah] = r
V = np.zeros_like(X1); V[:] = np.nan; V[nah] = X1[nah] @ (s * R).T + t - X0[nah]
erg["global"] = dict(s=round(float(s), 4), dreh=round(drehung_grad(R), 2), kipp=round(kipp_grad(R), 2), t=np.round(t, 2).tolist(), inlier=int(inl.sum()), median_m=round(float(np.median(r)), 2),
                     p90_m=round(float(np.percentile(r, 90)), 2), je_teil=bericht(rg, nah, tl), je_gruppe=bericht(rg, nah, gr),
                     je_sektor=bericht(rg, nah & (ent < 60), (az // 45 * 45).astype(int)))
# je Teil eigener Fit
erg["je_teil_fit"] = {}; VT = np.full_like(X1, np.nan)
for k in sorted(set(tl)):
    m = nah & (tl == k)
    if m.sum() < 8: continue
    s, R, t, r, inl = robust(X1[m], X0[m]); VT[m] = X1[m] @ (s * R).T + t - X0[m]; rr = np.full(len(namen), np.nan); rr[m] = r
    # Versatz ohne Fit (Objektrahmen): Median der Differenz -> starrer Teilversatz in der GESCHRIEBENEN Lage
    d = X1[m] - X0[m]
    erg["je_teil_fit"][str(k)] = dict(n=int(m.sum()), s=round(float(s), 4), dreh=round(drehung_grad(R), 2), kipp=round(kipp_grad(R), 2), median_m=round(float(np.median(r)), 2),
                                      p90_m=round(float(np.percentile(r, 90)), 2), roh_versatz_median_xyz=np.round(np.median(d, 0), 2).tolist(),
                                      roh_abstand_median=round(float(np.median(np.linalg.norm(d, axis=1))), 2), je_gruppe=bericht(rr, m, gr),
                                      je_sektor=bericht(rr, m & (ent < 60), (az // 45 * 45).astype(int)))
# Biegung: in Teil 0 Rest gegen Azimut/Hoehe korrelieren (eigener Fit)
m = nah & (tl == 0) & (ent < 60); rv = np.linalg.norm(VT[m], axis=1)
erg["teil0_biegung"] = dict(rest_gegen_entfernung_spearman=round(float(np.corrcoef(np.argsort(np.argsort(ent[m])), np.argsort(np.argsort(rv)))[0, 1]), 2),
                            rest_gegen_hoehe_spearman=round(float(np.corrcoef(np.argsort(np.argsort(X0[m, 2])), np.argsort(np.argsort(rv)))[0, 1]), 2))
json.dump(erg, open(f"{OUT}/kameras.json", "w"), indent=1)
print(json.dumps(erg, indent=1)[:7000])
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
fig, axs = plt.subplots(1, 3, figsize=(27, 9))
for ax, (V_, tit) in zip(axs, [(X1 - X0, "ROH: Standort 1122 - 1120 (geschriebene Lage, ohne Fit)"), (V, "nach EINER Sim3 1122->1120 (global)"), (VT, "nach Sim3 JE TEIL (Form in sich)")]):
    for b in B:
        for g in b["ground"]:
            q = np.vstack([g, g[:1]]); ax.plot(q[:, 0], q[:, 1], "k" if b["id"] == obj["lod2"]["id"] else "0.7", lw=1.5 if b["id"] == obj["lod2"]["id"] else 0.7)
    mm = nah & ~np.isnan(V_[:, 0]); col = {0: "tab:blue", 1: "tab:red"}
    for k in (0, 1, -1):
        q = mm & (tl == k)
        ax.quiver(X0[q, 0], X0[q, 1], V_[q, 0], V_[q, 1], angles="xy", scale_units="xy", scale=0.5, color=col.get(k, "0.4"), width=0.002, label=f"Teil {k} (n {q.sum()})")
    ax.set_aspect("equal"); ax.set_xlim(-50, 50); ax.set_ylim(-50, 50); ax.set_title(tit + "\nPfeile 2-fach, Fuss = Kamera 1120"); ax.legend(); ax.grid(alpha=.3)
plt.tight_layout(); plt.savefig(f"{OUT}/kameras_vergleich.png", dpi=60)
