#!/usr/bin/env python3
"""bogen_gewaende.py - GEWAENDE (Werkstein-Rahmenband) um gebaute Tor-/Bogenoeffnungen aus dem feinen Wandbild (24.11.2026, Kettenstufe 'bauplan' nach oeffnungen_aus_kanten).

Anlass (Kettenlauf 1122w, Schwabentor, audit/neben_detail_oeffnung_bogen_f00/_f01.jpg, neben_sued_w): beide Torboegen haben im Foto ein deutlich abgesetztes
Sandstein-Gewaende (Bogensteine als Ring um den Spitzbogen, glatter als die Bruchsteinquader), im Modell nur ein glattes Loch. Ursache: bauteile.oeffnungen_aus_json
schneidet nur das Loch; das 'gewaende' aus oeffnungen_aus_kanten ist nur der Abstand Aussen-/Innenkante (Fase, 0,12-0,15 m) und wird nicht gebaut;
loch_gewaende.py behandelt nur Fenster/geschlossene Tueren (dunkles Loch), nie gebaute Durchblicke.
Methode (WANDBILD = BAUPLAN, keine Musterteile, keine generierten Bogensteine): je gebauter Oeffnung in audit/oeffnungen_auto.json
  1. ABROLLEN: der lichte Umriss (bogen_querschnitt wie im Bau) wird in 1-cm-Schritten abgegangen, je Punkt die Aussennormale; das Wandbild wird entlang der Normalen
     0..dmax m abgetastet -> Streifen S[d, s] (Zeile = Abstand vom Loch, Spalte = Weg entlang des Umrisses).
  2. BAND im Bogen/Sturz (Umrissteil ueber dem Kaempfer): die Bogensteine laufen RADIAL ueber die ganze Bandbreite - jede Streifenzeile im Band zeigt dieselben
     Stossfugen (Zeilenkorrelation hoch), ausserhalb liegen die Lagerfugen des Mauerwerks quer dazu (Korrelation ~0). Kernzeile r0 = Zeile mit der hoechsten
     Korrelation zu ihren +-10-cm-Nachbarn; Band = zusammenhaengende Zeilen mit Korrelation zur Kernzeile >= --schwelle; Aussenkante b = erste Zeile darunter.
     GUARD: Kontrast (Band gegen 5-30 cm ausserhalb) >= --kontrast, Bandbreite >= 0,08 m, b <= dmax - 0,3; sonst kein Band (Grund im Bericht).
  3. PFOSTEN: die Pfostensteine sind mit dem Mauerwerk verzahnt (Lagerfugen laufen durch) - im Wandbild nicht trennbar (gemessen 1122w: Kante je Spalte streut
     0,1-0,7 m). Breite = Bogenband (ANNAHME im Eintrag).
  4. VORSPRUNG: Tiefe je Zelle (fassade/tiefe_<fid>.npz, w positiv = vor der Wand): Median im Band gegen Median im Wandring b+0,1..b+0,4; plausibel 0,01-0,30 m,
     sonst ANNAHME Druckmindestmass (MINMM x SCALE).
Ausgabe: oeffnungen_auto.json bekommt je gebauter Oeffnung 'gewaende_band' {aussen (m vom lichten Umriss), innen, vorsprung, *_quelle, kontrast, ...}; Bericht
  bogen_gewaende.json und Bild bogen_gewaende_<fid>.jpg (rot = lichter Umriss, gelb = Aussenkante des Bands; ANSEHEN). Bau: bauteile.bogen_gewaende_spaet
  (auf der echten Oberflaeche nach allen Anbauten, Generator-Vorlage objekt_anlegen.py).
Aufruf:  bogen_gewaende.py <audit/oeffnungen_auto.json> <fassade_fein-ordner> [--fassade <fassade-ordner mit tiefe_fNN.npz>] [--aus ordner] [--nur f00 f01]
rc 0 = mindestens ein Band vermessen, 3 = nichts geaendert.
"""
import sys, os, json, argparse
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

SCHRITT = 0.01


def druck_min():
    return float(os.environ.get("MINMM", "0.8")) * float(os.environ.get("SCALE", "87")) / 1000.0


def umriss_pfad(x, schritt=SCHRITT):
    """Lichter Umriss der Oeffnung x (form, breite, kaempfer, scheitel, unten; u-Mitte = 0) ohne die Unterkante, gleichmaessig abgetastet.
    Liefert (Q [n,2] in (quer, z), N [n,2] Aussennormalen, teil [n] 'oben'/'links'/'rechts')."""
    import cv2
    from bauteile import bogen_querschnitt
    un = float(x.get("unten", 0.0))
    P = np.array(bogen_querschnitt(x["form"], float(x["breite"]), float(x["kaempfer"]), float(x["scheitel"]), un).to_polygons()[0], float)
    n = len(P); boden = [i for i in range(n) if P[i, 1] <= un + 1e-6 and P[(i + 1) % n, 1] <= un + 1e-6]
    if boden: P = np.roll(P, -(boden[0] + 1), axis=0)                  # Pfad beginnt an einer Unterecke und endet an der anderen
    Q = []
    for i in range(len(P) - 1):
        a, b = P[i], P[i + 1]; L = float(np.hypot(*(b - a))); k = max(1, int(np.ceil(L / schritt)))
        Q += [a + (b - a) * t for t in np.arange(k) / k]
    Q.append(P[-1]); Q = np.array(Q)
    T = np.gradient(Q, axis=0); T /= np.linalg.norm(T, axis=1, keepdims=True) + 1e-12
    N = np.stack([T[:, 1], -T[:, 0]], 1)
    kont = P.astype(np.float32).reshape(-1, 1, 2)
    mitte = len(Q) // 2
    if cv2.pointPolygonTest(kont, (float(Q[mitte, 0] + 0.05 * N[mitte, 0]), float(Q[mitte, 1] + 0.05 * N[mitte, 1])), False) > 0: N = -N
    senk = np.abs(T[:, 1]) > 0.97
    teil = np.where(senk & (Q[:, 1] < float(x["kaempfer"]) + 0.02), np.where(Q[:, 0] < 0, "links", "rechts"), "oben")
    return Q, N, teil


def abrollen(bgr, raster, x, dmax=1.0, schritt=SCHRITT):
    """Wandbild entlang der Aussennormalen des lichten Umrisses abtasten. raster = {u0, z1, zelle} des Wandbilds. Liefert (S [D, n, 3] BGR, bel [D, n] bool, Q, N, teil, D)."""
    import cv2
    Q, N, teil = umriss_pfad(x, schritt)
    D = np.arange(0.0, dmax, schritt)
    UU = float(x["u"]) + Q[None, :, 0] + D[:, None] * N[None, :, 0]; ZZ = Q[None, :, 1] + D[:, None] * N[None, :, 1]
    c = float(raster["zelle"])
    mx = ((UU - float(raster["u0"])) / c).astype(np.float32); my = ((float(raster["z1"]) - ZZ) / c).astype(np.float32)
    S = cv2.remap(np.ascontiguousarray(bgr), mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=0)
    bel = cv2.remap((bgr.sum(2) > 0).astype(np.uint8), mx, my, cv2.INTER_NEAREST, borderMode=cv2.BORDER_CONSTANT, borderValue=0).astype(bool)
    return S, bel, Q, N, teil, D


def band_radial(L, schritt=SCHRITT, schwelle=0.45, kontrast_min=0.25, min_spalten=50, min_band=0.08, rand_aussen=0.3, kern=(0.08, 0.5)):
    """Rahmenband im abgerollten Helligkeitsstreifen L [D, n] (nur belegte Spalten): radiale Kohaerenz der Steinfugen.
    Liefert dict(aussen, innen, kern, kontrast, profil) oder dict(fehler=...)."""
    import cv2
    D, n = L.shape
    if n < min_spalten: return dict(fehler=f"nur {n} belegte Spalten ueber dem Kaempfer (< {min_spalten})")
    A = L.astype(np.float32)
    hp = A - cv2.GaussianBlur(A, (0, 0), sigmaX=0.15 / schritt, sigmaY=0.1)         # Helligkeitsverlauf entlang des Umrisses weg (Schatten, Licht)
    hp = (hp - hp.mean(1, keepdims=True)) / (hp.std(1, keepdims=True) + 1e-6)
    C = hp @ hp.T / n
    k10 = int(round(0.10 / schritt)); r_lo, r_hi = int(kern[0] / schritt), min(int(kern[1] / schritt), D - k10 - 1)
    if r_hi <= r_lo: return dict(fehler="Streifen zu kurz")
    wert = [float(np.mean(C[r, max(0, r - k10): r + k10 + 1])) for r in range(r_lo, r_hi)]
    r0 = r_lo + int(np.argmax(wert))
    k3 = int(round(0.03 / schritt))
    rho = C[max(0, r0 - k3): r0 + k3 + 1].mean(0)
    rho = np.convolve(rho, np.ones(3) / 3, mode="same")
    b = r0
    while b + 1 < D and rho[b + 1] >= schwelle: b += 1
    a = r0
    while a - 1 >= 0 and rho[a - 1] >= schwelle: a -= 1
    b += 1                                                                # erste Zeile ausserhalb
    aussen, innen = b * schritt, a * schritt
    prof = [round(float(v), 2) for v in rho[::3]]
    if aussen > D * schritt - rand_aussen: return dict(fehler=f"Band reicht bis {aussen:.2f} m - keine Aussenkante im Suchbereich", profil=prof)
    if aussen - innen < min_band: return dict(fehler=f"Band nur {aussen - innen:.2f} m breit", profil=prof)
    o0, o1 = b + int(0.05 / schritt), min(D, b + int(rand_aussen / schritt))
    kontrast = float(np.mean(rho[a:b]) - np.mean(rho[o0:o1]))
    if kontrast < kontrast_min: return dict(fehler=f"Band nicht vom Mauerwerk abgesetzt (Kontrast {kontrast:.2f} < {kontrast_min})", profil=prof)
    return dict(aussen=round(aussen, 3), innen=round(innen, 3), kern=round(r0 * schritt, 3), kontrast=round(kontrast, 2), profil=prof)


def farbe(lab, bel, d0, d1, schritt=SCHRITT):
    """Lab-Median der belegten Zellen in den Zeilen d0..d1 (m)."""
    a, b = int(d0 / schritt), int(d1 / schritt); m = bel[a:b]
    return [round(float(v), 1) for v in np.median(lab[a:b][m], axis=0)] if m.sum() >= 20 else None


def vorsprung_messen(npz, x, innen, aussen, ring=(0.1, 0.4)):
    """Vorsprung des Bands aus der Tiefe je Zelle (w positiv = vor der Wand): Median im Band (innen..aussen vom lichten Umriss) gegen Wandring
    aussen+ring. None, wenn zu wenig sichere Zellen oder unplausibel (< 0,01 oder > 0,30 m)."""
    import cv2
    from bauteile import bogen_querschnitt
    if npz is None: return None
    w, gut = np.asarray(npz["w"], float), np.asarray(npz["gut"]).astype(bool); c = float(npz["zelle"]); u0, z1 = float(npz["u0"]), float(npz["z1"])
    P = np.array(bogen_querschnitt(x["form"], float(x["breite"]), float(x["kaempfer"]), float(x["scheitel"]), float(x.get("unten", 0.0))).to_polygons()[0], float)
    pts = np.stack([(float(x["u"]) + P[:, 0] - u0) / c, (z1 - P[:, 1]) / c], 1).round().astype(np.int32)
    m = np.zeros(w.shape, np.uint8); cv2.fillPoly(m, [pts], 1)
    d = cv2.distanceTransform((1 - m).astype(np.uint8), cv2.DIST_L2, 5) * c
    H, _ = w.shape; z = z1 - np.arange(H)[:, None] * c + 0 * d
    ueber = z > float(x.get("unten", 0.0)) + 0.3
    band = (d > max(innen, c)) & (d <= aussen) & gut & ueber & np.isfinite(w)
    wand = (d >= aussen + ring[0]) & (d <= aussen + ring[1]) & gut & ueber & np.isfinite(w)
    if band.sum() < 10 or wand.sum() < 10: return None
    v = float(np.median(w[band]) - np.median(w[wand]))
    return round(v, 3) if 0.01 <= v <= 0.30 else None


def oeffnung_messen(bgr, raster, x, npz=None, dmax=1.0, schwelle=0.45, kontrast_min=0.25):
    """Gewaende-Band einer gebauten Oeffnung x. Liefert (gewaende_band dict | None, bericht dict, abrollung)."""
    import cv2
    S, bel, Q, N, teil, D = abrollen(bgr, raster, x, dmax)
    lab = cv2.cvtColor(S, cv2.COLOR_BGR2LAB).astype(np.float32); lab[..., 0] *= 100.0 / 255.0; lab[..., 1:] -= 128.0
    un = float(x.get("unten", 0.0))
    sp = (teil == "oben") & (Q[:, 1] > un + 0.3) & (bel.mean(0) >= 0.9)
    erg = band_radial(lab[:, sp, 0], kontrast_min=kontrast_min, schwelle=schwelle) if sp.any() else dict(fehler="kein Bogen/Sturz ueber dem Kaempfer im Wandbild")
    ber = dict(u=x["u"], breite=x["breite"], form=x["form"], spalten_oben=int(sp.sum()), **erg)
    if "fehler" in erg: return None, ber, (S, Q, N, D)
    fb = farbe(lab[:, sp], bel[:, sp], erg["innen"], erg["aussen"]); fw = farbe(lab[:, sp], bel[:, sp], erg["aussen"] + 0.05, erg["aussen"] + 0.3)
    v = vorsprung_messen(npz, x, erg["innen"], erg["aussen"])
    G = dict(aussen=erg["aussen"], innen=erg["innen"], kontrast=erg["kontrast"],
             quelle="bogen_gewaende: radiale Fugen-Kohaerenz im abgerollten feinen Wandbild (Bogen/Sturz ueber dem Kaempfer)",
             pfosten_quelle="ANNAHME: Pfosten so breit wie das Bogenband (Pfostensteine mit dem Mauerwerk verzahnt, im Wandbild nicht trennbar)",
             vorsprung=v if v is not None else round(druck_min(), 3),
             vorsprung_quelle="Tiefe je Zelle (fassade/tiefe_<fid>.npz): Band gegen Wandring" if v is not None else
             "ANNAHME Druckmindestmass (MINMM x SCALE) - Tiefe je Zelle misst das Band nicht (0,01-0,30 m)",
             farbe_band=fb, farbe_wand=fw)
    if fb and fw: G["farbabstand"] = round(float(np.linalg.norm(np.subtract(fb, fw))), 1)
    return G, ber, (S, Q, N, D)


def kontrollbild(bgr, raster, eintraege, pfad, rand=1.2):
    """rot = lichter Umriss, gelb = Aussenkante des Bands (gemessen), grau = kein Band."""
    import cv2
    if not eintraege: return
    c = float(raster["zelle"]); P = lambda u, z: (int(round((u - float(raster["u0"])) / c)), int(round((float(raster["z1"]) - z) / c)))
    us = [x["u"] + s * (x["breite"] / 2 + rand) for x, _ in eintraege for s in (-1, 1)]; zs = [float(x.get("unten", 0.0)) for x, _ in eintraege] + [x["scheitel"] + rand for x, _ in eintraege]
    (j0, i0), (j1, i1) = P(min(us), max(zs)), P(max(us), min(zs))
    i0, j0 = max(0, i0), max(0, j0); i1, j1 = min(bgr.shape[0], i1), min(bgr.shape[1], j1)
    im = np.ascontiguousarray(bgr[i0:i1, j0:j1]).copy()
    for x, G in eintraege:
        Q, N, _ = umriss_pfad(x)
        innen = np.array([P(x["u"] + q[0], q[1]) for q in Q], np.int32) - [j0, i0]
        cv2.polylines(im, [innen], False, (0, 0, 255), 2)
        if G:
            au = np.array([P(x["u"] + q[0] + G["aussen"] * n_[0], q[1] + G["aussen"] * n_[1]) for q, n_ in zip(Q, N)], np.int32) - [j0, i0]
            cv2.polylines(im, [au], False, (0, 230, 255), 2)
            cv2.putText(im, f"Band {G['aussen']:.2f} m, vor {G['vorsprung']:.3f}", (5, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 230, 255), 2)
    s = 900.0 / max(im.shape[:2]); im = cv2.resize(im, None, fx=s, fy=s) if s < 1 else im
    cv2.imwrite(pfad, im)


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("oeffnungen"); ap.add_argument("fein")
    ap.add_argument("--fassade", help="Ordner mit tiefe_<fid>.npz (Vorsprung)"); ap.add_argument("--aus"); ap.add_argument("--nur", nargs="*")
    ap.add_argument("--dmax", type=float, default=1.0); ap.add_argument("--schwelle", type=float, default=0.45); ap.add_argument("--kontrast", type=float, default=0.25)
    a = ap.parse_args(argv)
    import cv2
    from loch_gewaende import wandbild
    aus = a.aus or os.path.dirname(os.path.abspath(a.oeffnungen)); os.makedirs(aus, exist_ok=True)
    J = json.load(open(a.oeffnungen))
    FF = {F["id"]: F for F in json.load(open(os.path.join(a.fein, "fassaden.json")))["fassaden"]}
    bericht = {}; n_ok = 0; alt_weg = 0
    for fid, F in J.items():
        if not isinstance(F, dict) or (a.nur and fid not in a.nur): continue
        geb = [x for x in F.get("oeffnungen", []) if x.get("gebaut")]
        if not geb: continue
        bgr = wandbild(a.fein, fid)
        if fid not in FF or bgr is None: bericht[fid] = "kein feines Wandbild"; continue
        rs = FF[fid]["raster"]
        nz = os.path.join(a.fassade, f"tiefe_{fid}.npz") if a.fassade else None; npz = dict(np.load(nz)) if nz and os.path.exists(nz) else None
        br = []; bild = []
        for x in geb:
            if x.pop("gewaende_band", None) is not None: alt_weg += 1     # zweiter Lauf: nur die neue Messung gilt
            G, ber, _ = oeffnung_messen(bgr, rs, x, npz, a.dmax, a.schwelle, a.kontrast)
            if G: x["gewaende_band"] = G; n_ok += 1
            br.append(ber); bild.append((x, G))
            print(f"{fid} Oeffnung u {x['u']:.2f} ({x['form']}, {x['breite']:.2f} m): " + (f"Band {G['aussen']:.2f} m (innen {G['innen']:.2f}, Kontrast {G['kontrast']:.2f}), "
                  f"Vorsprung {G['vorsprung']:.3f} m" + (" ANNAHME" if "ANNAHME" in G["vorsprung_quelle"] else " gemessen") if G else "kein Band: " + ber["fehler"]))
        bericht[fid] = br; kontrollbild(bgr, rs, bild, os.path.join(aus, f"bogen_gewaende_{fid}.jpg"))
    json.dump(bericht, open(os.path.join(aus, "bogen_gewaende.json"), "w"), indent=1, ensure_ascii=False)
    if not n_ok:
        if alt_weg: json.dump(J, open(a.oeffnungen, "w"), indent=1, ensure_ascii=False); print(f"{alt_weg} altes Gewaende-Band entfernt (neue Messung ohne Band)")
        print("kein Gewaende-Band vermessen"); return 3
    json.dump(J, open(a.oeffnungen, "w"), indent=1, ensure_ascii=False)
    print(f"-> {a.oeffnungen}: {n_ok} Gewaende-Band/Baender vermessen"); return 0


if __name__ == "__main__": sys.exit(main())
