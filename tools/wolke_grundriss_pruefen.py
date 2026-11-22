#!/usr/bin/env python3
"""wolke_grundriss_pruefen.py - GENERISCH: Dichte Wolke (Modellrahmen) gegen die amtlichen LoD2-Grundrisse der Umgebung pruefen.

Lehre Schwabentor 2026-11-14: Ein ganzes Haus (Fluegel, 205 000 Punkte) lag in der Wolke AUF DER STRASSE, ausserhalb jedes
LoD2-Gebaeudes. Es wurde einen Tag lang per Augenmass, Farbtests und Reglern 'verschoben', statt einmal die Grundrisse darueber
zu legen. Ursachen: (1) Kamerakranz nur auf einer Halbebene (Luecke > 100 Grad, tools/kamera_abdeckung.py), (2) Turm von
mehreren Seiten aehnlich -> Gruppen/Zusatzfotos auf der falschen Seite registriert, (3) LoD2-Ausrichtung knapp
(beste 22,2 % Inlier gegen zweitbeste 19,4 %), niemand hat den Abstand gewertet.

Was das Werkzeug prueft (alles im Modellrahmen = objekt.json 'rahmen'):
  A  STRASSE: Anteil der Wandpunkte (Hoehe 1,5..9 m ueber Gelaende) ausserhalb aller LoD2-Grundrisse und > --wandabstand
     von jeder LoD2-Wand. Zusammenhaengende Haufen (1-m-Raster) werden mit Lage, Groesse und Punktzahl gelistet.
     Ein Haufen > --haufen Punkte auf der Strasse = WARNUNG (falsch verortetes Teilnetz oder Baum/Auto - am Foto klaeren).
  B  EINDEUTIGKEIT: Wandpunkte per FFT-Korrelation gegen die LoD2-Wandlinien, Drehung 0..359 Grad, mit und ohne Spiegelung.
     Verglichen werden die aktuelle Lage (Identitaet) und die beste Alternative (> 15 Grad weg oder gespiegelt).
     Alternative besser als aktuelle Lage, oder Abstand < --abstand (relativ) = HINWEIS (kein Tor: warnt auch am richtig liegenden Kaufhaus).
  C  TEILE OHNE WOLKE (Lehre Schwabentor 2026-11-14, Treppentuermchen): je LoD2-GroundSurface des Zielgebaeudes (objekt.json lod2.id) Anteil
     der eigenen Randpunkte (> 0,6 m von anderen Grundrissen) mit Wolke (Wandband, 0,4 m). Fehlt die Wolke, wird gesucht, ob die
     unerklaerten Punkte (ausserhalb der Ziel-Grundrisse) gedreht um die Mitte des Hauptteils (0..359 Grad, Versatz +-1 m) den Rand fuellen
     und das Innere frei lassen: F1 aus Randdeckung (>= 4 Punkte je Randprobe im 0,2-m-Fenster; ohne Dichte Schein-Treffer 100 Grad aus Streupunkten) und Anteil Punkte
     auf dem Rand statt innen (Toleranz 0,2 m, GPU). Drehzentrum = Flaechenmitte
     des Hauptteils (Eckpunktmittel lag 1,7 m daneben -> 180-Grad-Kreis 3 m verfehlt); reine Belegung gab Schein-Treffer 105 Grad / 97 %.
     Das Tuermchen lag 180 Grad punktgespiegelt an der Gegenecke, dicht an der Turmwand -> A sah es nicht (Wandabstand < 1,5 m).
     HINWEIS C (kein Tor): gedrehte Form F1 >= 0,6 und deckt >= 40 Prozentpunkte mehr Rand als der Ist-Zustand. Kontrolle 2026-11-14:
     Schwabentor-Tuermchen 174 Grad F1 0,92 (richtig), aber Kaufhaus (liegt richtig) Teil 1 15 m2 ungesehen 284 Grad F1 0,76 -> gerade Waende
     fuellen kleine Rechtecke beliebig. Rundformen sind aussagekraeftig, Rechtecke nicht. = falsch gedrehtes Teilnetz. Nur fehlende Deckung = Hinweis.
     Rueckgabe: 0 ok, 3 = Haufen auf der Strasse (Tor A).
  Geklaerte Haufen (objekt.json grundriss_haufen_geklaert) mit "punkte" gelten nur bis 2x dieser Punktzahl (22.11.2026, schwabentor-1122: die
  falsche Lage legte einen 7,9x groesseren Haufen versetzter Waende 0,5 m neben den geklaerten Platz-Haufen von schwabentor-1120).
  22.11.2026 Kontrolle 1122 (Lage +8 Grad / x1,089 neben dem GPS, Rest 3,9 m; GPS-Tor selbst rc 3): A schlaegt zu Recht an - gleiche Kette 1120
  (GPS-Fit -0,03 Grad / x0,994) besteht, Turmtuermchen 88 % gedeckt (1122: 0 %). B/C bleiben Hinweise; kein GPS-Freibrief fuer A, weil Telefon-GPS
  (Rest 4 m) einen Versatz von 2-4 m nicht ausschliessen kann, A ihn aber sieht.
Quellen-Blindheit: LoD2 kennt keine Erker, Arkaden, Vordaecher, Baeume, Autos - Punkte dort landen in A als 'Strasse'.
Deshalb wird nur gewarnt und gelistet; die Entscheidung faellt am Foto (tools/foto_diff.py, Ueberlagerung).

  /media/oem/scan/venv-seg/bin/python -I tools/wolke_grundriss_pruefen.py modelle/<objekt>/objekt.json --wolke <punkte_modell.npy> [--radius 60]
Ausgabe: modelle/<objekt>/audit/wolke_grundriss.json und audit/wolke_grundriss.png; Exit 0 = ok, 3 = Strasse-Warnung, 4 = Lage nicht eindeutig (4 hat Vorrang).
"""
import sys, os, json, argparse, hashlib, pickle
import numpy as np
from scipy import ndimage
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lod2_gebaeude as LG

CACHE = "/media/oem/scan/rc-park_daten/_cache"


def grundrisse(obj, radius):
    r = obj["rahmen"]; m0 = np.array(r["mitte_utm"], float); xh = np.array(r["xhat_utm"], float); yh = np.array(r["yhat_utm"], float)
    gml = obj.get("_gml") or obj.get("lod2", {}).get("gml")
    if not gml or not os.path.exists(gml):                                   # Kachel per UTM suchen (LGL: LoD2_32_<E km>_<N km>_1_BW.gml)
        import glob
        hit = glob.glob(f"/media/oem/scan/rc-park_daten/_geo/**/LoD2_32_{int(m0[0] // 1000)}_{int(m0[1] // 1000)}_1_BW.gml", recursive=True)
        if not hit: sys.exit(f"LoD2-GML fehlt ({gml}) und keine Kachel unter _geo gefunden - --gml angeben")
        print(f"LoD2: {gml} fehlt, nehme Kachel {hit[0]}"); gml = hit[0]
    st = os.stat(gml)
    k = hashlib.sha1(f"grund|{gml}|{st.st_size}|{int(st.st_mtime)}|{m0.tolist()}|{radius}".encode()).hexdigest()[:16]
    cp = os.path.join(CACHE, f"lod2_grund_{k}.pkl")
    if os.path.exists(cp):
        B = pickle.load(open(cp, "rb"))
    else:
        B = []
        for meta, polys in LG.extract(gml, center=tuple(m0), radius=radius):
            B.append(dict(id=meta["id"], ground=[P[:, :2] for t, P in polys if t == "GroundSurface"]))
        os.makedirs(CACHE, exist_ok=True); pickle.dump(B, open(cp, "wb"))
    tm = lambda U: np.c_[(U - m0) @ xh, (U - m0) @ yh]
    return [dict(id=b["id"], ground=[tm(g) for g in b["ground"]]) for b in B]


def flaechenmitte(g):
    x, y = g[:, 0], g[:, 1]; c = x * np.roll(y, -1) - np.roll(x, -1) * y; A = c.sum() / 2
    return np.array([((x + np.roll(x, -1)) * c).sum(), ((y + np.roll(y, -1)) * c).sum()]) / (6 * A), abs(A)


def rand(g, d=0.1):
    q = np.vstack([g, g[:1]])
    return np.vstack([p0 + np.linspace(0, 1, max(2, int(np.linalg.norm(p1 - p0) / d)), endpoint=False)[:, None] * (p1 - p0) for p0, p1 in zip(q[:-1], q[1:])])


def teile_pruefen(zp, andere_g, Q, min_abstand, z0, Path, tol=0.2, schritt_w=2, versatz=1.5, schritt_v=0.25, n_max=150000, min_dichte=4):
    """Test C je Teil: eigener Rand (> 0,6 m von anderen Grundrissen) - Deckung jetzt; dann bester starrer Kandidat (Drehung um die
    Flaechenmitte des Hauptteils, Versatz +-versatz) der UNERKLAERTEN Punkte: F1 aus Randdeckung (recall) und Anteil Punkte auf dem Rand
    statt innen (precision). Hohes F1 nur bei echter Wandform (Kreisbogen), nicht bei dichten Fremdflaechen."""
    import torch
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    mit = [flaechenmitte(g) for g in zp]; hi = int(np.argmax([m[1] for m in mit])); hc = mit[hi][0]
    alle_r = np.vstack([rand(g) for g in zp]); zin = np.zeros(len(Q), bool)
    for g in zp: zin |= Path(g).contains_points(Q)
    unerkl = Q[~zin & (min_abstand(z0(Q), z0(alle_r)) > 0.5)]
    andere = np.vstack([rand(g) for g in andere_g]) if andere_g else np.zeros((0, 2))
    out = []
    for i, g in enumerate(zp):
        S = rand(g); eig = np.ones(len(S), bool)
        for j, h in enumerate(zp):
            if j != i: eig &= min_abstand(z0(S), z0(rand(h))) > 0.6
        if len(andere): eig &= min_abstand(z0(S), z0(andere)) > 0.6
        S = S[eig]
        if len(S) < 20: continue
        # lokales Raster um den Teil: Rand-Band (eigener Rand, tol) und Innen (> tol vom Rand) - 0,05 m
        R = 0.05; lo = g.min(0) - 0.6; hi_ = g.max(0) + 0.6; nx, ny = np.ceil((hi_ - lo) / R).astype(int)
        gx, gy = np.meshgrid(lo[0] + (np.arange(nx) + .5) * R, lo[1] + (np.arange(ny) + .5) * R); C = np.c_[gx.ravel(), gy.ravel()]
        dS = min_abstand(z0(C), z0(S)); dR = min_abstand(z0(C), z0(rand(g)))
        band = torch.as_tensor((dS < tol).astype(np.float32), device=dev)
        innen = torch.as_tensor((Path(g).contains_points(C) & (dR > tol)).astype(np.float32), device=dev)
        Sk = torch.as_tensor(np.floor((S - lo) / R).astype(np.int64), device=dev); Sidx = Sk[:, 1] * nx + Sk[:, 0]
        r_ = max(1, int(round(tol / R)))
        def dichte_deckung(PP, f=1.0):                                          # Anteil Randproben mit >= min_dichte*f Punkten im tol-Fenster
            kk = np.floor((PP - lo) / R).astype(int); m = (kk[:, 0] >= 0) & (kk[:, 0] < nx) & (kk[:, 1] >= 0) & (kk[:, 1] < ny)
            o_ = torch.zeros(nx * ny, device=dev); o_.index_add_(0, torch.as_tensor(kk[m, 1] * nx + kk[m, 0], device=dev), torch.ones(int(m.sum()), device=dev))
            o_ = torch.nn.functional.avg_pool2d(o_.view(1, 1, ny, nx), 2 * r_ + 1, 1, r_, count_include_pad=False) * (2 * r_ + 1) ** 2
            return float((o_.view(-1)[Sidx] >= min_dichte * f).float().mean())
        jetzt = dichte_deckung(Q)                                               # Ist-Zustand, gleiche Dichteschwelle wie die Kandidaten
        # nur Punkte, die nach Drehung um hc in die Naehe kommen koennen (Abstand zu hc bleibt erhalten)
        rr = np.hypot(*(g - hc).T); dq = np.hypot(*(unerkl - hc).T); P = unerkl[(dq > rr.min() - versatz - 1) & (dq < rr.max() + versatz + 1)]
        fak = 1.0
        if len(P) > n_max: fak = n_max / len(P); P = P[np.random.default_rng(0).choice(len(P), n_max, replace=False)]   # Schwelle mit ausduennen
        best = dict(f1=0.0)
        if len(P):
            Pt = torch.as_tensor(P - hc, dtype=torch.float32, device=dev)
            vs = np.arange(-versatz, versatz + 1e-6, schritt_v); V = torch.as_tensor(np.array([[a, b] for a in vs for b in vs]), dtype=torch.float32, device=dev)
            hct = torch.as_tensor(hc, dtype=torch.float32, device=dev); lot = torch.as_tensor(lo, dtype=torch.float32, device=dev)
            # Randpunkte duerfen nicht von Nahpunkten (Hauptteil) gedeckt werden: nur gedrehte Punkte zaehlen
            for w in range(0, 360, schritt_w):
                if min(w, 360 - w) <= 15: continue
                t = np.radians(w); Rm = torch.as_tensor([[np.cos(t), -np.sin(t)], [np.sin(t), np.cos(t)]], dtype=torch.float32, device=dev)
                Y = Pt @ Rm.T + hct                                                     # (n,2)
                Y = Y[None] + V[:, None]                                               # (nv,n,2)
                k = torch.floor((Y - lot) / R).long(); ok = (k[..., 0] >= 0) & (k[..., 0] < nx) & (k[..., 1] >= 0) & (k[..., 1] < ny)
                lin = (k[..., 1] * nx + k[..., 0]).clamp(0, nx * ny - 1)
                auf = (band[lin] * ok).sum(1); inn = (innen[lin] * ok).sum(1)
                prec = auf / (auf + inn + 1e-6)
                # recall: Randproben mit mind. 1 Punkt in tol -> Belegungsraster je Versatz
                occ = torch.zeros((len(V), nx * ny), device=dev); occ.scatter_add_(1, lin, ok.float())
                occ = occ.view(len(V), 1, ny, nx); r_ = max(1, int(round(tol / R)))
                occ = (torch.nn.functional.avg_pool2d(occ, 2 * r_ + 1, 1, r_, count_include_pad=False) * (2 * r_ + 1) ** 2 >= min_dichte * fak).float().view(len(V), -1)   # Dichte statt 'irgendein Punkt'
                rec = occ[:, Sidx].mean(1); f1 = 2 * prec * rec / (prec + rec + 1e-6); b = int(torch.argmax(f1))
                if float(f1[b]) > best["f1"]:
                    best = dict(f1=float(f1[b]), drehung_grad=w, versatz_m=[float(V[b, 0]), float(V[b, 1])], randdeckung=float(rec[b]), auf_rand=float(prec[b]))
        t = dict(teil=i, flaeche_m2=round(float(mit[i][1]), 1), randproben=int(len(S)), deckung=round(jetzt, 3), gedreht={k: (round(v, 3) if isinstance(v, float) else v) for k, v in best.items()})
        # Warnung: gedrehte Form passt (F1 >= 0,6) UND erklaert >= 40 Prozentpunkte mehr Rand als der Ist-Zustand
        # (Schwabentor-Tuermchen: Ist 31 % - eine fremde Wandlinie streift die gerade Seite -, gedreht 174 Grad 94 %; Hauptteil Ist 65 %, gedreht 42 %)
        t["hinweis"] = bool(jetzt < 0.5); t["warnung"] = bool(best["f1"] >= 0.6 and best.get("randdeckung", 0) - jetzt >= 0.4); out.append(t)
    return out


def haufen_geklaert(h, gekl, faktor=2.0):
    """Befund eines am Foto geklaerten Haufens oder None. 22.11.2026 (schwabentor-1122): der Strassenhaufen der falsch ausgerichteten Wolke
    (348 813 Punkte, versetzte Ost- und Nordwaende) lag mit seiner Mitte 0,5 m neben dem in schwabentor-1120 geklaerten Platz-Haufen
    (44 105 Punkte, Laterne/Masten/Passanten) - ein mitkopierter Eintrag haette die falsche Lage durchgewunken. Darum: Eintrag mit "punkte"
    (Punktzahl beim Klaeren) gilt nur, solange der Haufen hoechstens faktor-mal so gross ist; ohne "punkte" wie bisher nur nach Lage."""
    for g in gekl:
        if np.hypot(h["mitte"][0] - g["mitte"][0], h["mitte"][1] - g["mitte"][1]) > g.get("radius_m", 5.0): continue
        if g.get("punkte") and h["punkte"] > faktor * g["punkte"]:
            print(f"A Haufen bei {h['mitte']} ({h['punkte']} Punkte) liegt bei einem geklaerten Haufen, ist aber {h['punkte'] / g['punkte']:.1f}x so gross "
                  f"wie beim Klaeren ({g['punkte']}) - gilt NICHT als geklaert (neue Wolke/Lage, erneut am Foto pruefen)")
            continue
        return g.get("befund", "ja")
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("objekt"); ap.add_argument("--wolke", required=True); ap.add_argument("--radius", type=float, default=60.0)
    ap.add_argument("--wandabstand", type=float, default=1.5); ap.add_argument("--haufen", type=int, default=5000)
    ap.add_argument("--abstand", type=float, default=0.15); ap.add_argument("--zelle", type=float, default=0.25)
    ap.add_argument("--max_verschiebung", type=float, default=8.0, help="m; FFT-Treffer weiter weg passen auf Nachbarhaeuser (Schwabentor: 52 m), nicht zaehlen")
    ap.add_argument("--gml", default="", help="LoD2-GML statt objekt.json lod2.gml")
    ap.add_argument("--min_wandpunkte", type=int, default=0, help="Mindestzahl Wolkenpunkte im Wandband (z 1,5-9 m, Umkreis); 0 = --haufen. Darunter rc 4 'nicht geprueft'")
    a = ap.parse_args()
    obj = json.load(open(a.objekt)); od = os.path.dirname(os.path.abspath(a.objekt))
    if a.gml: obj["_gml"] = a.gml
    B = grundrisse(obj, a.radius)
    from matplotlib.path import Path
    polys = [g for b in B for g in b["ground"] if len(g) >= 3]
    segs = []
    for g in polys:
        q = np.vstack([g, g[:1]])
        for p0, p1 in zip(q[:-1], q[1:]):
            n = max(2, int(np.linalg.norm(p1 - p0) / 0.1)); segs.append(p0 + np.linspace(0, 1, n)[:, None] * (p1 - p0))
    W = np.vstack(segs)
    X = np.load(a.wolke).astype(float)
    band = (X[:, 2] > 1.5) & (X[:, 2] < 9) & (np.hypot(X[:, 0], X[:, 1]) < a.radius * 0.8)
    Q = X[band][:, :2]
    # 17.11.2026 (Durchsicht): keine Mindestzahl - eine fast leere Wolke im Rahmen (300 Punkte: falscher Massstab/falsche Lage, Fusion fast leer) ergab "A Strasse 0.0 %" und rc 0 = Tor bestanden.
    # Test A schlaegt erst bei einem Haufen > --haufen Punkten an; mit weniger Wandpunkten als --haufen KANN er nicht durchfallen - dann ist nichts geprueft (rc 4, kein Urteil).
    # Bestand: schwab_v3 1,16 Mio., kaufhaus_gk 1,11 Mio., martinstor_gk 0,49 Mio. Wandpunkte - fuer sie aendert sich nichts.
    n_min = a.min_wandpunkte or a.haufen
    if len(Q) < n_min:
        print(f"NICHT GEPRUEFT (Grundriss-Tor): nur {len(Q)} Wolkenpunkte im Wandband (z 1,5-9 m, Umkreis {a.radius * 0.8:.0f} m; Wolke {len(X)} Punkte), Mindestzahl {n_min} - "
              "Wolke leer/falsch skaliert/falsch verortet? KEIN Lage-Urteil, gilt nicht als bestanden")
        os.makedirs(os.path.join(od, "audit"), exist_ok=True)
        json.dump(dict(werkzeug="wolke_grundriss_pruefen.py", wolke=a.wolke, lod2_gebaeude=len(B), wandpunkte=int(len(Q)), geprueft=False, ergebnis=f"nicht geprueft: {len(Q)} Wandpunkte < {n_min}",
                       strasse=dict(anteil=None, haufen=[], warnung=None)), open(os.path.join(od, "audit", "wolke_grundriss.json"), "w"), indent=1, ensure_ascii=False)
        raise SystemExit(4)
    # --- A: Strasse
    innen = np.zeros(len(Q), bool)
    for g in polys:
        innen |= Path(g).contains_points(Q)
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); from gpu_knn import min_abstand   # GPU (Nutzerregel)
    z0 = lambda P: np.c_[P, np.zeros(len(P))]
    dwand = min_abstand(z0(Q), z0(W))
    strasse = ~innen & (dwand > a.wandabstand)
    gr = 1.0; ij = np.floor(Q[strasse] / gr).astype(int); haufen = []
    if len(ij):
        o = ij.min(0); sz = ij.max(0) - o + 1; G = np.zeros(sz[::-1], int); np.add.at(G, (ij[:, 1] - o[1], ij[:, 0] - o[0]), 1)
        lab, n = ndimage.label(G > 0, structure=np.ones((3, 3)))
        for k in range(1, n + 1):
            cnt = int(G[lab == k].sum())
            if cnt < 200: continue
            yy, xx = np.nonzero(lab == k)
            haufen.append(dict(punkte=cnt, mitte=[round(float((xx.mean() + o[0] + .5) * gr), 1), round(float((yy.mean() + o[1] + .5) * gr), 1)],
                               ausdehnung_m=[int(np.ptp(xx) + 1), int(np.ptp(yy) + 1)]))
        haufen.sort(key=lambda h: -h["punkte"])
    anteil = float(strasse.mean())
    try:                                                                     # 20.11.2026: die Strassenpunkte selbst ablegen (hoechstens 300 000) - haufen_herkunft.py/haufen_am_foto.py brauchen GENAU diese Punkte, nicht den Kasten um den Haufen (der enthaelt auch echte Waende)
        _S = X[band][strasse]; _S = _S[np.random.default_rng(0).choice(len(_S), min(len(_S), 300000), replace=False)]
        os.makedirs(os.path.join(od, "audit"), exist_ok=True); np.save(os.path.join(od, "audit", "wolke_grundriss_strasse.npy"), _S.astype(np.float32))
    except Exception as e_: print("Strassenpunkte nicht abgelegt:", e_)
    # --- C: LoD2-Teile des Zielgebaeudes ohne Wolke / gedrehtes Teilnetz (Formvergleich auf GPU)
    teile_c = []; warn_c = False
    zid = obj["lod2"].get("id") if isinstance(obj.get("lod2"), dict) else None
    ziel = [b for b in B if b["id"] == zid]
    if ziel:
        teile_c = teile_pruefen([g for g in ziel[0]["ground"] if len(g) >= 3], [g for b in B if b["id"] != zid for g in b["ground"] if len(g) >= 3], Q,
                                min_abstand, z0, Path)
        warn_c = any(t["warnung"] for t in teile_c)
    # --- B: Eindeutigkeit (FFT, Drehung x Spiegelung)
    R = a.zelle; N = int(2 * a.radius / R); N += N % 2; half = N * R / 2
    def ras(p):
        g = np.zeros((N, N), np.float32); k = ((p + half) / R).astype(int); ok = (k >= 0).all(1) & (k < N).all(1); np.add.at(g, (k[ok, 1], k[ok, 0]), 1); return g
    import torch                                                             # FFT-Suche auf der GPU, alle 360 Drehungen je Spiegelung als Stapel
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    if dev == "cpu": print("WARNUNG: keine GPU, FFT laeuft auf CPU")
    L = ndimage.binary_dilation(ras(W) > 0, iterations=2).astype(np.float32)
    FL = torch.fft.rfft2(torch.as_tensor(L, device=dev))
    Qw = Q[~strasse]; ctr = Qw.mean(0); Qc = Qw - ctr
    g0 = np.minimum(ras(Qw), 5.0); ident = float((g0 * L).sum() / g0.sum())
    sh = torch.fft.fftfreq(N, d=1.0 / N, device=dev) * R                     # Verschiebung je FFT-Index (m)
    fenster = (sh[:, None] ** 2 + sh[None, :] ** 2) <= a.max_verschiebung ** 2
    res = []; Pt = torch.as_tensor(Qc, dtype=torch.float32, device=dev); ct = torch.as_tensor(ctr, dtype=torch.float32, device=dev)
    for sp in (0, 1):
        P0 = Pt * torch.tensor([-1.0 if sp else 1.0, 1.0], device=dev)
        stapel = max(1, min(30, int(2.0e7 // max(1, len(Pt)))))               # ~40 Byte je Punkt und Drehung: 2e7 Elemente = ca. 0,8 GiB (20.11.: 7,9 Mio. Punkte * 30 = OOM auf 8 GB)
        for d0 in range(0, 360, stapel):
            degs = np.arange(d0, min(360, d0 + stapel)); t = torch.as_tensor(np.radians(degs), dtype=torch.float32, device=dev)
            c, s_ = torch.cos(t), torch.sin(t)
            X2 = (P0[None, :, 0] * c[:, None] - P0[None, :, 1] * s_[:, None]) + ct[0]
            Y2 = (P0[None, :, 0] * s_[:, None] + P0[None, :, 1] * c[:, None]) + ct[1]
            kx = ((X2 + half) / R).long(); ky = ((Y2 + half) / R).long(); ok = (kx >= 0) & (kx < N) & (ky >= 0) & (ky < N)
            b = torch.arange(len(degs), device=dev)[:, None].expand_as(kx)
            G = torch.zeros(len(degs) * N * N, device=dev)
            G.index_add_(0, (b * N * N + ky * N + kx)[ok], torch.ones(int(ok.sum()), device=dev))
            G = torch.clamp(G.view(len(degs), N, N), max=5.0)
            cc = torch.fft.irfft2(FL[None] * torch.conj(torch.fft.rfft2(G)), s=(N, N))
            cc = cc.masked_fill(~fenster, float("-inf"))
            mx, am = cc.view(len(degs), -1).max(1); su = G.view(len(degs), -1).sum(1)
            for i, deg in enumerate(degs):
                k0, k1 = divmod(int(am[i]), N); dy = (k0 if k0 < N / 2 else k0 - N) * R; dx = (k1 if k1 < N / 2 else k1 - N) * R
                res.append(dict(anteil=float(mx[i] / su[i]), spiegel=sp, drehung=int(deg), verschiebung=[round(dx, 2), round(dy, 2)]))
    res.sort(key=lambda r: -r["anteil"])
    def nah(r): return r["spiegel"] == 0 and min(r["drehung"], 360 - r["drehung"]) <= 15
    best_nah = next(r for r in res if nah(r)); best_alt = next(r for r in res if not nah(r))
    rel = (best_nah["anteil"] - best_alt["anteil"]) / max(best_nah["anteil"], 1e-9)
    warn_b = best_alt["anteil"] > best_nah["anteil"] or rel < a.abstand
    # 15.11.2026: am FOTO geklaerte Haufen (objekt.json "grundriss_haufen_geklaert": [{"mitte": [x, y], "radius_m": r, "befund": "...", "quelle": "Fotos ..."}])
    # zaehlen nicht mehr als Warnung - z. B. Erker/Traufe des Nachbarhauses oder Galerie, die ueber den LoD2-Grundriss kragen (echt, kein Teilnetzfehler).
    _gekl = obj.get("grundriss_haufen_geklaert", [])
    for h in haufen: h["geklaert"] = haufen_geklaert(h, _gekl)
    _offen = [h for h in haufen if not h["geklaert"]]
    warn_a = bool(_offen) and _offen[0]["punkte"] > a.haufen
    for h in haufen[:5]:
        if h["geklaert"] and h["punkte"] > a.haufen: print(f"A Haufen bei {h['mitte']} ({h['punkte']} Punkte) am Foto geklaert: {h['geklaert']}")
    out = dict(werkzeug="wolke_grundriss_pruefen.py", wolke=a.wolke, lod2_gebaeude=len(B), wandpunkte=int(len(Q)), geprueft=True,
               strasse=dict(anteil=round(anteil, 4), haufen=haufen[:10], warnung=warn_a), teile=dict(ziel=zid, teile=teile_c, warnung=warn_c),
               eindeutigkeit=dict(identitaet_anteil=round(ident, 4), beste_nahe_identitaet=best_nah, beste_alternative=best_alt,
                                  abstand_relativ=round(rel, 3), warnung=warn_b, top5=res[:5]))
    os.makedirs(os.path.join(od, "audit"), exist_ok=True)
    json.dump(out, open(os.path.join(od, "audit", "wolke_grundriss.json"), "w"), indent=1, ensure_ascii=False)
    try:
        import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
        fig, ax = plt.subplots(figsize=(10, 10)); s = np.random.default_rng(0).choice(len(Q), min(150000, len(Q)), replace=False)
        ax.scatter(Q[s, 0], Q[s, 1], s=0.2, c=np.where(strasse[s], "red", "0.55"))
        for g in polys:
            q = np.vstack([g, g[:1]]); ax.plot(q[:, 0], q[:, 1], "k", lw=1)
        ax.set_aspect("equal"); lim = a.radius * 0.8; ax.set_xlim(-lim, lim); ax.set_ylim(-lim, lim)
        ax.set_title("Wandpunkte grau, auf der Strasse rot (%.1f %%), LoD2-Grundrisse schwarz" % (100 * anteil))
        plt.tight_layout(); plt.savefig(os.path.join(od, "audit", "wolke_grundriss.png"), dpi=70)
    except Exception as e:
        print("Bild nicht erzeugt:", e)
    print("A Strasse: %.1f %% der Wandpunkte ausserhalb LoD2 und > %.1f m von jeder Wand" % (100 * anteil, a.wandabstand))
    for h in haufen[:5]: print("   Haufen %6d Punkte bei (%.1f/%.1f), %dx%d m" % (h["punkte"], *h["mitte"], *h["ausdehnung_m"]))
    print("B Eindeutigkeit: aktuelle Lage %.3f, beste nahe Identitaet %.3f (%d Grad), beste Alternative %.3f (Spiegel %d, %d Grad), Abstand %.1f %%"
          % (ident, best_nah["anteil"], best_nah["drehung"], best_alt["anteil"], best_alt["spiegel"], best_alt["drehung"], 100 * rel))
    # Kontrolle 2026-11-14: B warnt auch am korrekt liegenden Kaufhaus (Abstand 4,4 %), Wandlinien-Ueberlapp trennt nicht -> B nur HINWEIS, Tor ist A
    # (Kaufhaus 0,4 % / Haufen <1200 Punkte, Schwabentor 10 % / Haufen 207 190 Punkte = falscher Fluegel).
    if warn_b: print("HINWEIS B: Drehlage gegen LoD2 nicht eindeutig (allein kein Fehlerbeleg, Kontrolle Kaufhaus warnt auch) - nur zusammen mit A deuten.")
    for t in teile_c:
        gd = t["gedreht"]
        print("C Teil %d (%.0f m2): Wolke deckt %.0f %% des eigenen Randes; beste gedrehte Form %s Grad (Versatz %s m): F1 %.2f (Rand %.0f %%, auf Rand %.0f %%)" % (
              t["teil"], t["flaeche_m2"], 100 * t["deckung"], gd.get("drehung_grad", "-"), gd.get("versatz_m", "-"), gd["f1"], 100 * gd.get("randdeckung", 0), 100 * gd.get("auf_rand", 0)))
    if any(t["hinweis"] and not t["warnung"] for t in teile_c): print("HINWEIS C: LoD2-Teil kaum von Wolke gedeckt (ungesehen? Kameraabdeckung pruefen)")
    if warn_c: print("HINWEIS C: gedrehte Wolke fuellt einen LoD2-Teil deutlich besser als der Ist-Zustand - moeglich falsch gedrehtes Teilnetz; "
                     "am Foto/Kamera-GPS klaeren (kein Tor: Kontrolle Kaufhaus schlaegt bei kleinen Rechteckteilen auch an)")
    if warn_a: print("WARNUNG A: grosser Wolkenhaufen auf der Strasse - am Foto klaeren (falsch verortetes Teilnetz?), NICHT modellieren."); raise SystemExit(3)


if __name__ == "__main__":
    main()
