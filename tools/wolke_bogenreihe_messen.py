#!/usr/bin/env python3
"""wolke_bogenreihe_messen.py - Parameter einer Bogenreihe (Arkade) AUS DER WOLKE messen (Quelle fuer tools/baukasten_gen.py Bauteil 'bogenreihe').
Generisch: keine Objektnamen; Fassadennormale/Wolke/Suchbereich per Argument. Ausgabe JSON: je Wert {wert, sigma, n_punkte, quelle}.

Messung (alles Wolke, Netzrahmen m; n = horizontale Fassadennormale, u = n um -90 Grad, z = Hoehe):
 1. Pfeiler: Schnitt im Hoehenband --pfeiler-z (z. B. 2,0-3,2 m). n-Lage = Gipfel des n-Histogramms im Band; u-Histogramm (5 cm) der Punkte
    im n-Streifen -> zusammenhaengende Laeufe (Luecken < 0,3 m verschmolzen) = Pfeiler. Mitte u/n = Mitte der P3-P97-Spanne, Breite/Tiefe = Spanne
    (Rundpfeiler: Wolke sieht nur den Ring). sigma = Bootstrap (Punkte neu gezogen, 200x). Raster aus Mittenfolge u0 + i*pitch (lineare Ausgleichung, Restabweichung).
 2. Bogenlaibung: je Bogen (Feld zwischen zwei Pfeilern) pro u-Spalte (--spalte 0,1 m) die UNTERSTE dichte z (>=5 Punkte innerhalb 0,25 m) oberhalb --bogen-zmin im
    Bogenstreifen (n-Lage des Pfeilers +-tiefe); Spalten naeher als Pfeilerbreite/2+0,15 m an einem Pfeiler entfallen. Gemeinsamer Kreisfit (R, zc gemeinsam, uc je Bogen
    = Mitte zwischen den Pfeilern fest) nach kleinsten Quadraten (scipy), Bootstrap-sigma ueber die Spalten. Daraus scheitel_z = zc+R, kaempfer_z = zc+sqrt(R^2-(lichte/2)^2).
 3. Laibungstiefe: n-Spanne (P5-P95) der Wolkenpunkte direkt ueber der Laibung (0,05-0,4 m darueber), Pfeilerfuss: untere z-Grenze (P2) der Pfeilerpunkte im Ring (Boden).
 4. Oberkante (optional --balkon-n n0,n1): tiefstes z mit >=200 Punkten je 5 cm in n0..n1 im Bogenbereich = Unterseite des vorspringenden Bandes.
ZAEHLUNG der Boegen NICHT hier (Regel 9): --n-foto <Zahl> --n-foto-quelle <Z-Protokoll> wird nur zum Konsistenzvergleich (n_pfeiler-1) eingetragen.
  /media/oem/scan/venv-seg/bin/python -I tools/wolke_bogenreihe_messen.py --wolke <npy> --achse-n nx,ny --u-bereich -14,13 --aus <json> [--n-foto 4 --n-foto-quelle Z-004-001]"""
import os, sys, json, argparse, numpy as np
from scipy.optimize import least_squares

ap = argparse.ArgumentParser()
ap.add_argument("--wolke", required=True); ap.add_argument("--achse-n", required=True); ap.add_argument("--u-bereich", default="-14,13")
ap.add_argument("--pfeiler-z", default="2.0,3.2"); ap.add_argument("--bogen-zmin", type=float, default=2.6); ap.add_argument("--spalte", type=float, default=0.1)
ap.add_argument("--n-suche", default="9,16", help="n-Bereich, in dem der Pfeiler-Gipfel gesucht wird"); ap.add_argument("--min-punkte", type=int, default=25, help="u-Histogramm 5 cm: Mindestzahl je Bin")
ap.add_argument("--balkon-n", default=None); ap.add_argument("--n-foto", type=int, default=None); ap.add_argument("--n-foto-quelle", default=None); ap.add_argument("--aus", required=True)
ap.add_argument("--seed", type=int, default=1); ap.add_argument("--min-breite", type=float, default=0.15); ap.add_argument("--fuss-min", type=int, default=4, help="Punkte je 5 cm fuer Pfeilerfuss")
a = ap.parse_args(); rng = np.random.default_rng(a.seed)
n = np.array([float(v) for v in a.achse_n.split(",")]); n /= np.linalg.norm(n); ud = np.array([n[1], -n[0]])
W = np.load(a.wolke); N = W[:, :2] @ n; U = W[:, :2] @ ud; Z = W[:, 2]
u0_, u1_ = [float(v) for v in a.u_bereich.split(",")]; z0_, z1_ = [float(v) for v in a.pfeiler_z.split(",")]; n0_, n1_ = [float(v) for v in a.n_suche.split(",")]
quelle = f"Wolke {os.path.basename(a.wolke)} ({len(W)} Pkt), n=({n[0]:.4f},{n[1]:.4f}), tools/wolke_bogenreihe_messen.py"
def wert(w, s, k, extra=""): return dict(wert=round(float(w), 3), sigma=round(float(s), 3), n_punkte=int(k), quelle=quelle + (" " + extra if extra else ""))

# ---- 1. Pfeiler
b = (Z >= z0_) & (Z <= z1_) & (U >= u0_) & (U <= u1_) & (N >= n0_) & (N <= n1_)
h, e = np.histogram(N[b], bins=np.arange(n0_, n1_ + 0.05, 0.05)); n_pk = e[np.argmax(h)] + 0.025
for _ in range(2):                                                                      # Gipfel -> Streifen +-0,7 -> Gipfel (Ring: Mitte, nicht Wandpunkte)
    s = b & (np.abs(N - n_pk) < 0.7); n_pk = float(np.median(N[s & (np.abs(N - n_pk) < 0.5)]))
s = b & (np.abs(N - n_pk) < 0.7); hu, eu = np.histogram(U[s], bins=np.arange(u0_, u1_ + 0.05, 0.05)); ok = hu >= a.min_punkte
runs, i = [], 0
while i < len(ok):
    if ok[i]:
        j = i
        while j + 1 < len(ok) and ok[j + 1]: j += 1
        runs.append([eu[i], eu[j + 1]]); i = j + 1
    else: i += 1
verm = [runs[0]]
for r in runs[1:]:
    if r[0] - verm[-1][1] < 0.3: verm[-1][1] = r[1]
    else: verm.append(r)
pf = []
for r in verm:
    m = s & (U >= r[0] - 0.05) & (U <= r[1] + 0.05)
    if m.sum() < 100: continue
    uu, nn = U[m], N[m]
    def mess(idx):
        lo, hi = np.percentile(uu[idx], [3, 97]); nl, nh = np.percentile(nn[idx], [3, 97]); return (lo + hi) / 2, hi - lo, (nl + nh) / 2, nh - nl
    base = mess(np.arange(len(uu))); bs = np.array([mess(rng.integers(0, len(uu), len(uu))) for _ in range(200)])
    zz = Z[m]; pf.append(dict(u=base[0], u_s=bs[:, 0].std(), breite=base[1], breite_s=bs[:, 1].std(), n=base[2], n_s=bs[:, 2].std(), tiefe=base[3], tiefe_s=bs[:, 3].std(), k=int(m.sum()), z_unten=float(np.percentile(zz, 2))))
pf = [p for p in pf if p["breite"] >= a.min_breite]                                     # Staubfahnen/Kanten (< min_breite) sind keine Pfeiler
if len(pf) < 2: sys.exit("weniger als 2 Pfeiler gefunden")
pf.sort(key=lambda p: p["u"]); bmax = float(np.median([p["breite"] for p in sorted(pf, key=lambda p: -p["breite"])[:max(2, len(pf) // 2)]]))
voll = [p for p in pf if p["breite"] >= 0.8 * bmax]                                       # Ring voll sichtbar; Randpfeiler sind oft nur halb gescannt -> Mitte verschoben, nicht fuers Raster verwenden
for p in pf: p["teilsichtbar"] = p not in voll
if len(voll) < 2: sys.exit("weniger als 2 voll sichtbare Pfeiler")
pitch0 = float(np.median(np.diff([p["u"] for p in voll]))); uv = np.array([p["u"] for p in voll]); idxv = np.round((uv - uv[0]) / pitch0)
A = np.c_[np.ones(len(voll)), idxv]; (c0, pitch), *_ = np.linalg.lstsq(A, uv, rcond=None); rest = uv - A @ [c0, pitch]
pitch_s = float(np.sqrt(np.sum(rest ** 2) / max(len(voll) - 2, 1) / np.sum((idxv - idxv.mean()) ** 2))) if len(voll) > 2 else float(np.mean([p["u_s"] for p in voll]) + 0.05)
for p in pf: p["index"] = int(round((p["u"] - c0) / pitch)); p["u_raster"] = float(c0 + p["index"] * pitch)
i_min = min(p["index"] for p in pf); i_max = max(p["index"] for p in pf); c0 = float(c0 + i_min * pitch); n_p = i_max - i_min + 1
if n_p != len(pf): print(f"  HINWEIS: {n_p - len(pf)} Rasterposition(en) ohne gemessenen Pfeiler (verdeckt)")
uc = np.array([c0 + i * pitch for i in range(n_p)]); pf_alle = pf
pbr = float(np.median([p["breite"] for p in voll])); pti = float(np.median([p["tiefe"] for p in voll])); nmitte = float(np.median([p["n"] for p in voll]))
# Pfeilerfuss: tiefstes z mit >= 10 Punkten je 5 cm im Pfeiler-Ring (Boden nicht ueber das z-Band begrenzt)
zfuss = []
for p in voll:
    mm = (np.abs(U - p["u"]) < pbr / 2 + 0.1) & (np.abs(N - p["n"]) < pti / 2 + 0.1) & (Z < z1_); hz, ez = np.histogram(Z[mm], bins=np.arange(0.5, z1_ + 0.05, 0.05)); q = np.where(hz >= a.fuss_min)[0]
    if len(q): zfuss.append(ez[q[0]])
for p in pf: p["z_unten"] = None
lichte = pitch - pbr

# ---- 2. Laibung
bz = (Z >= a.bogen_zmin) & (Z <= 8) & (np.abs(N - nmitte) < max(pti, 0.5) + 0.3) & (U >= uc[0]) & (U <= uc[-1])
pts = []                                                                                 # (bogen_index, u, z)
for k in range(len(uc) - 1):
    ub = (uc[k] + uc[k + 1]) / 2
    for uu in np.arange(uc[k] + pbr / 2 + 0.15, uc[k + 1] - pbr / 2 - 0.15, a.spalte):
        z = np.sort(Z[bz & (np.abs(U - uu) < a.spalte / 2 + 0.03)]); lo = None
        for q in range(len(z) - 5):
            if z[q + 5] - z[q] < 0.25: lo = z[q]; break
        if lo is not None: pts.append((k, uu, lo))
pts = np.array(pts); nb = len(uc) - 1; ub = np.array([(uc[k] + uc[k + 1]) / 2 for k in range(nb)])
def res(p, P):
    R, zc = p; return np.hypot(P[:, 1] - ub[P[:, 0].astype(int)], P[:, 2] - zc) - R
def fit(P):
    r = least_squares(res, [lichte / 2, np.median(P[:, 2]) - lichte / 2], args=(P,), loss="soft_l1", f_scale=0.1); return r.x
R_, zc_ = fit(pts); bsR = []; bsZ = []
for _ in range(200):
    P = pts[rng.integers(0, len(pts), len(pts))]; r_, z_ = fit(P); bsR.append(r_); bsZ.append(z_)
R_s, zc_s = float(np.std(bsR)), float(np.std(bsZ)); sch = zc_ + R_; sch_s = float(np.std(np.array(bsR) + np.array(bsZ)))
halbkreis = R_ <= lichte / 2 + 0.05                                                      # Kreis schmaler als Pfeilerabstand: Halbkreis, der auf Kaempferbloecken sitzt (Kaempfer = Kreismitte)
if halbkreis: kz, kz_s, oeff, oeff_s = zc_, zc_s, 2 * R_, 2 * R_s
else: kz = zc_ + np.sqrt(R_ ** 2 - (lichte / 2) ** 2); kz_s = float(np.std(np.array(bsZ) + np.sqrt(np.maximum(np.array(bsR) ** 2 - (lichte / 2) ** 2, 0)))); oeff, oeff_s = lichte, np.hypot(pitch_s, 0.04)
rm = np.sqrt(np.mean(res([R_, zc_], pts) ** 2))

# ---- 3. Laibungstiefe
dt = []
for k, uu, lo in pts:
    m = (np.abs(U - uu) < 0.1) & (Z > lo + 0.05) & (Z < lo + 0.4) & (N > nmitte - 1.5) & (N < nmitte + 1.5); dt.append(N[m])
dt = np.concatenate(dt); nl, nh = np.percentile(dt, [5, 95]) if len(dt) else (np.nan, np.nan)
out = dict(achse_n=[round(float(n[0]), 4), round(float(n[1]), 4)], n_pfeiler=wert(n_p, 0, sum(p["k"] for p in pf), "(Pfeiler = Laeufe im u-Histogramm, Raster)"),
           n_boegen_aus_wolke=n_p - 1,
           u0=wert(c0, voll[0]["u_s"] + pitch_s, voll[0]["k"], "Mitte erster Pfeiler (Raster aus voll sichtbaren Pfeilern)"), pitch=wert(pitch, pitch_s, len(voll), f"Pfeilerabstand, Ausgleichung ueber {len(voll)} voll sichtbare Pfeiler, Rest max {np.abs(rest).max():.3f} m"),
           pfeiler_breite=wert(pbr, np.std([p["breite"] for p in voll]), sum(p["k"] for p in voll), "u-Spanne P3-P97 (Rundpfeiler: Ringdurchmesser)"),
           pfeiler_tiefe=wert(pti, np.std([p["tiefe"] for p in voll]), sum(p["k"] for p in voll), "n-Spanne P3-P97"),
           pfeiler_n=wert(nmitte, np.std([p["n"] for p in voll]), sum(p["k"] for p in voll), "n-Mitte der Pfeiler"),
           pfeiler_z_unten=wert(np.median(zfuss), np.std(zfuss), len(zfuss), "tiefstes z mit >=4 Pkt/5 cm im Pfeilerring (Wolke ohne Bodenpunkte; Fuss evtl. tiefer) (Boden/Fuss)"),
           lichte_breite=wert(lichte, np.hypot(pitch_s, np.std([p["breite"] for p in voll])), len(voll), "pitch - pfeiler_breite"),
           radius=wert(R_, R_s, len(pts), f"Kreisfit Laibung, RMS {rm:.3f} m, {'Halbkreis auf Kaempferblock (R <= Pfeilerlichte/2)' if halbkreis else 'Segment-/Stichbogen'}"),
           kreis_zc=wert(zc_, zc_s, len(pts)), scheitel_z=wert(sch, sch_s, len(pts), "Laibungsscheitel zc+R"), kaempfer_z=wert(kz, kz_s, len(pts), "Halbkreis: Kreismitte zc; Segment: Kreis bei u = Pfeilerkante"), oeffnung_breite=wert(oeff, oeff_s, len(pts), "Breite der Bogenoeffnung am Kaempfer (Halbkreis 2R; sonst Pfeilerlichte)"), bogen_art="halbkreis" if halbkreis else "segment",
           laibung_tiefe=wert(nh - nl, 0.05, len(dt), "n-Spanne P5-P95 0,05-0,4 m ueber der Laibung (Bogenband)") if len(dt) else None,
           pfeiler=pf_alle, laibungspunkte=int(len(pts)))
if a.balkon_n:
    bn0, bn1 = [float(v) for v in a.balkon_n.split(",")]; m = (N >= bn0) & (N <= bn1) & (U >= uc[0]) & (U <= uc[-1]) & (Z > 2); zb = np.arange(2, 9, 0.05); hh, _ = np.histogram(Z[m], bins=np.append(zb, 9.0 + 0.0))
    iz = [q for q in range(len(hh)) if hh[q] >= 200]; out["oberkante_z"] = wert(zb[iz[0]] if iz else np.nan, 0.05, int(m.sum()), f"tiefstes z mit >=200 Pkt/5 cm in n {bn0}..{bn1} (Unterseite des vorspringenden Bandes)")
if a.n_foto is not None: out["konsistenz_foto"] = dict(n_boegen_foto=a.n_foto, quelle_foto=a.n_foto_quelle, n_boegen_wolke=n_p - 1, gleich=(a.n_foto == n_p - 1), hinweis="nur Vergleich; Zaehlung = Foto (Regel 9)")
json.dump(out, open(a.aus, "w"), indent=1, ensure_ascii=False)
print(f"Pfeiler {n_p} (gemessen {len(pf)}, voll {len(voll)}): u0={c0:.2f} pitch={pitch:.2f}+-{pitch_s:.3f} breite={pbr:.2f} tiefe={pti:.2f} n={nmitte:.2f} z_unten={out['pfeiler_z_unten']['wert']}"+f" teilsichtbar={[round(p['u'],2) for p in pf if p['teilsichtbar']]}")
print(f"Laibung: R={R_:.2f}+-{R_s:.2f} zc={zc_:.2f}+-{zc_s:.2f} scheitel={sch:.2f}+-{sch_s:.2f} kaempfer={kz:.2f}+-{kz_s:.2f} lichte={lichte:.2f} RMS={rm:.3f} ({len(pts)} Spalten) tiefe={nh - nl:.2f}")
if a.balkon_n: print("oberkante", out["oberkante_z"])
