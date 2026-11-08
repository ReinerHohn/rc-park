#!/usr/bin/env python3
"""wolke_balkon_messen.py - Balkon/Galerieband (vor die Wandebene vorspringendes, waagerechtes Band zwischen Erkern, ueber einer Arkade) AUS DER WOLKE messen.
Generisch, keine Objektnamen; Vorbild wolke_erker_messen.py (gleicher Rahmen: Netzrahmen m; n = horizontale Fassadennormale, u = n um -90 Grad, z = Hoehe).
Ausgabe JSON: je Wert {wert, sigma, n_punkte, quelle, quelltyp, merkmal}; sigma = Bootstrap (Punkte neu gezogen, 200x), Untergrenze 0,025 m.
Messung:
 1. Wandebene n_wand = Gipfel (5 cm) im Hoehenband --wand-z und u-Bereich --wand-u (oberhalb des Bandes, zwischen den Erkern).
 2. Frontflaeche n_front = Gipfel (5 cm) der n-Verteilung im Hoehenband --front-z, u-Bereich --band-u, n > n_wand + 0,3. Auskragung = n_front - n_wand.
 3. Front-Streifen (n_front +-0,15): Unter-/Oberkante der senkrechten Front = tiefstes/hoechstes z eines zusammenhaengenden Blocks (Luecken < 0,3 m) mit >= --anteil x mittlere Dichte je 5 cm.
 4. Unterseite (Soffit): Gipfel der z-Verteilung (5 cm) der Punkte zwischen Wand und Front (n_wand+0,15 .. n_front-0,15) im Fenster Frontunterkante -0,5 .. +0,3.
    Oberseite: Gipfel der z-Verteilung im Fenster Frontoberkante -0,3 .. +0,3 im selben n-Bereich.
 5. u-Ausdehnung: u-Histogramm (0,1 m) der Frontstreifenpunkte; Laeufe >= --min-punkte, Luecken < --luecke verschmolzen. Ein Lauf = durchgehendes Band; mehrere = getrennte Platten (Luecken werden mit Breite gemeldet).
    Wolke ist an Verdeckungen/Seitenflaechen blind: Randluecken zu Erkern nicht als Bauteilfuge deuten (Hinweis in der Ausgabe).
 6. Bruestungsdicke: n-Spanne (P5-P95) der Oberseitenpunkte (z innerhalb +-0,06 um den Oberseiten-Gipfel) = OBERGRENZE der Dicke (Oberseite deckt ggf. Wand dahinter); dazu Dichte im Inneren (n_wand+0,15..n_front-0,25, Hoehe der Front) relativ zur Front -> hohl/offen?
 Zaehlung (Platten) = nur Konsistenz; Regel 9: Zaehlung Foto.  Widerspruch Wolke/Foto wird NICHT gemittelt (--foto-hinweis nur als Text).
  /media/oem/scan/venv-seg/bin/python -I tools/wolke_balkon_messen.py --wolke <npy> --achse-n 0.3338,0.9426 --aus <json>"""
import os, json, argparse, numpy as np
ap = argparse.ArgumentParser()
ap.add_argument("--wolke", required=True); ap.add_argument("--achse-n", required=True); ap.add_argument("--aus", required=True)
ap.add_argument("--band-u", default="-6,6"); ap.add_argument("--wand-u", default="-6,6"); ap.add_argument("--wand-z", default="6.8,9.0"); ap.add_argument("--front-z", default="5.3,5.9")
ap.add_argument("--n-suche", default="13,15.5"); ap.add_argument("--min-punkte", type=int, default=40); ap.add_argument("--luecke", type=float, default=0.3)
ap.add_argument("--anteil", type=float, default=0.25); ap.add_argument("--u-weit", default="-14,13"); ap.add_argument("--foto-hinweis", default=None); ap.add_argument("--erker-json", default=None, help="erker_messung.json: Laeufe, die in Erkern liegen (Erkerfront bei aehnlichem n), werden als Erker verworfen")
ap.add_argument("--seed", type=int, default=1)
a = ap.parse_args(); rng = np.random.default_rng(a.seed); B = 200
f2 = lambda s: [float(v) for v in s.split(",")]
n = np.array(f2(a.achse_n)); n /= np.linalg.norm(n); ud = np.array([n[1], -n[0]])
W = np.load(a.wolke); N = W[:, :2] @ n; U = W[:, :2] @ ud; Z = W[:, 2]
bu0, bu1 = f2(a.band_u); wu0, wu1 = f2(a.wand_u); wz0, wz1 = f2(a.wand_z); fz0, fz1 = f2(a.front_z); n0_, n1_ = f2(a.n_suche); uw0, uw1 = f2(a.u_weit)
quelle = f"Wolke {os.path.basename(a.wolke)} ({len(W)} Pkt), n=({n[0]:.4f},{n[1]:.4f}), tools/wolke_balkon_messen.py"
def wert(w, s, k, merkmal, extra=""): return dict(wert=round(float(w), 3), sigma=round(max(float(s), 0.025), 3), n_punkte=int(k), quelle=quelle + (" " + extra if extra else ""), quelltyp="Laser/Fotowolke (SfM-Punktwolke)", merkmal=merkmal)
def gipfel(x, lo, hi, w=0.05):
    h, e = np.histogram(x, bins=np.arange(lo, hi + w, w)); c = e[np.argmax(h)] + w / 2; return float(np.median(x[np.abs(x - c) < 0.15]))
def boot(fn, k, bsel=B):
    return float(np.std([fn(rng.integers(0, k, k)) for _ in range(bsel)]))
# 1. Wand
mw = (Z >= wz0) & (Z <= wz1) & (U >= wu0) & (U <= wu1) & (N >= n0_) & (N <= n1_); xw = N[mw]
nw = gipfel(xw, n0_, n1_); xw = xw[np.abs(xw - nw) < 0.2]; nw = float(np.median(xw)); nw_s = boot(lambda i: np.median(xw[i]), len(xw))
# 2. Front
mf = (Z >= fz0) & (Z <= fz1) & (U >= bu0) & (U <= bu1) & (N >= nw + 0.3) & (N <= n1_); xf = N[mf]
nf = gipfel(xf, nw + 0.3, n1_); xf2 = xf[np.abs(xf - nf) < 0.15]; nf = float(np.median(xf2)); nf_s = boot(lambda i: np.median(xf2[i]), len(xf2))
# 3. Kanten der Front
st = (U >= bu0) & (U <= bu1) & (np.abs(N - nf) <= 0.15) & (Z > 2) & (Z < 12); zf = Z[st]; zb = np.arange(2, 12.01, 0.05)
def kanten(zz):
    h, _ = np.histogram(zz, bins=zb); c = int(np.argmin(np.abs(zb[:-1] - (fz0 + fz1) / 2))); mit = np.median(h[(zb[:-1] >= fz0) & (zb[:-1] < fz1)]); sw = max(5, a.anteil * mit)
    lo = c
    while lo > 0 and np.any(h[max(0, lo - 6):lo] >= sw): lo -= 1
    hi = c
    while hi < len(h) - 1 and np.any(h[hi + 1:hi + 7] >= sw): hi += 1
    return zb[lo], zb[hi + 1]
zu, zo = kanten(zf); ks = np.array([kanten(zf[rng.integers(0, len(zf), len(zf))]) for _ in range(B)])
# 4. Unter-/Oberseite
inn = (U >= bu0) & (U <= bu1) & (N >= nw + 0.15) & (N <= nf - 0.15)
def zgip(lo, hi):
    q = inn & (Z >= lo) & (Z <= hi); zz = Z[q]
    if len(zz) < 30: return None
    g = gipfel(zz, lo, hi); zz2 = zz[np.abs(zz - g) < 0.1]; return float(np.median(zz2)), zz2, g
su = zgip(zu - 0.5, zu + 0.3); so = zgip(zo - 0.3, zo + 0.3)
def zw(r, merk):
    if r is None: return dict(wert=None, hinweis="zu wenig Punkte", merkmal=merk)
    return wert(r[0], boot(lambda i: np.median(r[1][i]), len(r[1])), len(r[1]), merk)
# 5. u-Ausdehnung
sb = (U >= uw0) & (U <= uw1) & (np.abs(N - nf) <= 0.15) & (Z >= zu + 0.1) & (Z <= zo - 0.1); eu = np.arange(uw0, uw1 + 0.1, 0.1); hu, _ = np.histogram(U[sb], bins=eu); ok = hu >= a.min_punkte
runs, i = [], 0
while i < len(ok):
    if ok[i]:
        j = i
        while j + 1 < len(ok) and ok[j + 1]: j += 1
        runs.append([eu[i], eu[j + 1]]); i = j + 1
    else: i += 1
verm = [runs[0]] if runs else []
for r in runs[1:]:
    if r[0] - verm[-1][1] < a.luecke: verm[-1][1] = r[1]
    else: verm.append(r)
verm = [r for r in verm if r[1] - r[0] >= 0.8]   # Mindestlaenge: kein Pilaster/Rauschen
verw = []
if a.erker_json:
    for e in json.load(open(a.erker_json))["erker"]:
        e0, e1 = e["mitte_u"]["wert"] - e["breite"]["wert"] / 2 - 0.3, e["mitte_u"]["wert"] + e["breite"]["wert"] / 2 + 0.3
        for r in list(verm):
            if r[0] >= e0 and r[1] <= e1: verm.remove(r); verw.append(dict(u_von=round(r[0], 2), u_bis=round(r[1], 2), grund="liegt im Erker (erker_messung.json), nicht Balkon"))
teile = []
for k, r in enumerate(verm):
    s = np.where(sb & (U >= r[0] - 0.05) & (U <= r[1] + 0.05))[0]; uu = U[s]
    m0 = lambda ix: np.percentile(uu[ix], [2, 98]); b0 = m0(np.arange(len(s))); bs = np.array([m0(rng.integers(0, len(s), len(s))) for _ in range(B)])
    teile.append(dict(index=k, u_von=wert(b0[0], bs[:, 0].std(), len(s), "u-Anfang des Frontlaufs (P2)"), u_bis=wert(b0[1], bs[:, 1].std(), len(s), "u-Ende des Frontlaufs (P98)"),
                      laenge=wert(b0[1] - b0[0], (bs[:, 1] - bs[:, 0]).std(), len(s), "u-Laenge des Frontlaufs")))
luecken = [dict(u_von=round(verm[i][1], 2), u_bis=round(verm[i + 1][0], 2), breite=round(verm[i + 1][0] - verm[i][1], 2)) for i in range(len(verm) - 1)]
# 6. Bruestung
if so is not None:
    g = so[2]; tp = inn & (np.abs(Z - so[0]) <= 0.06); nt = N[tp]; p = np.percentile(nt, [5, 95]); nt_full = (U >= bu0) & (U <= bu1) & (np.abs(Z - so[0]) <= 0.06) & (N >= nw - 0.3) & (N <= nf + 0.4); nn = N[nt_full]
    dick = lambda ix: np.subtract(*np.percentile(nn[ix][::-1][:0] if False else nn[ix], [95, 5]))
    d0 = dick(np.arange(len(nn))); d_s = boot(dick, len(nn)); k_ob = int(len(nn))
    zin = (Z >= zu + 0.2) & (Z <= zo - 0.2); dens = lambda lo, hi: float(((U >= bu0) & (U <= bu1) & (N >= lo) & (N < hi) & zin).sum()) / (hi - lo)
    d_in = dens(nw + 0.15, nf - 0.25); d_fr = dens(nf - 0.15, nf + 0.15)
    bru = dict(oberseite_n_spanne_P5_P95=wert(d0, d_s, k_ob, "n-Spanne der Oberseitenpunkte = OBERGRENZE der Bruestungs-/Plattendicke (Oberseite kann Wand dahinter einschliessen)"),
               oberseite_n_von=wert(np.percentile(nn, 5), 0.0, k_ob, "n-Anfang Oberseite (P5)"), oberseite_n_bis=wert(np.percentile(nn, 95), 0.0, k_ob, "n-Ende Oberseite (P95)"),
               dichte_innen_zu_front=wert(d_in / d_fr if d_fr else np.nan, 0.0, int(zin.sum()), "Punktdichte (je m n) Inneres/Front im Frontband; ~0 = Front duenn/hohl ohne Fuellung, sigma nicht bestimmt"))
else: bru = dict(hinweis="Oberseite nicht bestimmbar")
fzo = zo - zu
out = dict(achse_n=[round(float(n[0]), 4), round(float(n[1]), 4)], wandebene_n=wert(nw, nw_s, len(xw), "Wandebene n (Gipfel Band z %.1f..%.1f, u %.0f..%.0f)" % (wz0, wz1, wu0, wu1)),
    front_n=wert(nf, nf_s, len(xf2), "n der Balkon-/Bruestungsfront"), auskragung=wert(nf - nw, np.hypot(nf_s, nw_s), len(xf2), "Auskragung zur Wandebene = n_front - n_wand"),
    front_unterkante_z=wert(zu, ks[:, 0].std(), len(zf), "Unterkante der senkrechten Front", f"(Block >= {a.anteil:.2f} x mittlere Dichte/5 cm)"),
    front_oberkante_z=wert(zo, ks[:, 1].std(), len(zf), "Oberkante der Front (= Bruestungsoberkante)"),
    front_hoehe=wert(fzo, np.hypot(ks[:, 0].std(), ks[:, 1].std()), len(zf), "Hoehe der senkrechten Front"),
    unterseite_z=zw(su, "z der Unterseite (Soffit, Gipfel zwischen Wand und Front)"), oberseite_z=zw(so, "z der Oberseite/Bruestungsoberkante (Gipfel zwischen Wand und Front)"),
    bruestung=bru, u_laeufe=teile, n_laeufe_wolke=len(verm), laeufe_als_erker_verworfen=verw, luecken_zwischen_laeufen=luecken,
    band_art=("durchgehend (ein Lauf)" if len(verm) == 1 else ("getrennte Platten/Luecken" if len(verm) > 1 else "kein Lauf")),
    hinweis="Zaehlung/Plattenzahl nur Konsistenz (Regel 9: Zaehlung = Foto). Wolke blind fuer Verdeckung: Lauf-Enden an Erkern sind Verdeckung/Seitenflaeche, keine Bauteilfuge. Unterseite oft nur schraeg gesehen -> Untergrenze unsicher.",
    foto_hinweis=a.foto_hinweis)
json.dump(out, open(a.aus, "w"), indent=1, ensure_ascii=False)
v = lambda d: f"{d['wert']}+-{d.get('sigma')}" if d.get('wert') is not None else "n/a"
print(f"Wand n={v(out['wandebene_n'])} Front n={v(out['front_n'])} Ausk={v(out['auskragung'])} Front z {v(out['front_unterkante_z'])} .. {v(out['front_oberkante_z'])}  Soffit {v(out['unterseite_z'])} Oberseite {v(out['oberseite_z'])}")
print("Laeufe:", [(t['u_von']['wert'], t['u_bis']['wert']) for t in teile], "Luecken:", luecken, "Art:", out['band_art']); print("Bruestung:", {k: (d.get('wert') if isinstance(d, dict) else d) for k, d in bru.items()})
