#!/usr/bin/env python3
"""lot_wandneigung.py - LOT-TOR "Wandneigung": kippt das ausgerichtete Modell als Ganzes? (22.11.2026)

WARUM (Kettenlauf schwabentor-1122n, alle Lage-Tore gruen, Modell gebaut): die Ausrichtung hatte einen LOTFEHLER von ~3 Grad, den kein Tor sah - GPS, Grundriss,
Lageproben pruefen Drehung um das Lot, Massstab und Versatz, aber nicht die Kippung. Folgen: Fassaden-Tiefensweep 'nicht belastbar' (Guete 31 % < 35 %), Bilderker
fehlt, Falschfenster. An der dichten Wolke im Modellrahmen sichtbar: die Waende mit Normale -y und +y lehnen in DIESELBE Raumrichtung (-2,9 / +2,8 cm/m), die Wand
mit Normale +x -4,9 cm/m - das ist ein Lotfehler (Spitze wandert nach -x/+y), keine Verjuengung.

MESSUNG (je Wand des Zielgebaeudes): Waende = WallSurface-Flaechen des LoD2-Zielgebaeudes (objekt.json lod2.id), koplanare zusammengefasst, >= WAND_MIN_M lang,
Normale nach aussen. Wolkenpunkte im Streifen um die Wandebene (Raender WAND_RAND weg), je 1-m-Hoehenband der Gipfel der Abstandsverteilung (Wandmodus) und der
Median der Punkte +-0,1 m darum; Neigung dw/dz = Theil-Sen ueber Bandpaare >= 4 m Hoehenabstand (robust gegen Gesimse/Vorspruenge), Unsicherheit per Bootstrap
ueber die Baender. Vorzeichen: minus = lehnt nach INNEN. Bis 1 m unter die LoD2-Oberkante der Wand (darueber Dach).
TRENNUNG Kippung / Form: Kippt der Rahmen um den Vektor t (cm/m, Richtung, in die die Spitze wandert), misst die Wand mit Aussennormale n die Neigung t.n + a;
a = gemeinsamer Anzug (Verjuengung, echte Form, alle Waende gleich nach innen). Gewichtete kleinste Quadrate fuer (tx, ty, a); trennbar nur, wenn die Normalen
gegenueberliegen (Rang 3). Sonst (z. B. zwei Waende ueber Eck) a = 0 gesetzt (ANNAHME: Wand lotrecht) und so im Bericht vermerkt.
URTEIL: rc 0 = lotrecht (|t| <= KIPP_GRENZE und 2 sigma <= KIPP_GRENZE), rc 3 = ROT (|t| > KIPP_GRENZE und > 2 sigma), rc 4 = kein Urteil (weniger als zwei messbare
Waende mit nicht parallelen Normalen, Messung zu unsicher, Wolke fehlt, kein LoD2-Ziel).
GRENZEN DER MESSUNG: Streifen +-2,5 m um die LoD2-Wand -> bis ~7 cm/m Kippung ueber 35 m sicher im Fenster; der Wandmodus je Band ist keine Auswahl auf der
abhaengigen Groesse wie BS150 (z-Fenster-Ebenenfit), groessere Kippungen schneiden aber den Streifen an (dann Urteil ROT bleibt richtig, Betrag zu klein).
GRENZE KIPP_GRENZE = 2,0 cm/m (1,15 Grad) - BELEG (dichte Wolken im Modellrahmen, 22.11.2026, siehe tools/versuche/lot_runde/):
  schwabentor-1120 (gute Lage): 1,0 +- 0,6 cm/m (3 Waende, Anzug -0,2 getrennt);  schwabentor-1122n (Lotfehler, Tiefensweep 31 %): 5,6 +- 0,3 cm/m Richtung 153 Grad.
  Grenze dazwischen mit Abstand zu beiden (1120 + 2 sigma = 2,1; 1122n - 2 sigma = 5,0); physikalisch: 2 cm/m ueber 20 m Wandhoehe = 0,4 m Versatz oben.
  Unabhaengige Gegenproben derselben Staende: Fluchtpunkt-Lot gegen die Modell-Hochachse 0,3 / 5,0 cm/m (Lot-Runde), Kamerahoehe ueber DGM1 (kamera_gefaelle) 1,4 / 5,7 cm/m.
  Kontrollen: kaufhaus_gk2 1,8 +- 4,3 und martinstor_gk3 6,2 +- 4,4 cm/m (nur 2 kurze/teilweise Waende) -> kein Urteil (2 sigma > Grenze), richtig so.
Aufruf: lot_wandneigung.py <objekt.json> --wolke punkte_modell.npy [--aus audit/lot_wandneigung.json]. Exit 0 / 3 / 4 wie oben.
Funktionen: waende(obj) -> Wandliste; neigung(X, wand) -> dict; kippvektor(messungen) -> dict; pruefen(X, obj) -> Bericht (Kette, Pruefstand, Lot-Vergleich)."""
import os, sys, json, math, argparse
import numpy as np

T = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, T)

WAND_MIN_M = 4.0        # kuerzere Wandstuecke tragen die Neigung nicht (Theil-Sen ueber wenige Punkte je Band)
WAND_RAND = 0.15        # Anteil an jedem Wandende weg (Ecken: Nachbarwand, Strebepfeiler)
STREIFEN = (-2.5, 2.5)  # m um die LoD2-Wandebene (Lage +-1-2 m genau; der Wandmodus sucht die Wand darin)
BAND_MIN_PUNKTE = 200   # Punkte je 1-m-Band, sonst Band leer
MIN_BAENDER, MIN_SPANNE = 6, 8.0   # messbare Wand: >= 6 Baender ueber >= 8 m Hoehe
PAAR_MIN_DZ = 4.0
KIPP_GRENZE = 2.0       # cm/m (BELEG im Kopf)
SIGMA_MIN = 0.3         # cm/m Untergrenze der Bootstrap-Streuung (Wandrauhigkeit, Bandraster)
PARALLEL_SIN = math.sin(math.radians(30))


def _rahmen(obj):
    r = obj["rahmen"]; return np.array(r["mitte_utm"], float), np.array(r["xhat_utm"], float), np.array(r["yhat_utm"], float), float(r["gelaende"])


def waende(obj, min_m=WAND_MIN_M):
    """Waende des LoD2-Zielgebaeudes im Modellrahmen: [dict(o (2), d (2, Einheit laengs), n (2, aussen), u (u0, u1), z_oben, laenge)]."""
    import lod2_gebaeude as LG
    c0, xh, yh, gel = _rahmen(obj); gid = obj.get("lod2", {}).get("id"); gml = obj.get("lod2", {}).get("gml")
    if not gid or not gml or not os.path.exists(gml): return []
    lok = lambda P: np.c_[(P[:, :2] - c0) @ xh, (P[:, :2] - c0) @ yh, P[:, 2] - gel]
    flaechen = []; alle = []
    for meta, polys in LG.extract(gml, center=tuple(c0), radius=80.0):
        if meta.get("id") != gid: continue
        for t, P in polys:
            Q = lok(np.asarray(P, float)); alle.append(Q)
            if t == "WallSurface": flaechen.append(Q)
    if not flaechen: return []
    mitte = np.vstack(alle)[:, :2].mean(0); roh = []
    for Q in flaechen:
        xy = Q[:, :2]; c = xy.mean(0); _, _, vt = np.linalg.svd(xy - c, full_matrices=False); d = vt[0]; n = np.array([d[1], -d[0]])
        if (c - mitte) @ n < 0: n = -n
        u = (xy - c) @ d; roh.append(dict(c=c, d=d, n=n, u0=float(u.min()), u1=float(u.max()), z_oben=float(Q[:, 2].max())))
    # koplanare Flaechen zusammenfassen (gleiche Normale < 5 Grad, Ebenenabstand < 0,3 m, Laengsueberlappung oder Luecke < 1 m)
    gruppen = []
    for r in sorted(roh, key=lambda r: -(r["u1"] - r["u0"])):
        for g in gruppen:
            if g["n"] @ r["n"] < math.cos(math.radians(5)) or abs((r["c"] - g["o"]) @ g["n"]) > 0.3: continue
            a0, a1 = sorted(((r["c"] - g["o"]) @ g["d"] + r["u0"] * (r["d"] @ g["d"]), (r["c"] - g["o"]) @ g["d"] + r["u1"] * (r["d"] @ g["d"])))
            if a0 > g["u"][1] + 1.0 or a1 < g["u"][0] - 1.0: continue
            g["u"] = [min(g["u"][0], a0), max(g["u"][1], a1)]; g["z_oben"] = max(g["z_oben"], r["z_oben"]); break
        else: gruppen.append(dict(o=r["c"], d=r["d"], n=r["n"], u=[r["u0"], r["u1"]], z_oben=r["z_oben"]))
    W = []
    for i, g in enumerate(gruppen):
        L = g["u"][1] - g["u"][0]
        if L >= min_m: W.append(dict(id=f"w{i:02d}", o=g["o"].tolist(), d=g["d"].tolist(), n=g["n"].tolist(), u=[float(g["u"][0]), float(g["u"][1])], z_oben=float(g["z_oben"]), laenge=float(L)))
    return W


def _theil_sen(zs, ws):
    s = [(ws[j] - ws[k]) / (zs[j] - zs[k]) for j in range(len(zs)) for k in range(j) if zs[j] - zs[k] >= PAAR_MIN_DZ]
    return float(np.median(s)) if s else float("nan")


def neigung(X, wand, n_boot=200, seed=0):
    """Neigung einer Wand aus Wolkenpunkten X (n x 3, Modellrahmen) -> dict(id, n, neigung_cm_m (minus = nach innen), sigma_cm_m, baender, z (von, bis), messbar)."""
    o = np.array(wand["o"]); d = np.array(wand["d"]); n = np.array(wand["n"]); u0, u1 = wand["u"]; L = u1 - u0
    u = (X[:, :2] - o) @ d; w = (X[:, :2] - o) @ n; z = X[:, 2]
    m = (u > u0 + WAND_RAND * L) & (u < u1 - WAND_RAND * L) & (w > STREIFEN[0]) & (w < STREIFEN[1]) & (z > 1.0) & (z < wand["z_oben"] - 1.0)
    wm_, zm_ = w[m], z[m]; zs, ws = [], []
    for zb in np.arange(1.0, wand["z_oben"] - 1.0, 1.0):
        r = (zm_ >= zb) & (zm_ < zb + 1)
        if r.sum() < BAND_MIN_PUNKTE: continue
        h, e = np.histogram(wm_[r], bins=np.arange(STREIFEN[0], STREIFEN[1] + 1e-9, 0.05)); mo = e[np.argmax(h)] + 0.025
        sel = np.abs(wm_[r] - mo) < 0.1; zs.append(zb + 0.5); ws.append(float(np.median(wm_[r][sel])))
    zs, ws = np.array(zs), np.array(ws)
    erg = dict(id=wand["id"], n=[round(float(x), 3) for x in n], laenge_m=round(float(L), 1), baender=int(len(zs)), z=[float(zs.min()), float(zs.max())] if len(zs) else None, messbar=False)
    if len(zs) < MIN_BAENDER or zs.max() - zs.min() < MIN_SPANNE: return erg
    sl = _theil_sen(zs, ws); rng = np.random.default_rng(seed); bs = []
    for _ in range(n_boot):
        i = rng.integers(0, len(zs), len(zs)); b = _theil_sen(zs[i], ws[i])
        if np.isfinite(b): bs.append(b)
    sig = max(float(np.std(bs)) * 100 if bs else float("nan"), SIGMA_MIN)
    erg.update(messbar=bool(np.isfinite(sl)), neigung_cm_m=round(sl * 100, 2), sigma_cm_m=round(sig, 2), w_unten=round(float(np.median(ws[:3])), 2), w_oben=round(float(np.median(ws[-3:])), 2))
    return erg


def kippvektor(mess, grenze=KIPP_GRENZE):
    """Gemeinsamer Kippvektor t (cm/m, Modell-x/y; Richtung, in die die Spitze wandert) + Anzug a aus den messbaren Waenden. -> dict(urteil, rc, t, betrag, richtung_grad, ...)."""
    M = [m for m in mess if m.get("messbar")]
    if not M: return dict(rc=4, urteil="kein Urteil", grund="keine messbare Wand")
    N = np.array([m["n"] for m in M], float); s = np.array([m["neigung_cm_m"] for m in M], float); sg = np.array([m["sigma_cm_m"] for m in M], float)
    quer = max((abs(N[i, 0] * N[j, 1] - N[i, 1] * N[j, 0]) for i in range(len(N)) for j in range(i)), default=0.0)
    if quer < PARALLEL_SIN: return dict(rc=4, urteil="kein Urteil", grund=f"nur {len(M)} messbare Wand/Waende mit parallelen Normalen - Kippung nur in einer Richtung bestimmt", waende=len(M))
    A = np.c_[N, np.ones(len(N))] / sg[:, None]; b = s / sg
    sv = np.linalg.svd(A, compute_uv=False); mit_anzug = len(M) >= 3 and sv[-1] / sv[0] > 0.2
    if not mit_anzug: A = A[:, :2]
    x, *_ = np.linalg.lstsq(A, b, rcond=None); C = np.linalg.inv(A.T @ A)
    rest = s - (np.c_[N, np.ones(len(N))][:, :len(x)] @ x)
    if len(M) > len(x):                                                                  # Streuung aus den Resten, wenn ueberbestimmt (nicht kleiner als die Bootstrap-Streuung)
        C = C * max(1.0, float((rest / sg) @ (rest / sg)) / (len(M) - len(x)))
    t = x[:2]; Ct = C[:2, :2]; betr = float(np.hypot(*t)); sig = float(math.sqrt(max(t @ Ct @ t / max(betr ** 2, 1e-12), 0))) if betr > 0 else float(math.sqrt(np.trace(Ct) / 2))
    rot = betr > grenze and betr > 2 * sig; gut = betr <= grenze and 2 * sig <= grenze
    rc = 3 if rot else 0 if gut else 4
    return dict(rc=rc, urteil="ROT: Modell kippt (Lotfehler)" if rot else "lotrecht" if gut else "kein Urteil (Messung zu unsicher: 2 sigma > Grenze)",t_cm_m=[round(float(t[0]), 2), round(float(t[1]), 2)], betrag_cm_m=round(betr, 2),
                betrag_grad=round(math.degrees(math.atan(betr / 100)), 2), sigma_cm_m=round(sig, 2), richtung_grad=round(math.degrees(math.atan2(t[1], t[0])), 1),
                anzug_cm_m=round(float(x[2]), 2) if mit_anzug else None, anzug="getrennt" if mit_anzug else "ANNAHME a=0 (Normalen nicht gegenueber)",
                reste_cm_m=[round(float(r_), 2) for r_ in rest], waende=len(M), grenze_cm_m=grenze)


def pruefen(X, obj, grenze=KIPP_GRENZE, wand_liste=None):
    W = waende(obj) if wand_liste is None else wand_liste
    if not W: return dict(rc=4, urteil="kein Urteil", grund="kein LoD2-Zielgebaeude / keine Wand >= %.0f m" % WAND_MIN_M, messungen=[])
    X = np.asarray(X)[:, :3]; c = np.vstack([np.array(w["o"]) for w in W]).mean(0); r = max(w["laenge"] for w in W) + 10
    X = np.asarray(X[np.hypot(X[:, 0] - c[0], X[:, 1] - c[1]) < r], float)
    mess = [neigung(X, w) for w in W]; k = kippvektor(mess, grenze); k["messungen"] = mess; return k


def kamera_gefaelle(obj, au_pfad, max_r=45.0, hoehe=(0.5, 3.5)):
    """GEGENPROBE ohne Wolke (Lot-Runde 22.11.2026): Handkameras stehen ueberall gleich hoch ueber dem Boden. Ebene durch (Kamerahoehe - DGM1 darunter) der Strassenkameras
    (0,5-3,5 m ueber DGM1, < max_r m von der Mitte, robust) -> Gefaelle g; das Modell kippt dann um -g (Spitze weg von der hoeheren Seite). Gemessen: 1120 1,4 cm/m
    (Waende 1,0), 1122n 5,7 cm/m Richtung 156 (Waende 5,6 Richtung 153) - unabhaengig von dichter Wolke und Fotos. Nur Bericht (Handkameras auf Treppen/Bussen moeglich).
    -> dict(kipp_cm_m, betrag_cm_m, richtung_grad, n) oder dict(grund)."""
    import lage_proben as LP
    AU = json.load(open(au_pfad)); S = np.array([k["standort"] for k in (AU.get("kameras") or {}).values() if k.get("standort") is not None], float)
    if len(S) < 20: return dict(grund=f"nur {len(S)} Kamerastandorte")
    S = S[np.hypot(S[:, 0], S[:, 1]) < max_r]; g = LP.raster(obj, S[:, :2], "dgm1"); ok = np.isfinite(g); S, g = S[ok], g[ok]; h = S[:, 2] - g
    m = (h > hoehe[0]) & (h < hoehe[1]); xy = S[m, :2]; z = h[m]
    if m.sum() < 20 or np.ptp(xy[:, 0]) < 10 or np.ptp(xy[:, 1]) < 10: return dict(grund=f"zu wenige/zu eng stehende Strassenkameras ({int(m.sum())})")
    A = np.c_[xy, np.ones(len(z))]; w = np.ones(len(z))
    for _ in range(5):
        c = np.linalg.lstsq(A * w[:, None], z * w, rcond=None)[0]; r = z - A @ c; s = 1.4826 * np.median(np.abs(r)) + 1e-6; w = 1 / np.maximum(1, np.abs(r) / (2 * s))
    k = -100 * c[:2]
    return dict(kipp_cm_m=[round(float(k[0]), 2), round(float(k[1]), 2)], betrag_cm_m=round(float(np.hypot(*k)), 2), richtung_grad=round(math.degrees(math.atan2(k[1], k[0])), 1),
                n=int(m.sum()), hoehe_median_m=round(float(np.median(z)), 2))


def bericht_zeile(k):
    if k.get("rc") == 4: return f"Lot-Tor Wandneigung: kein Urteil ({k.get('grund')})"
    return (f"Lot-Tor Wandneigung: {k['urteil']} - gemeinsame Kippung {k['betrag_cm_m']:.1f} cm/m ({k['betrag_grad']:.2f} Grad, +-{k['sigma_cm_m']:.1f}) Richtung {k['richtung_grad']:.0f} Grad "
            f"(Modell-x = 0), Grenze {k['grenze_cm_m']:.1f} cm/m; Anzug {k['anzug_cm_m'] if k['anzug_cm_m'] is not None else k['anzug']}; Waende "
            + ", ".join(f"{m['id']} n({m['n'][0]:+.2f},{m['n'][1]:+.2f}) {m['neigung_cm_m']:+.1f}" for m in k["messungen"] if m.get("messbar")))


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("--wolke", required=True); ap.add_argument("--aus", default=""); ap.add_argument("--grenze", type=float, default=KIPP_GRENZE)
    ap.add_argument("--ausrichtung", default="", help="SFM-AUSRICHTUNG-*.json: Gegenprobe Kamerahoehe ueber DGM1 (nur Bericht)")
    a = ap.parse_args(argv); obj = json.load(open(a.objekt)); od = os.path.dirname(os.path.abspath(a.objekt))
    aus = a.aus or os.path.join(od, "audit", "lot_wandneigung.json")
    if not os.path.isfile(a.wolke): k = dict(rc=4, urteil="kein Urteil", grund=f"Wolke fehlt {a.wolke}", messungen=[])
    else: k = pruefen(np.load(a.wolke, mmap_mode="r"), obj, a.grenze)
    k.update(werkzeug="lot_wandneigung.py", wolke=a.wolke); print(bericht_zeile(k), flush=True)
    if a.ausrichtung and os.path.isfile(a.ausrichtung):
        try:
            k["kamera_gefaelle"] = kg = kamera_gefaelle(obj, a.ausrichtung)
            if kg.get("kipp_cm_m"): print(f"Gegenprobe Kamerahoehe ueber DGM1 ({kg['n']} Strassenkameras): Kippung {kg['betrag_cm_m']:.1f} cm/m Richtung {kg['richtung_grad']:.0f} Grad", flush=True)
            else: print("Gegenprobe Kamerahoehe ueber DGM1: kein Wert -", kg.get("grund"), flush=True)
        except Exception as e: print("Gegenprobe Kamerahoehe nicht moeglich:", type(e).__name__, e, flush=True)
    os.makedirs(os.path.dirname(aus), exist_ok=True); json.dump(k, open(aus, "w"), indent=1, ensure_ascii=False)
    return int(k["rc"])


if __name__ == "__main__":
    sys.exit(main())
