#!/usr/bin/env python3
"""bogen_anpassen.py - Bogenmasse (u0, u1, Kaempfer zk, Scheitel zs) je Bogen an die Fotokanten mehrerer kalibrierter Fotos anpassen (5.11., Nutzer:
"die vier Boegen muessen stimmen"). Analyse durch Synthese in 2D: Bogenumriss (Leibung + Segmentbogen, wie baukasten_gen.segmentbogen) in der Fassadenebene
mit der Buendelkamera (K-<foto>.json, rahmen_verschiebung) ins entzerrte Foto projizieren; Kosten = mittlere, bei --kappe gekappte Distanz der
Umrisspunkte zur naechsten Fotokante (foto_diff.fotokanten_mehrstufig: Skalen bis 1 cm x Belichtungen, Persistenz). Suche: Koordinatenabstieg mit
halbierender Schrittweite je Bogen (unabhaengig, Boegen ueberlappen nicht). Uebernahme je Bogen NUR, wenn die Kosten in JEDEM Foto sinken
(Konvergenzregel: kein Mitteln, kein Verschlechtern eines Fotos). Ausgabe: Elementdatei mit angepassten Boegen (+ 'anpassung'), Pruefbild je Foto.
GRENZEN: Verdecker (Personen, Stande) nicht maskiert -> Kappe; Leibungstiefe nicht gesucht (Foto sieht keine Tiefe); Ebene = Fassadenebene (Bogenstirn).
  python tools/bogen_anpassen.py modelle/<obj>/objekt.json <elemente.json> --fassade f02 --fotos 004 040 --aus <ordner>
"""
import os, sys, json, glob, argparse, copy
import numpy as np, cv2
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fehlteile_finden as FF
from foto_diff import fotokanten_mehrstufig
KETTE = os.environ.get("BOGEN_KETTE", "1") == "1"   # Kanten, die alle Skalen 16 cm .. 1 cm ueberleben (Persistenz-UND); 0 = ODER aller Skalen (zu dicht: Leibungen wanderten auf Pfeilerkanten)


def umriss(u0, u1, zk, zs, z_fuss, schritt=0.03):
    """Bogenumriss in (u, z): linke Leibung hoch, Segmentbogen, rechte Leibung runter (Stirnkante)."""
    c = (u0 + u1) / 2; h = (u1 - u0) / 2; s = zs - zk
    if s <= 1e-3: s = 1e-3
    r = (h * h + s * s) / (2 * s); zc = zs - r; a = np.arcsin(np.clip(h / r, -1, 1))
    nb = max(8, int(r * 2 * a / schritt)); th = np.linspace(-a, a, nb)
    bogen = np.c_[c + r * np.sin(th), zc + r * np.cos(th)]
    nl = max(2, int((zk - z_fuss) / schritt)); zl = np.linspace(z_fuss, zk, nl)
    return np.vstack([np.c_[np.full(nl, u0), zl], bogen, np.c_[np.full(nl, u1), zl[::-1]]])


class Foto:
    def __init__(s, objp, obj, root, nr, glatt_max, glatt_min):
        kp = FF.k_datei(objp, obj, root, nr); K = json.load(open(kp)); kk = K["kamera"]
        im = cv2.imread(glob.glob(os.path.join(root, obj["fotos_dir"], nr + "_*"))[0]); H, W = im.shape[:2]
        im, _ = FF.foto_entzerren(im, kk); s.R, s.t, s.f, _, _ = FF.kamera_laden(K, obj, nr, root, W, H)
        s.cx, s.cy = float(kk.get("cx", W / 2)), float(kk.get("cy", H / 2)); s.rv = np.asarray(kk.get("rahmen_verschiebung", [0, 0, 0]), float)
        s.nr, s.im, s.W, s.H = nr, im, W, H; s.glatt_max, s.glatt_min = glatt_max, glatt_min; s.dt = None

    def proj(s, X):
        Xc = (X + s.rv) @ np.asarray(s.R).T + np.asarray(s.t).ravel(); z = Xc[:, 2]
        return np.c_[s.f * Xc[:, 0] / z + s.cx, s.f * Xc[:, 1] / z + s.cy], z

    def kanten(s, X_mitte):
        _, z = s.proj(X_mitte[None]); ppm = s.f / float(z[0])                                       # Pixel je Meter an der Fassade
        g = cv2.cvtColor(s.im, cv2.COLOR_BGR2GRAY); s.fk = fotokanten_mehrstufig(g, ppm, s.glatt_max, s.glatt_min, s.W, s.H, kette=KETTE)
        s.dt = cv2.distanceTransform((~s.fk).astype(np.uint8), cv2.DIST_L2, 5); s.ppm = ppm


def kosten(F, P3, kappe_m):
    p, z = F.proj(P3); ok = (z > 1) & (p[:, 0] >= 0) & (p[:, 0] < F.W - 1) & (p[:, 1] >= 0) & (p[:, 1] < F.H - 1)
    if ok.sum() < 10: return None
    d = F.dt[p[ok, 1].astype(int), p[ok, 0].astype(int)] / F.ppm
    return float(np.minimum(d, kappe_m).mean())


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("elemente"); ap.add_argument("--fassade", required=True)
    ap.add_argument("--fotos", nargs="+", required=True); ap.add_argument("--aus", required=True); ap.add_argument("--kappe", type=float, default=0.25)
    ap.add_argument("--schritt", type=float, default=0.16); ap.add_argument("--min-schritt", type=float, default=0.01); ap.add_argument("--max-aend", type=float, default=0.6)
    ap.add_argument("--glaettung", type=float, default=0.16); ap.add_argument("--glaettung-min", type=float, default=0.01); ap.add_argument("--z-fuss", type=float, default=1.0,
                    help="Leibung ab dieser Hoehe bewerten (darunter Personen/Stande; ANNAHME)")
    ap.add_argument("--restfeld", help="restfeld_<fassade>.npz (restfeld_fassade.py): Pfeiler = Wandzellen (Tiefe < --wand-m) der Wolke; Leibungen nur im Band "
                    "+-(--band) um den Wolkenrand (Zwei-Quellen-Regel: Wolke sagt WO Wand/Oeffnung, Foto sagt die genaue Kante; 5.11. ohne: Pfeiler auf 0 m geschrumpft)")
    ap.add_argument("--band", type=float, default=0.25); ap.add_argument("--wand-m", type=float, default=0.5); ap.add_argument("--wand-z", type=float, nargs=2, default=[1.5, 3.0])
    a = ap.parse_args(argv); os.makedirs(a.aus, exist_ok=True)
    op = os.path.abspath(a.objekt); obj = json.load(open(op)); root = os.path.dirname(os.path.dirname(os.path.dirname(op)))
    E = json.load(open(a.elemente)); Fa = E["fassaden"][a.fassade]; n = np.array(Fa["n"], float); d = np.r_[np.array(Fa["d"], float)[:2], 0.0]; o = np.r_[np.array(Fa["o"], float)[:2], 0.0]   # Grundriss-2D -> 3D (z aus Element)
    welt = lambda U: o[None] + U[:, :1] * d[None] + U[:, 1:2] * np.array([[0, 0, 1.0]])   # Elementrahmen: X = o + u d + z e_z (Generator: u' = -u, d' = -d, gleich)
    B = [e for e in Fa["elemente"] if e["klasse"] == "bogen"]
    um = np.mean([[(e["u0"] + e["u1"]) / 2, (e["kaempfer"] + e["z1"]) / 2] for e in B], 0)
    FO = [Foto(op, obj, root, nr, a.glaettung, a.glaettung_min) for nr in a.fotos]
    for F in FO: F.kanten(welt(um[None])[0])
    wand = None
    if a.restfeld:                                                                                   # Wandanteil je u-Spalte im Hoehenband (Pfeilerschaefte)
        z_ = np.load(a.restfeld); D = z_["daten"]; c_ = float(z_["zelle"]); r0, r1 = int((float(z_["z1"]) - a.wand_z[1]) / c_), int((float(z_["z1"]) - a.wand_z[0]) / c_)
        w_ = (np.nan_to_num(D[r0:r1], nan=9) < a.wand_m).mean(0); uu_ = float(z_["u0"]) + (np.arange(D.shape[1]) + 0.5) * c_
        wand = (uu_, w_ > 0.15)                                                                      # ANNAHME: >= 15 % Wandzellen im Band = Pfeiler (Wolke duenn an Kanten)
    def wolkenrand(e):
        if wand is None: return None
        uu_, ww = wand; m_ = (e["u0"] + e["u1"]) / 2; i = int(np.argmin(np.abs(uu_ - m_)))
        if ww[i]: return None
        l = i; r = i
        while l > 0 and not ww[l - 1]: l -= 1
        while r < len(ww) - 1 and not ww[r + 1]: r += 1
        return float(uu_[l] - 0.05), float(uu_[r] + 0.05)
    erg = []; E2 = copy.deepcopy(E)
    for i, e in enumerate(B):
        p0 = np.array([e["u0"], e["u1"], e["kaempfer"] or e["z1"] - 0.3 * (e["u1"] - e["u0"]), e["z1"]], float); wr = wolkenrand(e)
        if wr: print(f"  Bogen {i}: Wolke Oeffnung u {wr[0]:.2f} .. {wr[1]:.2f} (Element {p0[0]:.2f} .. {p0[1]:.2f})", flush=True)
        def K(p): return [kosten(F, welt(umriss(p[0], p[1], p[2], p[3], a.z_fuss)), a.kappe) for F in FO]
        def ges(p):
            k = K(p); return (np.inf if any(x is None for x in k) or p[2] >= p[3] - 0.05 or p[1] - p[0] < 0.5 or np.abs(p - p0).max() > a.max_aend or (wr and (abs(p[0] - wr[0]) > a.band or abs(p[1] - wr[1]) > a.band)) else float(np.sum(k)))
        p = p0.copy()
        if wr: p[0], p[1] = wr; p0 = p.copy()                                                         # Start auf dem Wolkenrand (Element lag bis 0,9 m daneben)
        best = ges(p); st = a.schritt
        while st >= a.min_schritt:
            besser = False
            for j in range(4):
                for sg in (1, -1):
                    q = p.copy(); q[j] += sg * st; c = ges(q)
                    if c < best - 1e-6: p, best, besser = q, c, True
            if not besser: st /= 2
        rand = []
        if wr:                                                                                       # Leibung am Bandrand = Foto zieht aus dem Wolkenband: WIDERSPRUCH, nicht uebernehmen (Regel 5)
            for j_, nm in ((0, "u0"), (1, "u1")):
                if abs(abs(p[j_] - wr[j_]) - a.band) < 1e-6: rand.append(nm); p[j_] = wr[j_]
        k0, k1 = K(p0), K(p); uebern = all(b < a_ for a_, b in zip(k0, k1))
        r = dict(bogen=i, alt=dict(zip(["u0", "u1", "kaempfer", "z1"], np.round(p0, 3).tolist())), neu=dict(zip(["u0", "u1", "kaempfer", "z1"], np.round(p, 3).tolist())),
                 kosten_alt={F.nr: round(x, 4) for F, x in zip(FO, k0)}, kosten_neu={F.nr: round(x, 4) for F, x in zip(FO, k1)}, uebernommen=uebern, widerspruch_bandrand=rand)
        erg.append(r); print(json.dumps(r, ensure_ascii=False), flush=True)
        if uebern:
            e2 = [x for x in E2["fassaden"][a.fassade]["elemente"] if x["klasse"] == "bogen"][i]
            e2.update(u0=float(p[0]), u1=float(p[1]), kaempfer=float(p[2]), z1=float(p[3]))
            e2["anpassung"] = f"bogen_anpassen.py Fotos {','.join(a.fotos)} mehrstufige Kanten {a.glaettung_min}-{a.glaettung} m, Kosten je Foto gesunken"
    E2.setdefault("anpassungen", []).append(dict(werkzeug="bogen_anpassen.py", fassade=a.fassade, fotos=a.fotos, ergebnis=erg))
    json.dump(E2, open(os.path.join(a.aus, "elemente_boegen.json"), "w"), indent=1, ensure_ascii=False)
    for F in FO:                                                                                     # Pruefbild: Fotokanten gelb, alt rot, neu gruen
        v = (F.im * 0.55).astype(np.uint8); v[F.fk] = (0, 220, 255); pts_all = []
        for r in erg:
            for key, col in (("alt", (0, 0, 255)), ("neu", (0, 255, 0))):
                q = r[key]; p2, _ = F.proj(welt(umriss(q["u0"], q["u1"], q["kaempfer"], q["z1"], a.z_fuss - 0.5)))
                cv2.polylines(v, [p2.astype(np.int32)], False, col, 3); pts_all.append(p2)
        P = np.vstack(pts_all); x0, y0 = np.maximum(P.min(0) - 150, 0).astype(int); x1, y1 = np.minimum(P.max(0) + 150, [F.W, F.H]).astype(int)
        cv2.imwrite(os.path.join(a.aus, f"boegen_{F.nr}.jpg"), v[y0:y1, x0:x1])
    json.dump(erg, open(os.path.join(a.aus, "bogen_anpassung.json"), "w"), indent=1, ensure_ascii=False)


if __name__ == "__main__":
    main()
