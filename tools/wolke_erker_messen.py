#!/usr/bin/env python3
"""wolke_erker_messen.py - Erker (vor die Wandebene vorspringende Bauteile) AUS DER WOLKE messen. Generisch, keine Objektnamen; Vorbild wolke_bogenreihe_messen.py.
Koordinaten: Netzrahmen m; n = horizontale Fassadennormale, u = n um -90 Grad (Fassadenrichtung), z = Hoehe. Ausgabe JSON: je Wert {wert, sigma, n_punkte, quelle, quelltyp, merkmal}.
Messung:
 1. Wandebene n_wand = Gipfel des n-Histogramms (5 cm) im Hoehenband --erker-z und u-Bereich --wand-u (zwischen den Erkern).
 2. Erker-Laeufe: je u-Bin (0,1 m) Punktzahl in n_wand+0,35 .. +1,6 (Hoehenband --erker-z, oberhalb von Balkon/Band) >= --min-punkte; Luecken < 0,3 m verschmolzen; Mindestbreite --min-breite.
    Anzahl_wolke = Zahl der Laeufe (NICHT Sollwert; Zaehlung = Foto, Regel 9: --n-foto/--n-foto-quelle nur Konsistenzvergleich, Widerspruch wird NICHT gemittelt).
 3. Je Erker: Mitte u / Breite = P2-P98 der u der Streifenpunkte; Frontflaeche n_front = Gipfel (5 cm) der n-Verteilung im Lauf; Auskragung = n_front - n_wand.
    Unter-/Oberkante der senkrechten Front: tiefstes/hoechstes z mit >= --anteil (0,25) der mittleren Dichte je 5 cm in Frontstreifen (n_front -0,3..+0,4).
    Dach: Silhouette n_P98(z) und u-Breite(z) in 0,5-m-Scheiben ueber der Oberkante (Punkte n > n_wand+0,1, >= 40 Pkt), Spitze = hoechstes z (P99,5); Dachform aus Steigung der Silhouette.
 sigma = Bootstrap (Punkte neu gezogen, 200x).
  /media/oem/scan/venv-seg/bin/python -I tools/wolke_erker_messen.py --wolke <npy> --achse-n 0.3338,0.9426 --aus <json> [--n-foto 2 --n-foto-quelle Z-004-003]"""
import os, sys, json, argparse, numpy as np
ap = argparse.ArgumentParser()
ap.add_argument("--wolke", required=True); ap.add_argument("--achse-n", required=True); ap.add_argument("--u-bereich", default="-14,13")
ap.add_argument("--wand-u", default="-6,6"); ap.add_argument("--erker-z", default="6.8,9.0"); ap.add_argument("--n-suche", default="12,15.5")
ap.add_argument("--min-punkte", type=int, default=40); ap.add_argument("--min-breite", type=float, default=0.8); ap.add_argument("--anteil", type=float, default=0.25)
ap.add_argument("--n-foto", type=int, default=None); ap.add_argument("--n-foto-quelle", default=None); ap.add_argument("--aus", required=True); ap.add_argument("--seed", type=int, default=1)
a = ap.parse_args(); rng = np.random.default_rng(a.seed); B = 200
n = np.array([float(v) for v in a.achse_n.split(",")]); n /= np.linalg.norm(n); ud = np.array([n[1], -n[0]])
W = np.load(a.wolke); N = W[:, :2] @ n; U = W[:, :2] @ ud; Z = W[:, 2]
f2 = lambda s: [float(v) for v in s.split(",")]
u0_, u1_ = f2(a.u_bereich); wu0, wu1 = f2(a.wand_u); z0_, z1_ = f2(a.erker_z); n0_, n1_ = f2(a.n_suche)
quelle = f"Wolke {os.path.basename(a.wolke)} ({len(W)} Pkt), n=({n[0]:.4f},{n[1]:.4f}), tools/wolke_erker_messen.py"
def wert(w, s, k, merkmal, extra=""): return dict(wert=round(float(w), 3), sigma=round(max(float(s), 0.025), 3), n_punkte=int(k), quelle=quelle + (" " + extra if extra else ""), quelltyp="Laser/Fotowolke (SfM-Punktwolke)", merkmal=merkmal)
def gipfel(x, lo, hi, w=0.05):
    h, e = np.histogram(x, bins=np.arange(lo, hi + w, w)); k = np.argmax(h); c = e[k] + w / 2; return float(np.median(x[np.abs(x - c) < 0.15]))   # Gipfel, dann Median +-15 cm (kein Bin-Raster im sigma)

# 1. Wandebene
m = (Z >= z0_) & (Z <= z1_) & (U >= wu0) & (U <= wu1) & (N >= n0_) & (N <= n1_)
nw = gipfel(N[m], n0_, n1_); nw = float(np.median(N[m & (np.abs(N - nw) < 0.2)]))
nws = N[m & (np.abs(N - nw) < 0.2)]; nw_s = float(np.std([np.median(nws[rng.integers(0, len(nws), len(nws))]) for _ in range(B)]))
# 2. Laeufe
bz = (Z >= z0_) & (Z <= z1_) & (U >= u0_) & (U <= u1_) & (N >= nw + 0.35) & (N <= nw + 1.6)
eu = np.arange(u0_, u1_ + 0.1, 0.1); hu, _ = np.histogram(U[bz], bins=eu); ok = hu >= a.min_punkte
runs, i = [], 0
while i < len(ok):
    if ok[i]:
        j = i
        while j + 1 < len(ok) and ok[j + 1]: j += 1
        runs.append([eu[i], eu[j + 1]]); i = j + 1
    else: i += 1
verm = [runs[0]] if runs else []
for r in runs[1:]:
    if r[0] - verm[-1][1] < 0.3: verm[-1][1] = r[1]
    else: verm.append(r)
verworfen = [dict(u0=round(r[0], 2), u1=round(r[1], 2), grund=f"Breite < {a.min_breite} m (Pilaster/Gesims, kein Erker)") for r in verm if r[1] - r[0] < a.min_breite]
verm = [r for r in verm if r[1] - r[0] >= a.min_breite]
erker = []
for k, r in enumerate(verm):
    s = bz & (U >= r[0] - 0.05) & (U <= r[1] + 0.05); idx = np.where(s)[0]; uu, nn = U[idx], N[idx]
    def mess(ix): return (*np.percentile(uu[ix], [2, 98]), gipfel(nn[ix], nw + 0.35, nw + 1.6))
    b0 = mess(np.arange(len(idx))); bs = np.array([mess(rng.integers(0, len(idx), len(idx))) for _ in range(B)])
    um, ub = (b0[0] + b0[1]) / 2, b0[1] - b0[0]; ums = ((bs[:, 0] + bs[:, 1]) / 2).std(); ubs = (bs[:, 1] - bs[:, 0]).std(); nf = b0[2]
    # Front-Streifen (ganze Hoehe, Erkerbreite innen)
    fs = (U >= b0[0] + 0.1) & (U <= b0[1] - 0.1) & (N >= nf - 0.3) & (N <= nf + 0.4) & (Z > 2) & (Z < 20); fi = np.where(fs)[0]; zf = Z[fi]
    zb = np.arange(2, 20.01, 0.05)
    def kanten(zz):
        h, _ = np.histogram(zz, bins=zb); mit = np.median(h[(zb[:-1] >= z0_) & (zb[:-1] < z1_)]); q = np.where(h >= max(5, a.anteil * mit))[0]
        # zusammenhaengender Block um das Mittelband (Luecken < 0,3 m ueberbrueckt)
        c = int(np.argmin(np.abs(zb[:-1] - (z0_ + z1_) / 2))); lo = c
        while lo > 0 and np.any(h[max(0, lo - 6):lo] >= max(5, a.anteil * mit)): lo -= 1
        hi = c
        while hi < len(h) - 1 and np.any(h[hi + 1:hi + 7] >= max(5, a.anteil * mit)): hi += 1
        return zb[lo], zb[hi + 1]
    ku0 = kanten(zf); ks = np.array([kanten(zf[rng.integers(0, len(zf), len(zf))]) for _ in range(B)]); zu, zo = ku0
    # Auskragung Bootstrap: Wand + Front gemeinsam neu gezogen
    aus_s = float(np.std(bs[:, 2] - nw)); aus_s = float(np.hypot(aus_s, nw_s))
    # Dach
    prof = []
    for z in np.arange(np.floor(zo * 2) / 2, 20, 0.5):
        q = (Z >= z) & (Z < z + 0.5) & (U >= r[0] - 0.3) & (U <= r[1] + 0.3) & (N > nw + 0.1) & (N < nw + 1.8)
        if q.sum() < 40: continue
        prof.append((z + 0.25, float(np.percentile(N[q], 98)) - nw, float(np.diff(np.percentile(U[q], [5, 95]))[0]), int(q.sum())))
    dz = np.array([p[0] for p in prof]); dn = np.array([p[1] for p in prof]); dw = np.array([p[2] for p in prof])
    ro = (Z > zo) & (U >= r[0] - 0.3) & (U <= r[1] + 0.3) & (N > nw + 0.1) & (N < nw + 1.8); zr = Z[ro]
    sp = float(np.percentile(zr, 99.5)); sps = float(np.std([np.percentile(zr[rng.integers(0, len(zr), len(zr))], 99.5) for _ in range(B)]))
    if len(dz) >= 3:
        sl, ic = np.polyfit(dz, dn, 1); sw, _ = np.polyfit(dz, dw, 1)
        sb = np.array([np.polyfit(dz[ii], dn[ii], 1)[0] for ii in (rng.integers(0, len(dz), len(dz)) for _ in range(B)) if len(set(ii)) > 1]); sl_s = float(sb.std())
        form = "geneigt_verjuengend (Helm/Pyramide/Zelt: Silhouette faellt zur Wand, Spitze %.1f m ueber Oberkante der Front)" % (sp - zo) if sl < -0.05 and sp - zo > 1.5 else ("flach/Pult" if abs(sl) < 0.05 else "ungeklaert")
    else: sl = sw = sl_s = np.nan; form = "ungeklaert (zu wenig Punkte)"
    erker.append(dict(index=k, mitte_u=wert(um, ums, len(idx), "Erker-Mitte entlang Fassade (u)"), breite=wert(ub, ubs, len(idx), "Erker-Breite P2-P98 (u)"),
        front_n=wert(nf, bs[:, 2].std(), len(idx), "n der Frontflaeche"), auskragung=wert(nf - nw, aus_s, len(idx), "Auskragung = n_front - n_wand"),
        unterkante_z=wert(zu, ks[:, 0].std(), len(fi), "Unterkante der senkrechten Front", f"(Block >= {a.anteil:.2f} x mittlere Dichte/5 cm)"),
        oberkante_z=wert(zo, ks[:, 1].std(), len(fi), "Oberkante der senkrechten Front / Dachansatz"),
        spitze_z=wert(sp, sps, len(zr), "hoechster Punkt (P99,5) ueber der Front im Erkerbereich (Laser/SfM blind fuer Nadeln, Untergrenze)"),
        dachform=dict(art=form, silhouette_steigung_n_je_z=wert(sl, sl_s, len(dz), "Steigung n_P98(z) in m/m"), breite_steigung_u_je_z=wert(sw, 0 if np.isnan(sw) else 0.0, len(dz), "Steigung u-Breite(z); sigma nicht bestimmt"),
                      profil=[dict(z=round(p[0], 2), n_ueber_wand=round(p[1], 2), u_breite=round(p[2], 2), n_punkte=p[3]) for p in prof], quelltyp="Laser/Fotowolke (SfM-Punktwolke)", merkmal="Dachform des Erkers", quelle=quelle)))
out = dict(achse_n=[round(float(n[0]), 4), round(float(n[1]), 4)], wandebene_n=wert(nw, nw_s, int(m.sum()), "Wandebene n (Gipfel im Band %.1f..%.1f m, u %.0f..%.0f)" % (z0_, z1_, wu0, wu1)),
           n_erker_aus_wolke=len(verm), kandidaten_verworfen=verworfen, erker=erker, hinweis="Anzahl_wolke ist KEIN Sollwert (Regel 9); Zaehlung nur Foto.")
if a.n_foto is not None: out["konsistenz_foto"] = dict(n_erker_foto=a.n_foto, quelle_foto=a.n_foto_quelle, n_erker_wolke=len(verm), gleich=(a.n_foto == len(verm)), hinweis="nur Vergleich, nicht gemittelt; Widerspruch bleibt offen (Regel 5)")
json.dump(out, open(a.aus, "w"), indent=1, ensure_ascii=False)
print(f"Wand n={nw:.2f}+-{nw_s:.3f}; Erker aus Wolke: {len(verm)}")
for e in erker: print(f" #{e['index']}: u={e['mitte_u']['wert']}+-{e['mitte_u']['sigma']} b={e['breite']['wert']}+-{e['breite']['sigma']} ausk={e['auskragung']['wert']}+-{e['auskragung']['sigma']} z {e['unterkante_z']['wert']}+-{e['unterkante_z']['sigma']} .. {e['oberkante_z']['wert']}+-{e['oberkante_z']['sigma']} spitze={e['spitze_z']['wert']}+-{e['spitze_z']['sigma']} {e['dachform']['art']}")
